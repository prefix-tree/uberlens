"""The questions, and how each answer is checked against what was actually shown."""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass
from fractions import Fraction
from pathlib import Path

from bench.reading import clips
from uberseek.timecode import clock


@dataclass(frozen=True)
class Question:
    kind: str
    name: str
    video: Path
    look: str  # the look to ask for, in words
    ask: str
    answer_type: type
    expected: Callable[[dict], object]  # from the log entry of the observation


def _times(record: dict) -> list[Fraction]:
    base = Fraction(record["delivered"]["time_base"])
    return [frame["pts"] * base for frame in record["delivered"]["frames"]]


def _first_at_or_after(record: dict, moment: float) -> int:
    return next(i for i, t in enumerate(_times(record), start=1) if t >= Fraction(str(moment)))


def _inside_pause(record: dict) -> tuple[int, int]:
    (a, b), *_ = record["delivered"]["sound"]["pauses"]
    inside = [i for i, t in enumerate(_times(record), start=1) if Fraction(a) < t < Fraction(b)]
    return inside[0], inside[-1]


def _at_mark(record: dict) -> int:
    mark = Fraction(record["recipe"]["mark"])
    return max(i for i, t in enumerate(_times(record), start=1) if t <= mark)


def questions(folder: Path) -> list[Question]:
    out: list[Question] = []

    # Reading the grid in time order: the square appears halfway between two shown frames.
    for appears in (1.5, 2.3, 2.9, 3.7):
        out.append(
            Question(
                "first frame", f"square at {appears}", clips.event(folder, appears, (6.1, 6.9)),
                "from 1 to 4 seconds, focus visual",
                "Which numbered frame is the first to show the red square? Give its number.",
                int, lambda r, t=appears: _first_at_or_after(r, t),
            )
        )  # fmt: skip

    # Reading the labels.
    for number in (3, 7, 11, 16):
        out.append(
            Question(
                "label", f"time on frame {number}", clips.event(folder, 1.5, (6.1, 6.9)),
                "from 2 to 5 seconds, focus visual",
                f"What time is printed on frame {number}? Give it exactly as printed, like 0:01.234.",
                str, lambda r, n=number: clock(_times(r)[n - 1]),
            )
        )  # fmt: skip

    # Comparing neighbours: one cut, halfway between two shown frames.
    for at in (1.7, 2.5, 3.1, 3.9):
        out.append(
            Question(
                "change", f"cut at {at}", clips.cut(folder, at),
                "from 1 to 4 seconds, focus visual",
                "The scene changes once. Give the numbers of the two consecutive frames it changes between, lower first.",
                tuple[int, int], lambda r, t=at: (_first_at_or_after(r, t) - 1, _first_at_or_after(r, t)),
            )
        )  # fmt: skip

    # Reading the sound strip against the frame ticks.
    for quiet in ((1.5, 2.3), (2.1, 3.3), (2.7, 3.5), (1.9, 2.5)):
        out.append(
            Question(
                "sound", f"silence {quiet[0]}-{quiet[1]}", clips.event(folder, 7.5, quiet),
                "from 1 to 4 seconds, focus delivery",
                "The strip under the frames shows the sound, with one silent stretch shaded. Which numbered frames have their "
                "tick inside the shaded stretch? Give the first and the last such frame number.",
                tuple[int, int], _inside_pause,
            )
        )  # fmt: skip

    # A boundary: which frame is at the instant asked about.
    for instant in (2.0, 3.5, 4.2, 5.1):
        out.append(
            Question(
                "boundary", f"instant {instant}", clips.event(folder, 1.5, (6.1, 6.9)),
                f"at {instant} seconds (start only, no end), focus boundary",
                "A vertical line on the sound strip marks the instant asked about. Which numbered frame's tick is at that line?",
                int, _at_mark,
            )
        )  # fmt: skip
    return out
