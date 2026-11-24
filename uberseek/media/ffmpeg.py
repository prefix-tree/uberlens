"""The reference backend: FFmpeg and ffprobe, run as host-side processes.

Exactness rests on two things. Frames are chosen by presentation timestamp, never by counting or by
rounding seconds. And every decode reports the timestamps it produced, which are checked against the
ones asked for, so a wrong seek fails loudly instead of returning a neighbouring frame.
"""

from __future__ import annotations

import json
import math
import re
import subprocess
from dataclasses import dataclass
from fractions import Fraction
from itertools import groupby
from pathlib import Path

from uberseek.media.backend import (
    AudioStream,
    Frame,
    FrameIndex,
    FrameRef,
    MediaError,
    Segment,
    SourceInfo,
    VideoStream,
)
from uberseek.timecode import Seconds

_SCALE = "bicubic+accurate_rnd+full_chroma_int+bitexact"
_SHOWINFO_PTS = re.compile(rb"Parsed_showinfo_\d+ @ \w+\] n:\s*\d+ pts:\s*(-?\d+)")
_SHOWINFO_TB = re.compile(rb"Parsed_showinfo_\d+ @ \w+\] config in time_base: (\d+)/(\d+)")


def _run(args: list[str]) -> subprocess.CompletedProcess[bytes]:
    try:
        done = subprocess.run(args, capture_output=True, check=False)
    except FileNotFoundError as error:
        raise MediaError(f"{args[0]} is not installed") from error
    if done.returncode != 0:
        tail = done.stderr.decode(errors="replace").strip().splitlines()[-3:]
        raise MediaError(f"{args[0]} failed: {' | '.join(tail)}")
    return done


def _decimal(t: Seconds, *, up: bool = False) -> str:
    """Seconds as a decimal with microseconds, which is the precision FFmpeg options keep."""
    micro = math.ceil(t * 1_000_000) if up else math.floor(t * 1_000_000)
    sign = "-" if micro < 0 else ""
    whole, part = divmod(abs(micro), 1_000_000)
    return f"{sign}{whole}.{part:06d}"


@dataclass
class FFmpegBackend:
    ffmpeg: str = "ffmpeg"
    ffprobe: str = "ffprobe"
    name: str = "ffmpeg"

    @property
    def version(self) -> str:
        first = _run([self.ffmpeg, "-version"]).stdout.decode().splitlines()[0]
        return first.split()[2]

    def probe(self, path: Path) -> SourceInfo:
        out = _run([self.ffprobe, "-v", "error", "-show_streams", "-show_format", "-of", "json", str(path)])
        data = json.loads(out.stdout)
        streams = data.get("streams", [])
        video = next((s for s in streams if s["codec_type"] == "video"), None)
        audio = next((s for s in streams if s["codec_type"] == "audio"), None)
        return SourceInfo(
            format=data["format"]["format_name"],
            duration=Fraction(data["format"].get("duration", "0")),
            video=_video(video) if video else None,
            audio=AudioStream(audio["codec_name"], int(audio["sample_rate"]), int(audio["channels"])) if audio else None,
        )

    def frame_index(self, path: Path) -> FrameIndex:
        """Read the index from packets, which needs no decoding.

        Packets the demuxer marks to be discarded (cut away by an edit list) are left out. A codec that
        stores frames it never shows would list one too many; decoding such a frame then fails the
        timestamp check in `frames`.
        """
        out = _run(
            [self.ffprobe, "-v", "error", "-select_streams", "v:0", "-show_entries",
             "stream=time_base:packet=pts,flags", "-of", "json", str(path)]
        )  # fmt: skip
        data = json.loads(out.stdout)
        if not data.get("streams"):
            raise MediaError(f"{path.name} has no video stream")
        frames = {int(p["pts"]): "K" in p["flags"] for p in data.get("packets", []) if "pts" in p and "D" not in p["flags"]}
        if not frames:
            raise MediaError(f"{path.name} has no video frames with timestamps")
        refs = tuple(FrameRef(pts, key) for pts, key in sorted(frames.items()))
        return FrameIndex(Fraction(data["streams"][0]["time_base"]), refs)

    def frames(self, path: Path, index: FrameIndex, pts: list[int], size: tuple[int, int]) -> list[Frame]:
        """Decode each group of frames from the keyframe before it.

        If a group comes back incomplete, the seek landed past its keyframe; retry from the keyframe
        before, and last from the start of the file.
        """
        known = {f.pts for f in index.frames}
        if unknown := [p for p in pts if p not in known]:
            raise MediaError(f"no frame with pts {unknown[0]} in {path.name}")
        found: dict[int, Frame] = {}
        wanted = sorted(set(pts))
        for _, group in groupby(wanted, key=lambda p: index.keyframes_before(p)[:1]):
            targets = list(group)
            starts: list[int | None] = [*index.keyframes_before(targets[0])[:2], None]
            for start in starts:
                seek = None if start is None else index.time(start)
                got = self._decode(path, index.time_base, seek, targets, size)
                if len(got) == len(targets):
                    found.update(got)
                    break
            else:
                missing = [p for p in targets if p not in got]
                raise MediaError(f"{path.name}: frames with pts {missing} are indexed but did not decode")
        return [found[p] for p in pts]

    def _decode(self, path: Path, time_base: Fraction, seek: Seconds | None, targets: list[int], size: tuple[int, int]) -> dict[int, Frame]:
        width, height = size
        select = "+".join(f"eq(pts\\,{p})" for p in targets)
        args = [self.ffmpeg, "-v", "info", "-nostdin", "-nostats"]
        if seek is not None:
            # An absolute seek that drops nothing: the select filter picks frames by timestamp.
            args += ["-seek_timestamp", "1", "-noaccurate_seek", "-ss", _decimal(seek, up=True)]
        args += [
            "-copyts", "-i", str(path), "-map", "0:v:0", "-an", "-sn", "-dn",
            "-vf", f"select='{select}',showinfo=checksum=0,scale={width}:{height}:flags={_SCALE},setsar=1",
            "-fps_mode", "passthrough", "-frames:v", str(len(targets)),
            "-f", "rawvideo", "-pix_fmt", "rgb24", "pipe:1",
        ]  # fmt: skip
        done = _run(args)
        if (tb := _SHOWINFO_TB.search(done.stderr)) and Fraction(int(tb[1]), int(tb[2])) != time_base:
            raise MediaError(f"{path.name}: decoded in time base {tb[1].decode()}/{tb[2].decode()}, not {time_base}")
        decoded = [int(m[1]) for m in _SHOWINFO_PTS.finditer(done.stderr)]
        step = width * height * 3
        if len(done.stdout) != step * len(decoded):
            raise MediaError(f"{path.name}: got {len(done.stdout)} bytes for {len(decoded)} frames of {step}")
        return {p: Frame(p, width, height, done.stdout[i * step : (i + 1) * step]) for i, p in enumerate(decoded)}

    def audio(self, path: Path, start: Seconds, duration: Seconds, rate: int) -> bytes:
        count = math.ceil(duration * rate)
        done = _run(
            [self.ffmpeg, "-v", "error", "-nostdin", "-seek_timestamp", "1", "-ss", _decimal(start),
             "-i", str(path), "-map", "0:a:0", "-vn", "-sn", "-dn",
             # Sound that starts after `start` is placed where it belongs, with silence before it.
             "-af", f"aresample={rate}:async=1:first_pts=0",
             "-ac", "1", "-t", _decimal(duration, up=True), "-flags:a", "+bitexact",
             "-f", "s16le", "pipe:1"]
        )  # fmt: skip
        return done.stdout[: count * 2].ljust(count * 2, b"\0")

    def join(self, segments: list[Segment], out: Path, size: tuple[int, int], sound: bool) -> list[str]:
        command = _join_command(self.ffmpeg, segments, out, size, sound)
        _run(command)
        return command

    def decodes(self, path: Path) -> list[str]:
        done = subprocess.run(
            [self.ffmpeg, "-v", "error", "-nostdin", "-i", str(path), "-f", "null", "-"], capture_output=True, check=False
        )
        said = done.stderr.decode(errors="replace").strip().splitlines()
        return said[:5] if done.returncode != 0 or said else []


def _join_command(ffmpeg: str, segments: list[Segment], out: Path, size: tuple[int, int], sound: bool) -> list[str]:
    """One FFmpeg command: each segment is its own input, seeked to the keyframe before it and trimmed by timestamp.

    Frames are chosen by presentation timestamp, so the cut does not depend on where keyframes fall. The
    result is encoded again; a stream copy could only cut on keyframes.
    """
    width, height = size
    args, graph, joined = [ffmpeg, "-v", "error", "-nostdin", "-y"], [], []
    for i, segment in enumerate(segments):
        index = segment.index
        if before := index.keyframes_before(segment.first)[:1]:
            args += ["-seek_timestamp", "1", "-noaccurate_seek", "-ss", _decimal(index.time(before[0]), up=True)]
        args += ["-copyts", "-i", str(segment.path)]
        picture = f"trim=start_pts={segment.first}:end_pts={segment.end},setpts=PTS-STARTPTS"
        graph.append(f"[{i}:v:0]{picture},scale={width}:{height}:flags={_SCALE},setsar=1,format=yuv420p[v{i}]")
        joined.append(f"[v{i}]")
        if sound:
            start, end = _decimal(index.time(segment.first)), _decimal(index.time(segment.end))
            graph.append(
                f"[{i}:a:0]atrim=start={start}:end={end},asetpts=PTS-STARTPTS,aresample=48000,aformat=channel_layouts=stereo[a{i}]"
            )
            joined.append(f"[a{i}]")
    graph.append(f"{''.join(joined)}concat=n={len(segments)}:v=1:a={int(sound)}[v]" + ("[a]" if sound else ""))
    args += ["-filter_complex", ";".join(graph), "-map", "[v]", *(["-map", "[a]", "-c:a", "aac", "-b:a", "160k"] if sound else [])]
    return [*args, "-c:v", "libx264", "-crf", "18", "-preset", "veryfast", "-fps_mode", "passthrough", "-movflags", "+faststart", str(out)]


def _video(stream: dict) -> VideoStream:
    rotation = 0
    for side in stream.get("side_data_list", []):
        if "rotation" in side:
            rotation = int(side["rotation"]) % 360
    width, height = int(stream["width"]), int(stream["height"])
    sar = stream.get("sample_aspect_ratio", "1:1").replace(":", "/")
    if Fraction(sar) > 0:
        width = round(width * Fraction(sar))
    if rotation in (90, 270):
        width, height = height, width
    return VideoStream(stream["codec_name"], width, height, Fraction(stream["time_base"]), rotation)
