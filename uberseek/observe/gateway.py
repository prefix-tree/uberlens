"""The observe gateway: the one way footage reaches the model.

Every observation says what it delivered, is stored with its picture, and can be made again from its
log entry alone. `reproduce` is the proof: same file, same timestamps, same pixels.
"""

from __future__ import annotations

import hashlib
import statistics
import time
from dataclasses import dataclass, field
from fractions import Fraction
from itertools import pairwise
from pathlib import Path

import PIL

from uberseek.ingest import signals
from uberseek.media import FFmpegBackend, FrameIndex, FrameRef, MediaBackend, MediaError, SourceInfo
from uberseek.observe import render
from uberseek.observe.plan import SAMPLE_RATE, WAVEFORM_MAX, plan, tile_size
from uberseek.state.log import Log
from uberseek.timecode import Seconds, clock, seconds


@dataclass(frozen=True)
class Source:
    path: Path
    hash: str
    info: SourceInfo
    index: FrameIndex


@dataclass(frozen=True)
class Observation:
    """What the model is given: one picture, and a plain statement of what it shows."""

    id: str
    image: bytes
    text: str
    record: dict

    media_type = "image/png"


@dataclass(frozen=True)
class Reproduction:
    id: str
    frames: bool  # every frame decoded again has the same pixels
    sound: bool  # the sound samples are the same
    picture: bool  # the picture drawn again is the same file, byte for byte
    notes: list[str] = field(default_factory=list)

    @property
    def exact(self) -> bool:
        return self.frames and self.sound and self.picture


def _fraction(value: Fraction) -> str:
    return f"{value.numerator}/{value.denominator}"


class Project:
    """A folder holding the log, the pictures shown and what was derived from each source."""

    def __init__(self, root: Path | str = ".", backend: MediaBackend | None = None):
        self.log = Log(Path(root))
        self.backend = backend or FFmpegBackend()

    def open(self, path: Path | str) -> Source:
        path = Path(path)
        digest = self.log.content_hash(path)
        info = self.backend.probe(path)
        if info.video is None:
            raise MediaError(f"{path.name} has no video stream")

        def index() -> dict:
            made = self.backend.frame_index(path)
            return {"time_base": _fraction(made.time_base), "frames": [[f.pts, int(f.key)] for f in made.frames]}

        cached = self.log.derived(digest, "frame_index", index)
        frames = tuple(FrameRef(pts, bool(key)) for pts, key in cached["frames"])
        return Source(path, digest, info, FrameIndex(Fraction(cached["time_base"]), frames))

    def observe(
        self,
        path: Path | str,
        start: Seconds | str | int,
        end: Seconds | str | int | None = None,
        focus: str = "visual",
        purpose: str = "",
    ) -> Observation:
        """Show a span of the footage. The caller sets the span and the focus; the harness sets the rest."""
        source = self.open(path)
        start = seconds(start)
        made = plan(
            source.index, source.info.duration, source.info.audio is not None,
            start, start if end is None else seconds(end), focus,
        )  # fmt: skip
        size, columns = tile_size((source.info.video.width, source.info.video.height), made.tile_long, len(made.targets))
        request = {
            "start": _fraction(made.start),
            "end": _fraction(made.end),
            "focus": focus,
            "purpose": purpose,
        }
        recipe = {
            "level": made.level,
            "targets": list(made.targets),
            "frame_size": list(size),
            "columns": columns,
            "sound": [_fraction(t) for t in made.sound] if made.sound else None,
            "mark": _fraction(made.mark) if made.mark is not None else None,
        }
        began = time.perf_counter()
        image, delivered = self._render(source, recipe)
        gaps = [float(b - a) * float(source.index.time_base) for a, b in pairwise(made.targets)]
        record = self.log.append(
            {
                "source": {"hash": source.hash, "path": str(source.path), "format": source.info.format},
                "request": request,
                "recipe": recipe,
                "delivered": {
                    **delivered,
                    "frames_in_span": made.in_span,
                    "gap_seconds": {"median": statistics.median(gaps), "max": max(gaps)} if gaps else None,
                    "heard": False,
                },
                "artifact": {
                    "sha256": self.log.put_artifact(image, ".png"),
                    "media_type": Observation.media_type,
                    "bytes": len(image),
                },
                "backend": {"name": self.backend.name, "version": self.backend.version, "pillow": PIL.__version__},
                "cost": {"seconds": round(time.perf_counter() - began, 3)},
                "relates": [],
            }
        )
        return Observation(record["id"], image, _describe(record, source), record)

    def show(self, id: str) -> Observation:
        """A past observation again, from its stored picture. Nothing is decoded."""
        record = self.log.get(id)
        image = self.log.artifact(record["artifact"]["sha256"], ".png")
        return Observation(id, image, _describe(record, None), record)

    def reproduce(self, id: str, path: Path | str | None = None) -> Reproduction:
        """Make a logged observation again and compare it with what was shown."""
        record = self.log.get(id)
        source = self.open(path or record["source"]["path"])
        if source.hash != record["source"]["hash"]:
            return Reproduction(id, False, False, False, ["the file's content is not the version that was observed"])
        image, delivered = self._render(source, record["recipe"])
        was, notes = record["delivered"], []
        frames = delivered["frames"] == was["frames"]
        sound = delivered["sound"] == was["sound"]
        picture = hashlib.sha256(image).hexdigest() == record["artifact"]["sha256"]
        if not frames:
            notes.append("decoded frames differ")
        if not sound:
            notes.append("sound samples differ")
        if frames and sound and not picture:
            notes.append("same frames and sound, drawn differently: check the Pillow version")
        return Reproduction(id, frames, sound, picture, notes)

    def _render(self, source: Source, recipe: dict) -> tuple[bytes, dict]:
        """Decode and draw exactly what the recipe says, and report what came out."""
        index, targets = source.index, recipe["targets"]
        frames = self.backend.frames(source.path, index, targets, tuple(recipe["frame_size"]))
        times = [index.time(pts) for pts in targets]
        picture = render.sheet(frames, times, recipe["columns"])
        delivered: dict = {
            "time_base": _fraction(index.time_base),
            "frames": [{"pts": f.pts, "pixels_sha256": f.pixel_hash} for f in frames],
            "size": None,
            "drawn": ["frames"],
            "sound": None,
        }
        if recipe["sound"]:
            start, end = (Fraction(t) for t in recipe["sound"])
            quiet = self.log.derived(source.hash, "silences", lambda: signals.silences(source.path))
            if end - start <= WAVEFORM_MAX:
                pcm = self.backend.audio(source.path, start, end - start, SAMPLE_RATE)
                wave, caption = render.envelope(pcm, picture.width), "sound wave (decibel scale)"
                delivered["sound"] = {"kind": "waveform", "rate": SAMPLE_RATE, "samples_sha256": hashlib.sha256(pcm).hexdigest()}
            else:
                loud = self.log.derived(source.hash, "loudness", lambda: signals.loudness(source.path))
                wave, caption = render.loudness_envelope(loud["points"], (start, end), picture.width), "measured loudness"
                delivered["sound"] = {"kind": "loudness", "tool": loud["tool"]}
            pauses = signals.within(quiet["spans"], start, end)
            delivered["sound"] |= {
                "start": _fraction(start),
                "end": _fraction(end),
                "pauses": [[_fraction(a), _fraction(b)] for a, b in pauses],
                "pause_rule": quiet["params"],
            }
            delivered["drawn"] += [delivered["sound"]["kind"], "silences"]
            mark = Fraction(recipe["mark"]) if recipe["mark"] else None
            caption += ", silences shaded, ticks are the numbered frames" + (", the line is the instant asked about" if mark else "")
            picture = render.stack(picture, render.strip(picture.width, (start, end), wave, pauses, times, mark, caption))
        delivered["size"] = list(picture.size)
        return render.png(picture), delivered


def _describe(record: dict, source: Source | None) -> str:
    """The text that goes to the model with the picture: what was asked, and what was actually delivered."""
    request, delivered, recipe = record["request"], record["delivered"], record["recipe"]
    base = Fraction(delivered["time_base"])
    times = [frame["pts"] * base for frame in delivered["frames"]]
    start, end = Fraction(request["start"]), Fraction(request["end"])
    span = clock(start) if start == end else f"{clock(start)} to {clock(end)}"
    lines = [
        f"{record['id']}: {Path(record['source']['path']).name}, {span}, focus {request['focus']}, level {recipe['level']}.",
    ]
    count, width, height = len(times), *recipe["frame_size"]
    if count == 1:
        lines.append(f"1 frame, at {clock(times[0])}, {width}x{height}.")
    else:
        gap = delivered["gap_seconds"]
        apart = f"{gap['median']:.3f} s apart" + (f" (at most {gap['max']:.3f} s)" if gap["max"] > gap["median"] * 1.01 else "")
        lines.append(
            f"{count} frames from {clock(times[0])} to {clock(times[-1])}, {apart}, {width}x{height} each, "
            f"numbered in time order. The span holds {delivered['frames_in_span']} frames."
        )
    sound = delivered["sound"]
    if sound:
        what = "its wave" if sound["kind"] == "waveform" else "its measured loudness"
        pauses = [f"{clock(Fraction(a))} to {clock(Fraction(b))}" for a, b in sound["pauses"]]
        rule = sound["pause_rule"]
        lines.append(
            f"Sound from {clock(Fraction(sound['start']))} to {clock(Fraction(sound['end']))} is drawn as {what}. "
            + (
                f"Pauses (quieter than {rule['noise_db']} dB for {rule['min_seconds']} s or more): {'; '.join(pauses)}. "
                if pauses
                else "No pauses measured. "
            )
            + "You have seen the sound, not heard it: treat any judgment about it as not heard."
        )
    else:
        lines.append("No sound is shown.")
    return "\n".join(lines)
