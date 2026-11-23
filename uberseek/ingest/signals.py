"""Signals: measurements over time, made once per source by code and kept with where they came from.

They guide where to look and what to draw. They never decide anything.
"""

from __future__ import annotations

import re
import subprocess
from fractions import Fraction
from pathlib import Path

from uberseek.media.backend import MediaError

SILENCE = {"noise_db": -35, "min_seconds": "0.25"}
CUT = {"threshold": 10, "width": 320}

_SILENCE = re.compile(r"silence_(start|end): (-?[\d.]+)")
_CUT = re.compile(r"frame:\d+\s+pts:(-?\d+)\s+pts_time:\S+\s+lavfi\.scd\.time=")
_LOUDNESS = re.compile(r"pts_time:([\d.]+)\s+lavfi\.r128\.M=(-?[\d.]+|-?inf|nan)")


def _filter(path: Path, stream: str, graph: str, ffmpeg: str) -> str:
    """Run one stream through a filter graph and return what FFmpeg printed.

    `-copyts` keeps the file's own timestamps, so a measurement lines up with the frames even when the
    file does not start at zero.
    """
    kind = "-af" if stream.startswith("a") else "-vf"
    done = subprocess.run(
        [ffmpeg, "-v", "info", "-nostdin", "-nostats", "-copyts", "-i", str(path), "-map", f"0:{stream}", kind, graph, "-f", "null", "-"],
        capture_output=True,
        check=False,
    )
    if done.returncode != 0:
        raise MediaError(f"ffmpeg failed on {path.name}: {done.stderr.decode(errors='replace')[-300:]}")
    return done.stdout.decode() + done.stderr.decode(errors="replace")


def silences(path: Path, ffmpeg: str = "ffmpeg") -> dict:
    """Stretches quieter than the threshold: [start, end] pairs in seconds, as FFmpeg reports them."""
    graph = f"silencedetect=noise={SILENCE['noise_db']}dB:d={SILENCE['min_seconds']}"
    spans: list[list[str]] = []
    for kind, value in _SILENCE.findall(_filter(path, "a:0", graph, ffmpeg)):
        if kind == "start":
            spans.append([value])
        elif spans and len(spans[-1]) == 1:
            spans[-1].append(value)
    return {
        "kind": "measured",
        "tool": "ffmpeg silencedetect",
        "params": SILENCE,
        "spans": [s for s in spans if len(s) == 2],  # one still open at the end of the file is dropped
    }


def loudness(path: Path, ffmpeg: str = "ffmpeg") -> dict:
    """Momentary loudness (EBU R 128, a 400 ms window) every 100 ms: [time, LUFS] pairs."""
    text = _filter(path, "a:0", "ebur128=metadata=1,ametadata=mode=print:key=lavfi.r128.M:file=-", ffmpeg)
    points = [[t, v] for t, v in _LOUDNESS.findall(text) if v not in ("nan", "inf", "-inf")]
    return {"kind": "measured", "tool": "ffmpeg ebur128", "params": {"window": "momentary"}, "points": points}


def cuts(path: Path, ffmpeg: str = "ffmpeg") -> dict:
    """Where the picture changes abruptly: the timestamp of the first frame after each cut.

    The whole picture stream is decoded once, so this is the slowest signal. It is made only when a look
    needs it.
    """
    graph = f"scale={CUT['width']}:-2,scdet=threshold={CUT['threshold']},metadata=mode=print:key=lavfi.scd.time:file=-"
    found = sorted({int(pts) for pts in _CUT.findall(_filter(path, "v:0", graph, ffmpeg))})
    return {"kind": "measured", "tool": "ffmpeg scdet", "params": CUT, "pts": found}


def within(spans: list[list[str]], start: Fraction, end: Fraction) -> list[tuple[Fraction, Fraction]]:
    """The parts of the spans that fall inside [start, end]."""
    out = []
    for a, b in spans:
        a, b = max(Fraction(a), start), min(Fraction(b), end)
        if a < b:
            out.append((a, b))
    return out
