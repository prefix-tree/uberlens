"""Signals: measurements over time, made once per source by code and kept with where they came from.

They guide where to look and what to draw. They never decide anything.
"""

from __future__ import annotations

import re
import subprocess
from fractions import Fraction
from pathlib import Path

from PIL import Image, ImageChops, ImageStat

from uberseek.media.backend import MediaError

SILENCE = {"noise_db": -35, "min_seconds": "0.25"}
CUT = {"threshold": 10, "width": 320}
TOUCH = Fraction(1, 50)  # silences closer than this are one silence
CHANGE = {"width": 192, "height": 108, "rows": 9, "columns": 16}  # frames are compared this small, in this grid of cells
EVENT = 8  # a part of the frame that differs this much from the frame before, and well above usual, has changed
REACH = 15  # frames either side that say what is usual for a part of the frame
PARTS = 3  # parts of the frame (of 16 by 9) that must change together for an event: fewer is a moving object
STAYS = 24  # a change is an event only if the new picture of a part is still there this many frames after it settles
STEP = 20  # how far a part's colour must move, on a scale of 0 to 255, to count as a new picture
STILL = 0.05  # a frame that differs less than this from the one before repeats it
NEARLY = 0.2  # one frame up to this, between two that repeat, is the encoder's noise and not motion
ONSET = {"rate": 8000, "window": 160, "rise_db": 6, "floor_db": -50, "apart": "0.08"}

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


def change(path: Path, frames: int, ffmpeg: str = "ffmpeg") -> dict:
    """How much each frame differs from the one before it: over the whole frame, and in each cell of a grid.

    Every frame is decoded once, small and grey, so this costs a pass over the picture. `mean` is the mean
    difference per pixel on a scale of 0 to 255, to three decimals: near zero for a repeated frame. `cells`
    holds, for each frame, one byte per cell of the grid, row by row: the mean difference in that part of
    the frame. A change in one part of the picture shows there and hardly at all in `mean`. `colours` holds,
    for each frame, the mean red, green and blue of each cell, so whether a change stays can be told.
    """
    width, height, rows, columns = CHANGE["width"], CHANGE["height"], CHANGE["rows"], CHANGE["columns"]
    run = subprocess.Popen(
        [ffmpeg, "-v", "error", "-nostdin", "-i", str(path), "-map", "0:v:0", "-an", "-sn", "-dn",
         "-vf", f"scale={width}:{height}:flags=area,format=rgb24", "-fps_mode", "passthrough", "-f", "rawvideo", "pipe:1"],
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
    )  # fmt: skip
    step, before, mean, cells, colours = width * height * 3, None, [], bytearray(), bytearray()
    while len(raw := run.stdout.read(step)) == step:
        picture = Image.frombytes("RGB", (width, height), raw)
        colours += picture.resize((columns, rows), Image.Resampling.BOX).tobytes()
        frame = picture.convert("L")
        if before is None:
            mean.append(0.0)
            cells += bytes(rows * columns)
        else:
            differs = ImageChops.difference(before, frame)
            mean.append(round(ImageStat.Stat(differs).mean[0], 3))
            cells += differs.resize((columns, rows), Image.Resampling.BOX).tobytes()
        before = frame
    said = run.stderr.read().decode(errors="replace")
    if run.wait() != 0:
        raise MediaError(f"ffmpeg failed on {path.name}: {said[-300:]}")
    if len(mean) != frames:
        raise MediaError(f"{path.name}: {len(mean)} frames decoded where the index lists {frames}, so change cannot be placed on frames")
    return {
        "kind": "measured",
        "tool": "ffmpeg and frame difference",
        "params": CHANGE,
        "mean": mean,
        "cells": cells.hex(),
        "colours": colours.hex(),
    }


def onsets(path: Path, ffmpeg: str = "ffmpeg") -> dict:
    """Instants where the sound gets suddenly louder: a hit, a beat, the start of a word after silence.

    The level is measured every 20 ms. An onset is a window at least `rise_db` louder than the mean of the
    three before it, and not closer than `apart` seconds to the one before.
    """
    graph = (
        f"aresample={ONSET['rate']},aformat=channel_layouts=mono,asetnsamples=n={ONSET['window']}:p=0,"
        "astats=metadata=1:reset=1,ametadata=mode=print:key=lavfi.astats.Overall.RMS_level:file=-"
    )
    levels = [
        (Fraction(t), max(-120.0, float(v)) if v not in ("nan", "-inf") else -120.0)
        for t, v in _LEVEL.findall(_filter(path, "a:0", graph, ffmpeg))
    ]
    found: list[list] = []
    for i in range(3, len(levels)):
        time, level = levels[i]
        rise = level - sum(v for _, v in levels[i - 3 : i]) / 3
        if (
            level > ONSET["floor_db"]
            and rise >= ONSET["rise_db"]
            and (not found or time - Fraction(found[-1][0]) >= Fraction(ONSET["apart"]))
        ):
            found.append([str(time), round(rise, 1)])
    return {"kind": "measured", "tool": "ffmpeg astats", "params": ONSET, "points": found}
