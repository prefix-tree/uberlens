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
# Pauses in speech that a fixed threshold misses because music or room sound fills them. The level of the voice
# band is measured every 20 ms; a pause is where it falls well below the speech around it, judged against the
# loud and quiet ends of the surrounding seconds rather than against one number for the whole file.
VOICE = {
    "band_hz": [300, 3400],  # where speech carries most of its energy, and where bass and cymbals do not
    "frame_seconds": "0.02",
    "window_seconds": 6,  # the stretch either side that sets what speech and quiet sound like here
    "contrast_db": 6,  # a stretch whose loud and quiet ends are closer than this has no pauses to tell apart
    "share": "0.35",  # a pause is quieter than the quiet end plus this share of the way to the loud end
    "min_seconds": "0.25",
}
CUT = {"threshold": 10, "width": 320}
TOUCH = Fraction(1, 50)  # silences closer than this are one silence

_SILENCE = re.compile(r"silence_(start|end): (-?[\d.]+)")
_CUT = re.compile(r"frame:\d+\s+pts:(-?\d+)\s+pts_time:\S+\s+lavfi\.scd\.time=")
_LEVEL = re.compile(r"pts_time:(-?[\d.]+)\s+lavfi\.astats\.Overall\.RMS_level=(-?[\d.]+|-?inf|nan)")
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


def voice_levels(path: Path, ffmpeg: str = "ffmpeg") -> list[tuple[Fraction, float]]:
    """The level of the voice band, in dB, every 20 ms: (time, level) pairs. Silence is -100."""
    low, high = VOICE["band_hz"]
    samples = int(16_000 * Fraction(VOICE["frame_seconds"]))
    graph = (
        f"aresample=16000,highpass=f={low},lowpass=f={high},asetnsamples=n={samples}:p=0,"
        "astats=metadata=1:reset=1:measure_perchannel=none:measure_overall=RMS_level,"
        "ametadata=mode=print:key=lavfi.astats.Overall.RMS_level:file=-"
    )
    out = []
    for t, v in _LEVEL.findall(_filter(path, "a:0", graph, ffmpeg)):
        level = -100.0 if v in ("-inf", "nan") else max(-100.0, float(v))
        out.append((Fraction(t), level))
    return out


def _percentile(values: list[float], share: float) -> float:
    ordered = sorted(values)
    return ordered[min(len(ordered) - 1, int(share * len(ordered)))]


def quiet_stretches(levels: list[tuple[Fraction, float]], rule: dict = VOICE) -> list[tuple[Fraction, Fraction]]:
    """Where the voice band falls well below the speech around it, for at least `min_seconds`.

    Every half second, the surrounding `window_seconds` either side give a loud end (the 90th percentile)
    and a quiet end (the 10th). A frame is quiet when it is below the quiet end plus `share` of the
    distance between them. Where the two ends are too close to tell speech from its gaps (music alone, or
    speech with no gaps), the nearest threshold that could tell them apart is used instead, so a long
    stretch of music between two lines is still a pause.
    """
    if not levels:
        return []
    step = Fraction(rule["frame_seconds"])
    half = int(Fraction(rule["window_seconds"]) / step)
    every = max(1, int(Fraction(1, 2) / step))
    share, contrast = float(Fraction(rule["share"])), float(rule["contrast_db"])
    values = [v for _, v in levels]
    grid: list[float | None] = []
    for i in range(0, len(values), every):
        near = values[max(0, i - half) : i + half + 1]
        loud, quiet = _percentile(near, 0.9), _percentile(near, 0.1)
        grid.append(quiet + share * (loud - quiet) if loud - quiet >= contrast else None)
    known = [i for i, g in enumerate(grid) if g is not None]
    if not known:
        return []  # nothing anywhere tells speech from quiet
    filled, k = [], 0
    for i in range(len(grid)):
        while k + 1 < len(known) and abs(known[k + 1] - i) <= abs(known[k] - i):
            k += 1
        filled.append(grid[known[k]])
    # A level is judged against the threshold of the nearest grid point; a single loud frame does not end a pause.
    quiet = [values[i] < filled[min(len(filled) - 1, (i + every // 2) // every)] for i in range(len(values))]
    for i in range(1, len(quiet) - 1):
        if not quiet[i] and quiet[i - 1] and quiet[i + 1]:
            quiet[i] = True
    out, begin = [], None
    for i, (t, _) in enumerate(levels):
        if quiet[i] and begin is None:
            begin = t
        elif not quiet[i] and begin is not None:
            out.append((begin, t))
            begin = None
    if begin is not None:
        out.append((begin, levels[-1][0] + step))
    shortest = Fraction(rule["min_seconds"])
    return [(a, b) for a, b in out if b - a >= shortest]


def voice_pauses(path: Path, ffmpeg: str = "ffmpeg") -> dict:
    """Pauses in speech that are found under music too: [start, end] pairs in seconds."""
    spans = quiet_stretches(voice_levels(path, ffmpeg))
    return {
        "kind": "measured",
        "tool": "ffmpeg astats, voice band against the speech around it",
        "params": VOICE,
        "spans": [[f"{float(a):.3f}", f"{float(b):.3f}"] for a, b in spans],
    }


def cuts(path: Path, ffmpeg: str = "ffmpeg") -> dict:
    """Where the picture changes abruptly: the timestamp of the first frame after each cut.

    The whole picture stream is decoded once, so this is the slowest signal. It is made only when a look
    needs it.
    """
    graph = f"scale={CUT['width']}:-2,scdet=threshold={CUT['threshold']},metadata=mode=print:key=lavfi.scd.time:file=-"
    found = sorted({int(pts) for pts in _CUT.findall(_filter(path, "v:0", graph, ffmpeg))})
    return {"kind": "measured", "tool": "ffmpeg scdet", "params": CUT, "pts": found}


def within(spans: list[list[str]], start: Fraction, end: Fraction) -> list[tuple[Fraction, Fraction]]:
    """The parts of the spans that fall inside [start, end].

    Silences that touch are one silence: the detector sometimes ends a silence and starts the next at the
    same instant, on a single loud sample, and a four-second pause must not be reported as two short ones.
    """
    out: list[tuple[Fraction, Fraction]] = []
    for a, b in spans:
        a, b = Fraction(a), Fraction(b)
        if out and a - out[-1][1] <= TOUCH:
            a = out.pop()[0]
        out.append((a, b))
    clipped = [(max(a, start), min(b, end)) for a, b in out]
    return [(a, b) for a, b in clipped if a < b]
