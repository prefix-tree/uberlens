"""Signals are on the file's own timeline, and cuts land on exact frames."""

from __future__ import annotations

from fractions import Fraction

import pytest

from uberseek import Project
from uberseek.ingest import signals, transcript


def test_cuts_are_the_first_frame_of_each_new_shot(clips, backend):
    index = backend.frame_index(clips["three_shots"])
    found = signals.cuts(clips["three_shots"])
    assert found["kind"] == "measured"
    assert [index.time(pts) for pts in found["pts"]] == [Fraction(5, 2), Fraction(9, 2)]


def test_a_measurement_lines_up_with_the_frames_when_the_file_does_not_start_at_zero(clips, backend):
    """offset.ts is bframes.mp4 with other timestamps: the silent second must move with the picture."""
    plain, moved = signals.silences(clips["bframes"])["spans"], signals.silences(clips["offset"])["spans"]
    shift = backend.frame_index(clips["offset"]).start - backend.frame_index(clips["bframes"]).start
    assert Fraction(moved[0][0]) - Fraction(plain[0][0]) == pytest.approx(shift, abs=0.03)
    assert Fraction(moved[0][0]) > backend.frame_index(clips["offset"]).start


def test_a_section_shows_one_frame_per_shot(clips, tmp_path):
    project = Project(tmp_path)
    seen = project.observe(clips["ten_shots"], 0, 80)
    index, record = project.open(clips["ten_shots"]).index, seen.record
    assert record["recipe"]["level"] == "section" and record["recipe"]["shots"] == 10
    shown = [int(index.time(pts) // 8) for pts in record["recipe"]["targets"]]
    assert shown == list(range(10))  # one frame from each eight-second shot, in order
    assert len(record["delivered"]["cuts"]) == 9
    assert "One frame per shot: the span holds 10 shots." in seen.text and "9 cuts in the span" in seen.text
    assert Project(tmp_path).reproduce(seen.id).exact


def test_too_few_shots_fall_back_to_equal_slices_of_time(clips, tmp_path):
    seen = Project(tmp_path).observe(clips["long"], 0, 300)  # one shot
    assert seen.record["recipe"]["level"] == "section" and seen.record["recipe"]["shots"] is None
    assert len(seen.record["recipe"]["targets"]) == 24 and "No cuts in the span." in seen.text


def test_a_map_covers_the_whole_source(clips, tmp_path):
    project = Project(tmp_path)
    seen = project.observe(clips["long"], 0, 720)
    record = seen.record
    base = Fraction(record["delivered"]["time_base"])
    times = [frame["pts"] * base for frame in record["delivered"]["frames"]]
    assert record["recipe"]["level"] == "map" and len(times) == 32
    assert times[0] < 720 / 32 and times[-1] > 720 - 720 / 32  # the middle of the first and of the last slice
    assert Project(tmp_path).reproduce(seen.id).exact


def test_cuts_already_made_are_shown_at_any_level(clips, tmp_path):
    project = Project(tmp_path)
    before = project.observe(clips["three_shots"], 2, 5)
    assert "cuts" not in before.record["delivered"] and before.record["recipe"]["cuts"] is False
    project.observe(clips["three_shots"], 0, 6, focus="visual")  # a moment: still no cuts made
    project._cuts(project.open(clips["three_shots"]))
    after = project.observe(clips["three_shots"], 2, 5)
    assert after.record["delivered"]["cuts"] == ["5/2", "9/2"] and "2 cuts in the span, at 0:02.500, 0:04.500." in after.text
    assert project.reproduce(before.id).exact and project.reproduce(after.id).exact


def test_words_are_given_to_the_frame_they_start_after():
    words = [["1.0", "1.2", "one", 1], ["1.5", "1.7", "two", 1], ["2.0", "2.4", "three", 1], ["3.0", "3.1", "four", 1]]
    times = [Fraction(1), Fraction(2), Fraction(5, 2)]
    assert transcript.by_frame(words, times, Fraction(3)) == ["one two", "three", "four"]
    assert transcript.by_frame(words, times, Fraction(14, 5)) == ["one two", "three", ""]
