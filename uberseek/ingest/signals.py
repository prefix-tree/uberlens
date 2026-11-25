"""Signals: measurements over time, made once per source by code and kept with where they came from.

They guide where to look and what to draw. They never decide anything.
"""

from __future__ import annotations

import re
import subprocess
import tempfile
from array import array
from collections import deque
from fractions import Fraction
from pathlib import Path

from PIL import Image, ImageChops

from uberseek.media.backend import MediaError

SILENCE = {"noise_db": -35, "min_seconds": "0.25"}
CUT = {"threshold": 10, "width": 320}
# Change is measured on a small grey copy of each frame, cut into a grid of parts. Values are the mean
# difference from the frame before, in percent of the most a pixel can change.
CHANGE = {
    "size": 64,  # each frame is scaled to size x size, whatever its shape, so a part is a fixed share of the picture
    "grid": 8,  # parts across and down: each is an eighth of the width and of the height
    "flash": 12,  # a flash differs from the frames on both sides by at least this much
    "flash_match": 5,  # while those two sides differ from each other by at most this much
    "flash_frames": 3,  # the longest flash, in frames
    "still": 0.4,  # no part changes more than this: the picture is held
    "part": 15,  # a part that changes by at least this much has changed abruptly
    "part_most": 0.5,  # ... in at most this share of the picture
    "part_hold": 5,  # while the rest changes by at most this much on average, and on the next frame that part does too
    "part_frames": 12,  # an abrupt change of a part lasts at most this many frames; longer is motion
}
TOUCH = Fraction(1, 50)  # silences closer than this are one silence

_SILENCE = re.compile(r"silence_(start|end): (-?[\d.]+)")
_CUT = re.compile(r"frame:\d+\s+pts:(-?\d+)\s+pts_time:\S+\s+lavfi\.scd\.time=")
_SHOWINFO = re.compile(r"Parsed_showinfo_\d+ @ \w+\] n:\s*\d+ pts:\s*(-?\d+)")
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


def changes(path: Path, ffmpeg: str = "ffmpeg") -> dict:
    """How much the picture changes from each frame to the next, over the whole frame and in its parts.

    One pass decodes every frame to a small grey grid. For each frame it keeps the mean change over the
    whole frame and the change of the part that changed most, and it finds three kinds of event that
    `cuts` cannot see:

    - flashes: one to three frames unlike the frames on both sides, which are like each other;
    - freezes: runs of frames where no part of the picture changes;
    - parts: one part of the picture changes abruptly and then stays, while the rest holds (a strip of a
      collage appearing, a picture in a picture switching).

    Times are the file's own timestamps, frame by frame.
    """
    size, grid = CHANGE["size"], CHANGE["grid"]
    graph = f"showinfo=checksum=0,scale={size}:{size}:flags=area,format=gray"
    args = [ffmpeg, "-v", "info", "-nostdin", "-nostats", "-copyts", "-i", str(path), "-map", "0:v:0", "-an", "-sn", "-dn"]
    args += ["-vf", graph, "-fps_mode", "passthrough", "-f", "rawvideo", "-pix_fmt", "gray", "pipe:1"]
    measure = _Changes(size, grid)
    step = size * size
    with tempfile.TemporaryFile() as said:  # FFmpeg reports a line per frame; a file cannot fill up and stall it
        try:
            process = subprocess.Popen(args, stdout=subprocess.PIPE, stderr=said)
        except FileNotFoundError as error:
            raise MediaError(f"{ffmpeg} is not installed") from error
        with process.stdout:
            while len(chunk := process.stdout.read(step)) == step:
                measure.add(Image.frombytes("L", (size, size), chunk))
        failed = process.wait() != 0
        said.seek(0)
        text = said.read().decode(errors="replace")
    if failed:
        raise MediaError(f"ffmpeg failed on {path.name}: {text[-300:]}")
    pts = [int(p) for p in _SHOWINFO.findall(text)]
    if len(pts) != len(measure.whole):
        raise MediaError(f"{path.name}: {len(measure.whole)} frames decoded but {len(pts)} timestamps reported")
    measure.finish()
    return {
        "kind": "measured",
        "tool": "uberseek frame difference (ffmpeg, Pillow)",
        "params": CHANGE,
        "pts": pts,
        "whole": measure.whole,
        "part": measure.part,
        "flashes": [[pts[a], pts[b]] for a, b in measure.flashes],
        "freezes": [[pts[a], pts[b + 1] if b + 1 < len(pts) else None] for a, b in measure.freezes],
        "parts": [{"first": pts[a], "last": pts[b], "where": where, "change": peak} for a, b, where, peak in measure.parts],
    }


class _Changes:
    """The frame-by-frame bookkeeping of `changes`. Frames are numbered from 0 in decoding order."""

    def __init__(self, size: int, grid: int):
        self.size, self.grid = size, grid
        self.whole: list[float] = []  # change from the frame before, over the whole frame; 0 for the first
        self.part: list[float] = []  # the same, for the part that changed most
        self.flashes: list[tuple[int, int]] = []
        self.freezes: list[tuple[int, int]] = []
        self.parts: list[tuple[int, int, list[float], float]] = []
        self.recent: deque[Image.Image] = deque(maxlen=CHANGE["flash_frames"] + 2)
        self.held: int | None = None  # first frame of the run of held frames going on
        self.open: list[dict] = []  # parts changing on the frame before

    def _cells(self, a: Image.Image, b: Image.Image) -> list[float]:
        difference = ImageChops.difference(a, b).convert("F").resize((self.grid, self.grid), Image.Resampling.BOX)
        return [v * 100 / 255 for v in array("f", difference.tobytes())]

    def _apart(self, a: Image.Image, b: Image.Image) -> float:
        cells = self._cells(a, b)
        return sum(cells) / len(cells)

    def add(self, frame: Image.Image) -> None:
        n = len(self.whole)
        cells = self._cells(self.recent[-1], frame) if self.recent else [0.0] * self.grid**2
        whole, part = sum(cells) / len(cells), max(cells)
        self.whole.append(round(whole, 2))
        self.part.append(round(part, 2))
        if n:
            self._flash(n, frame, whole)
            self._freeze(n, part)
            self._parts(n, cells)
        self.recent.append(frame)

    def _flash(self, n: int, frame: Image.Image, whole: float) -> None:
        """Frame n changed a lot: see whether the frames just before it were a flash it returns from."""
        if whole < CHANGE["flash"]:
            return
        for k in range(1, CHANGE["flash_frames"] + 1):
            if k + 1 > len(self.recent) or (self.flashes and self.flashes[-1][1] >= n - k):
                return
            before, inside = self.recent[-k - 1], list(self.recent)[-k:]
            if self._apart(before, frame) > CHANGE["flash_match"]:
                continue
            if all(min(self._apart(before, f), self._apart(f, frame)) >= CHANGE["flash"] for f in inside):
                self.flashes.append((n - k, n - 1))
                return

    def _freeze(self, n: int, part: float) -> None:
        if part <= CHANGE["still"]:
            self.held = n - 1 if self.held is None else self.held
        elif self.held is not None:
            self.freezes.append((self.held, n - 1))
            self.held = None

    def _parts(self, n: int, cells: list[float]) -> None:
        """Group the parts that change abruptly into events, and keep the events whose part then stays."""
        changed = {i for i, v in enumerate(cells) if v >= CHANGE["part"]}
        rest = [v for i, v in enumerate(cells) if i not in changed]
        if len(changed) > len(cells) * CHANGE["part_most"] or sum(rest) / len(rest) > CHANGE["part_hold"]:
            changed = set()  # most of the picture changed: a cut, a flash or motion, not a part
        still_open = []
        for event in self.open:
            if event["cells"] & changed:
                event["cells"] |= changed
                event["peak"] = max(event["peak"], max(cells[i] for i in changed))
                event["last"] = n
                changed = set()
                still_open.append(event)
            elif max(cells[i] for i in event["cells"]) <= CHANGE["part_hold"] and event["last"] - event["first"] < CHANGE["part_frames"]:
                self._keep(event)
        if changed:
            still_open.append({"first": n, "last": n, "cells": changed, "peak": max(cells[i] for i in changed)})
        self.open = still_open

    def _keep(self, event: dict) -> None:
        g = self.grid
        columns, rows = [i % g for i in event["cells"]], [i // g for i in event["cells"]]
        where = [min(columns) / g, min(rows) / g, (max(columns) + 1) / g, (max(rows) + 1) / g]
        self.parts.append((event["first"], event["last"], where, round(event["peak"], 1)))

    def finish(self) -> None:
        """Close what is still going on at the last frame. A part changing on the last frame is not kept."""
        if self.held is not None:
            self.freezes.append((self.held, len(self.whole) - 1))
        self.parts.sort(key=lambda p: p[0])


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
