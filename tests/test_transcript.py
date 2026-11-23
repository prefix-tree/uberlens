"""The transcript puts words on the timeline, and `observe` shows them under the frames."""

from __future__ import annotations

import os
from fractions import Fraction

import pytest

os.environ.setdefault("HF_HUB_DISABLE_XET", "1")
pytest.importorskip("faster_whisper")

from uberseek import Project  # noqa: E402


@pytest.fixture(scope="module")
def project(tmp_path_factory, speech) -> Project:
    project = Project(tmp_path_factory.mktemp("spoken"), transcript_model="tiny")
    try:
        project.transcribe(speech)
    except Exception as error:  # the model is downloaded on first use
        pytest.skip(f"the Whisper model could not be loaded: {error}")
    return project


def test_words_are_timed_on_the_files_own_clock(project, speech):
    made = project.transcribe(speech)
    words = [w[2].strip(".,").lower() for w in made["words"]]
    assert made["kind"] == "estimated" and made["model"] == "tiny"
    assert {"company", "failed", "money", "nobody"} <= set(words)
    first = Fraction(made["words"][0][0])
    assert 1.2 < first < 1.9  # the voice starts at 1.5 s


def test_a_look_shows_the_words_under_the_frames(project, speech):
    seen = project.observe(speech, 1, 7)
    by_frame = seen.record["delivered"]["words"]["by_frame"]
    assert len(by_frame) == 16 and "words" in seen.record["delivered"]["drawn"]
    assert "company" in " ".join(by_frame).lower()
    assert "an estimate, a word can be wrong" in seen.text
    assert Project(project.log.root.parent, transcript_model="tiny").reproduce(seen.id).exact


def test_a_look_made_before_the_transcript_has_no_words(tmp_path, speech):
    seen = Project(tmp_path).observe(speech, 1, 7)
    assert "words" not in seen.record["delivered"] and seen.record["recipe"]["words"] is None
