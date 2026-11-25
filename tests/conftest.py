"""Short clips made with FFmpeg, one per way a file can make exact seeking hard."""

from __future__ import annotations

import subprocess
from pathlib import Path

import pytest

from uberseek.media import FFmpegBackend

PATTERN = "testsrc2=size=320x180:rate=30:duration=5"
# A tone with a silent second in the middle.
TONE = ["-f", "lavfi", "-i", "sine=frequency=440:duration=5", "-af", "volume=enable='between(t,2,3)':volume=0"]


def make(path: Path, *args: str) -> Path:
    subprocess.run(["ffmpeg", "-v", "error", "-y", *args, str(path)], check=True)
    return path


@pytest.fixture(scope="session")
def clips(tmp_path_factory) -> dict[str, Path]:
    d = tmp_path_factory.mktemp("clips")
    video = ["-f", "lavfi", "-i", PATTERN]
    h264 = ["-c:v", "libx264", "-bf", "2", "-g", "40", "-pix_fmt", "yuv420p"]
    clips = {
        # Frames stored out of order (B-frames), with sound.
        "bframes": make(d / "bframes.mp4", *video, *TONE, *h264, "-c:a", "aac"),
        # Frames unevenly spaced in time.
        "vfr": make(d / "vfr.mkv", *video, "-vf", r"select='not(mod(n\,3))+gt(mod(n\,7)\,4)'", "-fps_mode", "vfr", *h264),
        "hevc": make(d / "hevc.mp4", *video, "-c:v", "libx265", "-x265-params", "log-level=error:keyint=40", "-tag:v", "hvc1"),
        "vp9": make(d / "vp9.webm", *video, "-c:v", "libvpx-vp9", "-b:v", "400k", "-g", "40", "-cpu-used", "8"),
    }
    # Timestamps that do not start at zero.
    clips["offset"] = make(d / "offset.ts", "-i", str(clips["bframes"]), "-c", "copy", "-f", "mpegts")
    # A stream copy cut away from a keyframe: the container hides the frames before the cut.
    clips["trimmed"] = make(d / "trimmed.mp4", "-ss", "1.7", "-i", str(clips["bframes"]), "-c", "copy")
    # Stored sideways, shown upright.
    clips["rotated"] = make(d / "rotated.mp4", "-display_rotation", "90", "-i", str(clips["bframes"]), "-c", "copy")
    # Sound that starts one second after the picture.
    clips["late_sound"] = make(
        d / "late_sound.mkv", *video, "-itsoffset", "1", "-f", "lavfi", "-i", "sine=frequency=440:duration=3", *h264, "-c:a", "aac"
    )
    # Three shots: cuts at 2.5 s and 4.5 s.
    parts = [
        "smptebars=size=320x180:rate=30:duration=2.5",
        "testsrc=size=320x180:rate=30:duration=2",
        "gradients=size=320x180:rate=30:duration=1.5",
    ]
    clips["three_shots"] = make(d / "three_shots.mp4", *lavfi(parts), "-filter_complex", "concat=n=3:v=1:a=0", *h264)
    # Eighty seconds in ten shots of eight seconds, small and at five frames a second so it is quick to make.
    parts = [f"{'smptebars' if i % 2 else 'testsrc'}=size=160x90:rate=5:duration=8" for i in range(10)]
    clips["ten_shots"] = make(d / "ten_shots.mp4", *lavfi(parts), "-filter_complex", "concat=n=10:v=1:a=0", *h264, "-g", "10")
    # A moving picture with a white flash frame at frame 45 (1.5 s), then frame 80 held for a second.
    held = r"drawbox=c=white:t=fill:enable='eq(n\,45)',loop=loop=30:size=1:start=80"
    clips["flash_freeze"] = make(d / "flash_freeze.mp4", *video[:-1], PATTERN.replace("duration=5", "duration=4"), "-vf", held, *h264)
    # A collage that builds in 0.7 s: six grey strips appear on a dark ground, left to right, one every 4 frames from 1 s.
    strips = ",".join(f"drawbox=x={round(k * 320 / 6)}:y=0:w=54:h=180:c=0xa0a0a0:t=fill:enable='gte(n,{30 + 4 * k})'" for k in range(6))
    ground = ["-f", "lavfi", "-i", "color=c=0x202020:size=320x180:rate=30:duration=3"]
    clips["strips"] = make(d / "strips.mp4", *ground, "-vf", strips, *h264)
    # Twelve minutes, one shot.
    clips["long"] = make(d / "long.mp4", "-f", "lavfi", "-i", "testsrc=size=160x90:rate=2:duration=720", *h264, "-g", "20")
    return clips


def lavfi(sources: list[str]) -> list[str]:
    return [arg for source in sources for arg in ("-f", "lavfi", "-i", source)]


SPOKEN = "The company almost failed in the second year. We had no money left and nobody believed in us."


@pytest.fixture(scope="session")
def speech(tmp_path_factory) -> Path:
    """A synthetic voice saying SPOKEN from 1.5 s, over a moving picture. Skipped where FFmpeg cannot speak."""
    filters = subprocess.run(["ffmpeg", "-hide_banner", "-filters"], capture_output=True, text=True).stdout
    if " flite " not in filters:
        pytest.skip("this FFmpeg has no speech synthesis (flite)")
    inputs = ["-f", "lavfi", "-i", f"flite=text='{SPOKEN}':voice=slt", "-f", "lavfi", "-i", "testsrc2=size=320x180:rate=25:duration=9"]
    encode = ["-af", "adelay=1500,apad=pad_dur=2", "-shortest", "-c:v", "libx264", "-c:a", "aac"]
    return make(tmp_path_factory.mktemp("speech") / "speech.mp4", *inputs, *encode)


@pytest.fixture(scope="session")
def backend() -> FFmpegBackend:
    return FFmpegBackend()
