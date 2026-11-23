"""Draws what the model is shown: a sheet of numbered frames, and the sound as a strip under it.

A picture of sound is not listening. The strip lets the model see where sound and silence are; it does
not let it hear.
"""

from __future__ import annotations

import io
import math
from array import array
from fractions import Fraction

from PIL import Image, ImageDraw, ImageFont

from uberseek.media.backend import Frame
from uberseek.timecode import Seconds, clock

GAP = 4
STRIP_HEIGHT = 120
_INK, _PAPER, _DIM, _WAVE, _QUIET, _MARK = "#f2f2f2", "#161616", "#8a8a8a", "#7698fd", "#2a2a2a", "#ffb000"


def _font(size: int) -> ImageFont.FreeTypeFont:
    return ImageFont.load_default(size=size)


def _label(draw: ImageDraw.ImageDraw, xy: tuple[int, int], text: str, size: int) -> None:
    font = _font(size)
    box = draw.textbbox(xy, text, font=font)
    draw.rectangle((box[0] - 3, box[1] - 2, box[2] + 3, box[3] + 2), fill=_PAPER)
    draw.text(xy, text, font=font, fill=_INK)


def sheet(frames: list[Frame], times: list[Seconds], columns: int) -> Image.Image:
    """Frames in time order, left to right and top to bottom, each with its number and time."""
    width, height = frames[0].width, frames[0].height
    rows = -(-len(frames) // columns)
    image = Image.new("RGB", (columns * width + (columns - 1) * GAP, rows * height + (rows - 1) * GAP), _PAPER)
    draw = ImageDraw.Draw(image)
    size = max(11, min(20, width // 22))
    for i, (frame, time) in enumerate(zip(frames, times, strict=True)):
        x, y = (i % columns) * (width + GAP), (i // columns) * (height + GAP)
        image.paste(Image.frombytes("RGB", (width, height), frame.rgb), (x, y))
        _label(draw, (x + 6, y + 5), f"{i + 1}  {clock(time)}", size)
    return image


FLOOR_DB = 60


def _height(sample: int) -> float:
    """A sample's height on a decibel scale: silence is 0, full scale is 1, and -60 dB or less is flat.

    A linear wave makes quiet speech invisible; this keeps it readable and still shows louder as taller.
    """
    if sample == 0:
        return 0.0
    level = max(0.0, 1 + 20 * math.log10(abs(sample) / 32768) / FLOOR_DB)
    return math.copysign(level, sample)


def envelope(pcm: bytes, columns: int) -> list[tuple[float, float]]:
    """The lowest and highest sample in each column, from -1 to 1 on a decibel scale."""
    samples = array("h")
    samples.frombytes(pcm)
    out = []
    for c in range(columns):
        part = samples[c * len(samples) // columns : (c + 1) * len(samples) // columns]
        out.append((_height(min(part)), _height(max(part))) if part else (0.0, 0.0))
    return out


def loudness_envelope(points: list[list[str]], window: tuple[Seconds, Seconds], columns: int) -> list[tuple[float, float]]:
    """Measured loudness per column, drawn like a wave: -60 LUFS is flat and -10 LUFS is full height."""
    start, end = window
    best = [None] * columns
    for t, value in points:
        t = Fraction(t)
        if start <= t < end:
            c = int((t - start) / (end - start) * columns)
            best[c] = max(best[c] or -70.0, float(value))
    last, out = -70.0, []
    for value in best:
        last = last if value is None else value
        level = min(1.0, max(0.0, (last + 60) / 50))
        out.append((-level, level))
    return out


def strip(
    width: int,
    window: tuple[Seconds, Seconds],
    wave: list[tuple[float, float]],
    quiet: list[tuple[Seconds, Seconds]],
    ticks: list[Seconds],
    mark: Seconds | None,
    caption: str,
) -> Image.Image:
    """The sound over the window: the wave, silences shaded, a numbered tick for each frame shown."""
    image = Image.new("RGB", (width, STRIP_HEIGHT), _PAPER)
    draw = ImageDraw.Draw(image)
    start, end = window
    top, bottom = 22, STRIP_HEIGHT - 22
    middle, half = (top + bottom) // 2, (bottom - top) // 2

    def x(t: Seconds) -> int:
        return min(width - 1, max(0, int((t - start) / (end - start) * (width - 1))))

    for a, b in quiet:
        draw.rectangle((x(a), top, x(b), bottom), fill=_QUIET)
    for column, (low, high) in enumerate(wave):
        draw.line((column, middle - int(high * half), column, middle - int(low * half)), fill=_WAVE)
    for number, t in enumerate(ticks, start=1):
        if start <= t <= end:
            draw.line((x(t), top - 6, x(t), top), fill=_INK)
            draw.text((min(x(t) + 2, width - 16), 2), str(number), font=_font(11), fill=_DIM)
    if mark is not None:
        draw.line((x(mark), top - 6, x(mark), bottom + 4), fill=_MARK, width=2)
    draw.text((0, bottom + 5), f"{clock(start)}  {caption}", font=_font(12), fill=_DIM)
    right = clock(end)
    draw.text((width - draw.textlength(right, font=_font(12)), bottom + 5), right, font=_font(12), fill=_DIM)
    return image


def stack(*images: Image.Image) -> Image.Image:
    width = max(i.width for i in images)
    out = Image.new("RGB", (width, sum(i.height for i in images) + GAP * (len(images) - 1)), _PAPER)
    y = 0
    for image in images:
        out.paste(image, (0, y))
        y += image.height + GAP
    return out


def png(image: Image.Image) -> bytes:
    buffer = io.BytesIO()
    image.save(buffer, "PNG", compress_level=6)
    return buffer.getvalue()
