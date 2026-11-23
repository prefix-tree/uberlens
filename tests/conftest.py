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
    return clips


@pytest.fixture(scope="session")
def backend() -> FFmpegBackend:
    return FFmpegBackend()
