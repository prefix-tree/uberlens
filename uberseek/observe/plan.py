"""How a span is shown. The caller gives the extent and the focus; this module sets the fidelity.

The ladder is a default, not a route: any span can be asked for at any time.
"""

from __future__ import annotations

import math
from dataclasses import dataclass
from fractions import Fraction

from uberseek.media.backend import FrameIndex
from uberseek.timecode import Seconds

FOCUSES = ("visual", "speech", "motion", "delivery", "boundary")

MAX_SIDE = 1568  # the longest side of any picture delivered
WAVEFORM_MAX = Fraction(60)  # longer spans show measured loudness, not the wave itself
SAMPLE_RATE = 16_000

# level: (the longest span it covers, frames at most, the long side of one frame)
LADDER = {
    "frame": (Fraction(0), 1, MAX_SIDE),
    "moment": (Fraction(8), 16, 384),
    "passage": (Fraction(60), 24, 320),
    "section": (Fraction(600), 24, 256),
    "map": (None, 32, 192),
}


@dataclass(frozen=True)
class Plan:
    level: str
    start: Seconds
    end: Seconds
    targets: tuple[int, ...]  # timestamps of the frames to show, in time order
    in_span: int  # how many frames the span holds
    tile_long: int
    sound: tuple[Seconds, Seconds] | None  # the stretch of sound to draw
    shots: int | None  # how many shots the span holds, when frames were chosen one per shot
    mark: Seconds | None  # an instant to mark on the sound strip


def _level(span: Seconds) -> str:
    return next(name for name, (limit, _, _) in LADDER.items() if limit is None or span <= limit)


def _spread(first: int, last: int, count: int) -> list[int]:
    """Up to `count` positions from first to last, both ends included, evenly apart."""
    size = last - first + 1
    if size <= count:
        return list(range(first, last + 1))
    return sorted({first + round(i * (size - 1) / (count - 1)) for i in range(count)})


def _slices(first: int, last: int, count: int) -> list[int]:
    """The middle position of each of up to `count` equal slices of first..last."""
    size = last - first + 1
    count = min(count, size)
    return [first + (2 * i + 1) * size // (2 * count) for i in range(count)]


def _shots(index: FrameIndex, first: int, last: int, cuts: list[int]) -> list[tuple[int, int]]:
    """The shots inside first..last, as position ranges. A cut is the first frame of a new shot."""
    starts = [first, *(p for pts in cuts if first < (p := index.position(index.time(pts))) <= last)]
    return list(zip(starts, [*(s - 1 for s in starts[1:]), last], strict=True))


MIN_SHOTS = 8  # with fewer shots than this, one frame per shot shows too little


def plan(
    index: FrameIndex,
    duration: Seconds,
    has_sound: bool,
    start: Seconds,
    end: Seconds,
    focus: str,
    cuts: list[int] | None = None,
) -> Plan:
    if focus not in FOCUSES:
        raise ValueError(f"focus must be one of {', '.join(FOCUSES)}")
    if end < start:
        raise ValueError("the span ends before it starts")
    limit = max(duration, index.end)
    start, end = min(max(start, index.start), limit), min(max(end, index.start), limit)
    span = end - start
    level = _level(span)
    _, most, tile_long = LADDER[level]
    first, last = index.position(start), index.position(end)
    sound, mark, shots = (start, end), None, None

    if focus == "boundary":
        # Consecutive frames around one instant, and two seconds of sound centred on it.
        mark = start + span / 2
        centre = index.position(mark)
        first, last = max(0, centre - 4), min(len(index.frames) - 1, centre + 3)
        positions = list(range(first, last + 1))
        sound, tile_long = (max(index.start, mark - 1), min(limit, mark + 1)), LADDER["moment"][2]
    elif focus == "motion":
        positions = _spread(first, last, LADDER["moment"][1])
        tile_long = LADDER["moment"][2]
    elif focus == "speech":
        positions = _spread(first, last, 4 if span else 1)
    elif focus == "delivery":
        positions = _spread(first, last, min(most, 12))
    elif level == "passage":
        positions = _spread(first, last, min(most, max(4, math.ceil(span / 2))))
    elif level in ("section", "map"):
        # One frame per shot where there are enough shots; otherwise one per equal slice of time.
        found = _shots(index, first, last, cuts or [])
        if level == "section" and len(found) >= MIN_SHOTS:
            shots = len(found)
            found = [found[i] for i in _spread(0, shots - 1, most)]
            positions = [(a + b) // 2 for a, b in found]
        else:
            positions = _slices(first, last, most)
    else:
        positions = _spread(first, last, most)

    wide = level in ("moment", "section", "map")
    drawn = has_sound and sound[1] > sound[0] and (focus in ("speech", "delivery", "boundary") or wide)
    return Plan(
        level=level,
        start=start,
        end=end,
        targets=tuple(index.frames[p].pts for p in positions),
        in_span=last - first + 1,
        tile_long=tile_long,
        sound=sound if drawn else None,
        shots=shots,
        mark=mark,
    )


def tile_size(display: tuple[int, int], long_side: int, count: int) -> tuple[tuple[int, int], int]:
    """The size of one frame and the number of columns, so the whole sheet fits MAX_SIDE. Never enlarges."""
    width, height = display
    columns = math.ceil(math.sqrt(count * height / width * 4 / 3)) if count > 1 else 1  # a 4:3 sheet
    rows = math.ceil(count / columns)
    scale = min(
        Fraction(long_side, max(width, height)),
        Fraction(MAX_SIDE, columns * width),
        Fraction(MAX_SIDE - 190 - rows * 40, rows * height),  # room for the title, the sound strip and the words
        1,
    )
    return (max(2, int(width * scale)), max(2, int(height * scale))), columns
