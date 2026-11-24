"""The compositional tasks are checked code: each reference function gives the right A and B on clips built to order."""

from __future__ import annotations

import os

import pytest

from bench.compose import tasks
from uberseek import Project
from uberseek.api import Library

os.environ.setdefault("HF_HUB_DISABLE_XET", "1")


def test_structure_tasks_on_a_clip_with_known_shots(clips, tmp_path):
    lib = Library(Project(tmp_path), [clips["three_shots"]])  # shots: 0-2.5, 2.5-4.5, 4.5-6
    assert tasks.longest_shot_then_next(lib, "three_shots.mp4") == {"a": [0, 2.5], "b": [2.5, 4.5]}


@pytest.fixture(scope="module")
def spoken(tmp_path_factory, speech) -> Library:
    """The synthetic voice says: The company almost failed in the second year. We had no money left ..."""
    pytest.importorskip("faster_whisper")
    project = Project(tmp_path_factory.mktemp("compose"), transcript_model="tiny")
    try:
        project.transcribe(speech)
    except Exception as error:
        pytest.skip(f"the Whisper model could not be loaded: {error}")
    return Library(project, [speech])


def test_word_tasks_on_a_clip_with_known_words(spoken):
    said = {w["text"].strip(".,").lower(): [w["start"], w["end"]] for w in spoken.words("speech.mp4", 0, 9)}
    found = tasks.word_then_next_word(spoken, "speech.mp4", "company", "in")
    assert found["a"] == said["company"] and found["a"][1] <= found["b"][0] < said["money"][0]  # the first "in", not the last
    assert tasks.word_shot_then_next.__doc__ and tasks.longest_shot_then_count(spoken, "speech.mp4", "in")["b"] == 2


def test_time_tasks_on_a_clip_with_known_silence(spoken):
    found = tasks.longest_silence_then_words(spoken, "speech.mp4", 0, 5, 3)
    assert found["a"][0] == pytest.approx(0, abs=0.1) and 1.2 < found["a"][1] < 1.9  # the silence before the voice starts
    # The words that start once the silence is over. A word's printed time can sit a little inside the silence.
    assert " ".join(w.lower() for w in found["b"]) in "the company almost failed in the second year"
    after = tasks.word_then_longest_pause(spoken, "speech.mp4", "us", 5)
    assert after["b"][0] > after["a"][1] - 0.3  # the pause that follows the last word


def test_an_answer_is_scored_on_a_and_on_b_apart():
    span, text, number = (tasks.Task("t", "r", "v", "q", None, kind) for kind in ("span", "text", "number"))
    assert tasks.near([10.3, 99], [10.0, 12.0]) and not tasks.near([10.6, 12], [10.0, 12.0]) and not tasks.near(None, [1, 2])
    assert tasks.right_b(span, [5.4, 6], [5.0, 7.0]) and not tasks.right_b(span, [6.0, 7.0], [5.0, 7.0])
    assert tasks.right_b(text, "Great so those were all the details", ["Great,", "so", "those", "were", "all"])
    assert not tasks.right_b(text, "so those were all", ["Great,", "so", "those", "were", "all"])
    assert tasks.right_b(number, 5.0, 5) and not tasks.right_b(number, 4, 5) and not tasks.right_b(number, None, 5)
