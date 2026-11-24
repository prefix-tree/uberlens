"""The tasks, and the reference functions that compute their answers.

Each reference returns {"a": ..., "b": ...}. A is always a span. B is a span, a short text or a number.
"""

from __future__ import annotations

import re
from collections.abc import Callable
from dataclasses import dataclass

from uberseek.api import Library

TOLERANCE = 0.5  # seconds


def _plain(text: str) -> str:
    return re.sub(r"[^a-z0-9]", "", text.lower())


def _said(lib: Library, video: str, word: str) -> list[list[float]]:
    """Every time a word is said, as spans. The exact word: 'spacewalk' is not 'spacewalks'."""
    return [[w["start"], w["end"]] for w in lib.words(video, 0, lib.info(video)["duration"]) if _plain(w["text"]) == word]


def _longest(spans: list[list[float]]) -> list[float]:
    return max(spans, key=lambda s: s[1] - s[0])


# Related in time


def word_then_longest_pause(lib: Library, video: str, word: str, within: float) -> dict:
    """A: the first time `word` is said. B: the longest pause in the `within` seconds after it."""
    a = _said(lib, video, word)[0]
    return {"a": a, "b": _longest(lib.pauses(video, a[1], a[1] + within))}


def longest_silence_then_words(lib: Library, video: str, start: float, end: float, count: int) -> dict:
    """A: the longest silence between `start` and `end`. B: the first `count` words said after it."""
    a = _longest(lib.pauses(video, start, end))
    return {"a": a, "b": " ".join(w["text"] for w in lib.words(video, a[1], a[1] + 30) if w["start"] >= a[1])[:400].split()[:count]}


# Related by structure


def word_shot_then_next(lib: Library, video: str, word: str) -> dict:
    """A: the shot in which `word` is first said. B: the shot right after it."""
    at, shots = _said(lib, video, word)[0][0], lib.shots(video)
    i = next(k for k, shot in enumerate(shots) if shot[0] <= at < shot[1])
    return {"a": shots[i], "b": shots[i + 1]}


def longest_shot_then_next(lib: Library, video: str) -> dict:
    """A: the longest shot. B: the shot right after it."""
    shots = lib.shots(video)
    i = shots.index(_longest(shots))
    return {"a": shots[i], "b": shots[i + 1]}


# Related by words


def word_then_next_word(lib: Library, video: str, first: str, then: str) -> dict:
    """A: the first time `first` is said. B: the next time `then` is said after that."""
    a = _said(lib, video, first)[0]
    return {"a": a, "b": next(span for span in _said(lib, video, then) if span[0] >= a[1])}


def longest_shot_then_count(lib: Library, video: str, word: str) -> dict:
    """A: the longest shot. B: how many times `word` is said during it."""
    a = _longest(lib.shots(video))
    return {"a": a, "b": sum(a[0] <= span[0] < a[1] for span in _said(lib, video, word))}


@dataclass(frozen=True)
class Task:
    name: str
    relation: str
    video: str
    question: str
    reference: Callable[[Library], dict]
    b: str  # what B is: "span", "text" or "number"


TASKS = [
    Task(
        "pause after Artemis", "time", "interview",
        "A: the first time the word 'Artemis' is said. B: the longest pause in the 30 seconds after that word ends. "
        "Give A as the span of the word and B as the span of the pause.",
        lambda lib: word_then_longest_pause(lib, "interview.mp4", "artemis", 30), "span",
    ),
    Task(
        "words after the longest silence", "time", "briefing",
        "A: the longest silence between 300 and 900 seconds. B: the first five words said after it ends. "
        "Give A as the span of the silence and B as those five words.",
        lambda lib: longest_silence_then_words(lib, "briefing.mp4", 300, 900, 5), "text",
    ),
    Task(
        "shot after the nitrogen shot", "structure", "explainer",
        "A: the shot during which the word 'nitrogen' is said. B: the shot right after it. Give both as spans.",
        lambda lib: word_shot_then_next(lib, "explainer.mp4", "nitrogen"), "span",
    ),
    Task(
        "shot after the longest shot", "structure", "reel",
        "A: the longest shot in the video. B: the shot right after it. Give both as spans.",
        lambda lib: longest_shot_then_next(lib, "reel.mp4"), "span",
    ),
    Task(
        "robotic after crane", "words", "explainer",
        "A: the first time the word 'crane' is said. B: the next time the word 'robotic' is said after that. "
        "Give both as the spans of those words.",
        lambda lib: word_then_next_word(lib, "explainer.mp4", "crane", "robotic"), "span",
    ),
    Task(
        "spacewalk count in the longest shot", "words and structure", "briefing",
        "A: the longest shot in the video. B: how many times the exact word 'spacewalk' (not 'spacewalks') is said "
        "during that shot. Give A as a span and B as a number.",
        lambda lib: longest_shot_then_count(lib, "briefing.mp4", "spacewalk"), "number",
    ),
]  # fmt: skip


def near(found: list[float] | None, truth: list[float]) -> bool:
    """A span is right when its start is within the tolerance of the true start."""
    return bool(found) and abs(found[0] - truth[0]) <= TOLERANCE


def right_b(task: Task, found, truth) -> bool:
    if task.b == "span":
        return near(found, truth)
    if task.b == "number":
        return found is not None and int(found) == truth
    return [_plain(w) for w in str(found or "").split()][: len(truth)] == [_plain(w) for w in truth]
