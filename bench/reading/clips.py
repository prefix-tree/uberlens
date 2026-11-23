"""Generated clips with known contents: when a square appears, where the sound is silent, where the cut is."""

from __future__ import annotations

import subprocess
from pathlib import Path

DURATION = 8
_ENCODE = ["-c:v", "libx264", "-pix_fmt", "yuv420p", "-g", "30", "-c:a", "aac"]


def _make(path: Path, *args: str) -> Path:
    if not path.exists():
        path.parent.mkdir(parents=True, exist_ok=True)
        subprocess.run(["ffmpeg", "-v", "error", "-y", *args, *_ENCODE, str(path)], check=True)
    return path


def _tone(quiet: tuple[float, float]) -> list[str]:
    a, b = quiet
    return ["-f", "lavfi", "-i", f"sine=frequency=330:duration={DURATION}", "-af", f"volume=enable='between(t,{a},{b})':volume=0"]


def event(folder: Path, appears: float, quiet: tuple[float, float]) -> Path:
    """A slow colour gradient. A red square appears at `appears` and stays; the tone is silent during `quiet`."""
    square = f"drawbox=x=420:y=200:w=120:h=120:color=red:t=fill:enable='gte(t,{appears})'"
    name = f"event_{appears}_{quiet[0]}_{quiet[1]}.mp4"
    source = f"gradients=size=640x360:rate=30:duration={DURATION}:speed=0.02"
    return _make(folder / name, "-f", "lavfi", "-i", source, *_tone(quiet), "-vf", square)


def cut(folder: Path, at: float) -> Path:
    """Colour bars until `at`, then a different test picture: one cut."""
    first = f"smptebars=size=640x360:rate=30:duration={at}"
    second = f"testsrc=size=640x360:rate=30:duration={DURATION - at}"
    joined = "[0:v][1:v]concat=n=2:v=1:a=0"
    return _make(
        folder / f"cut_{at}.mp4",
        "-f", "lavfi", "-i", first, "-f", "lavfi", "-i", second, *_tone((0, 0)), "-filter_complex", joined,
    )  # fmt: skip
