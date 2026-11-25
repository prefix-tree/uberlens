"""The library: a few operations on video that return plain values and combine."""

from __future__ import annotations

import os

import pytest

from uberseek import Project
from uberseek.api import ApiError, Library, search, spans

os.environ.setdefault("HF_HUB_DISABLE_XET", "1")


def test_span_arithmetic():
    assert spans.expand([5, 8], before=1, after=2) == [4, 10] and spans.expand([0.5, 2], before=3) == [0, 2]
    assert spans.merge([[5, 6], [1, 2], [1.5, 3], [6.2, 7]], gap=0.5) == [[1, 3], [5, 7]]
    assert spans.minus([0, 10], [[2, 3], [5, 12]]) == [[0, 2], [3, 5]]
    assert spans.minus([0, 10], []) == [[0, 10]] and spans.minus([2, 3], [[0, 10]]) == []


WORDS = [
    ["0.0", "0.3", "We", 1], ["0.3", "0.6", "almost", 1], ["0.6", "1.0", "failed.", 1],
    ["1.1", "1.4", "Money", 1], ["1.4", "1.7", "ran", 1], ["1.7", "2.0", "out", 1],
    ["3.0", "3.4", "Nobody", 1], ["3.4", "3.8", "believed", 1], ["3.8", "4.0", "us.", 1],
]  # fmt: skip


def test_the_transcript_is_cut_at_sentence_ends_and_where_the_speaker_stops():
    found = search.passages(WORDS)
    assert [p["text"] for p in found] == ["We almost failed.", "Money ran out", "Nobody believed us."]
    assert (found[1]["start"], found[1]["end"]) == (1.1, 2.0)  # ended by the one-second gap, not by a full stop


def test_find_ranks_passages_by_the_words_they_share_and_returns_nothing_for_a_paraphrase():
    found = search.passages(WORDS)
    best = search.rank(found, "who believed?", 5)
    assert [p["text"] for p in best] == ["Nobody believed us."] and best[0]["how"] == "words" and best[0]["score"] > 0
    assert search.rank(found, "the company went bankrupt", 5) == []  # it matches words, not meaning


@pytest.fixture(scope="module")
def spoken(tmp_path_factory, speech) -> Library:
    pytest.importorskip("faster_whisper")
    project = Project(tmp_path_factory.mktemp("library"), transcript_model="tiny")
    try:
        project.transcribe(speech)
    except Exception as error:
        pytest.skip(f"the Whisper model could not be loaded: {error}")
    return Library(project, [speech])


def test_find_on_a_video_returns_the_passage_and_respects_time_limits(spoken):
    (hit,) = spoken.find("speech.mp4", "money left")
    assert "money" in hit["text"].lower() and 1 < hit["start"] < hit["end"] < 7.5
    assert spoken.find("speech.mp4", "money left", before=hit["start"]) == []
    assert spoken.find("speech.mp4", "money left", after=hit["start"] - 0.1) == [hit]
    said = spoken.words("speech.mp4", hit["start"], hit["end"])
    assert " ".join(w["text"] for w in said) == hit["text"]


def test_what_cannot_be_done_is_said_plainly(spoken):
    with pytest.raises(ApiError, match="no video named 'other.mp4'. Available: speech.mp4"):
        spoken.info("other.mp4")
    with pytest.raises(ApiError, match="needs the picture index"):
        spoken.find("speech.mp4", like=[1, 2])
    with pytest.raises(ApiError, match="ends .* before it starts"):
        spoken.words("speech.mp4", 5, 2)


def test_measurements_come_back_as_plain_numbers(clips, tmp_path):
    library = Library(Project(tmp_path), [clips["bframes"], clips["three_shots"]])
    assert library.info("bframes.mp4") | {"has_cuts": False} == library.info("bframes.mp4")
    ((start, end),) = library.pauses("bframes.mp4")  # the tone is silent from 2 s to 3 s
    assert start == pytest.approx(2.0, abs=0.05) and end == pytest.approx(3.0, abs=0.05)
    assert library.pauses("bframes.mp4", 0, 1.5) == []
    assert library.cuts("three_shots.mp4") == [2.5, 4.5]
    assert library.shots("three_shots.mp4", 1, 5) == [[1, 2.5], [2.5, 4.5], [4.5, 5]]
    points = library.loudness("bframes.mp4", 0, 1)
    assert len(points) >= 5 and all(0 <= t <= 1 and level < 0 for t, level in points)


def test_coverage_says_what_was_looked_at_and_what_was_not(clips, tmp_path):
    library = Library(Project(tmp_path), [clips["bframes"]])
    assert library.coverage("bframes.mp4", 0, 5) == {"looked": [], "sheets": [], "never": [[0, 5]]}
    library.observe("bframes.mp4", 1, 2, purpose="first")
    library.observe("bframes.mp4", 3, 4.5, focus="motion", purpose="second")
    covered = library.coverage("bframes.mp4", 0, 5)
    assert [(look["start"], look["end"], look["id"]) for look in covered["looked"]] == [(1, 2, "obs_000001"), (3, 4.5, "obs_000002")]
    assert covered["never"] == [[0, 1], [2, 3], [4.5, 5]]
    assert covered["looked"][0]["gap"] < covered["looked"][1]["gap"]  # the one-second look is the closer one
    assert [look["purpose"] for look in library.observations("bframes.mp4", focus="motion")] == ["second"]
    assert [look["id"] for look in library.observations("bframes.mp4", end=2.5)] == ["obs_000001"]
    assert len(library.looks) == 2


def test_a_sheet_shows_the_frames_picked_and_covers_nothing_between_them(clips, tmp_path):
    library = Library(Project(tmp_path), [clips["bframes"]])
    seen = library.sheet("bframes.mp4", [4, 0.5, 2], labels=["late", "early", "middle"], purpose="which is sharpest?")
    assert "a sheet of 3 frames" in seen["text"] and "1: 0:04.000 (late); 2: 0:00.500 (early); 3: 0:02.000 (middle)" in seen["text"]
    assert "nothing between them was shown" in seen["text"]
    covered = library.coverage("bframes.mp4", 0, 5)
    assert covered["sheets"] == [{"id": "obs_000001", "times": [0.5, 2.0, 4.0]}]
    assert covered["looked"] == [] and covered["never"] == [[0, 5]]  # separate instants close no gap
    with pytest.raises(ApiError, match="at most 48 frames"):
        library.sheet("bframes.mp4", [i / 10 for i in range(49)])
    with pytest.raises(ApiError, match="2 labels were given for 3 times"):
        library.sheet("bframes.mp4", [1, 2, 3], labels=["a", "b"])
    with pytest.raises(ApiError, match="at least one time"):
        library.sheet("bframes.mp4", [])


def test_the_reference_is_written_from_the_operations_themselves(tmp_path):
    reference = Library(Project(tmp_path)).reference()
    assert all(f"\n{name}(" in "\n" + reference for name in Library.OPERATIONS)
    assert "find(video: str, query: str = " in reference and 'Returns: A list of {"start", "end", "text", "score", "how"}' in reference
