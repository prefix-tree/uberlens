"""An observation states what it delivered, is kept, and can be made again exactly."""

from __future__ import annotations

import shutil
import sqlite3
from fractions import Fraction

import pytest

from uberseek import Project
from uberseek.cli import main
from uberseek.observe.plan import MAX_SIDE


@pytest.fixture
def project(tmp_path) -> Project:
    return Project(tmp_path)


LOOKS = [
    ("bframes", "1", "4", "visual"),
    ("bframes", "2.5", None, "boundary"),
    ("bframes", "0", "5", "delivery"),
    ("bframes", "0", "5", "speech"),
    ("bframes", "3.1", None, "visual"),
    ("vfr", "0", "5", "motion"),
    ("offset", "2", "4.5", "visual"),
    ("trimmed", "0", "3", "visual"),
    ("rotated", "1", "2", "visual"),
    ("late_sound", "0.5", "2", "delivery"),
    ("hevc", "0", "5", "visual"),
]


@pytest.mark.parametrize(("name", "start", "end", "focus"), LOOKS)
def test_an_observation_is_made_again_exactly_from_its_log_entry(clips, tmp_path, name, start, end, focus):
    seen = Project(tmp_path).observe(clips[name], start, end, focus)
    again = Project(tmp_path).reproduce(seen.id)  # a new session: only the log and the file are shared
    assert again.exact, again.notes


def test_it_states_what_was_delivered(clips, project):
    seen = project.observe(clips["bframes"], 1, 4, purpose="is the bar moving?")
    record = seen.record
    base = Fraction(record["delivered"]["time_base"])
    times = [frame["pts"] * base for frame in record["delivered"]["frames"]]
    assert len(times) == 16 and times[0] == 1 and times[-1] == 4
    assert record["delivered"]["frames_in_span"] == 91
    assert record["delivered"]["gap_seconds"] == {"median": pytest.approx(0.2), "max": pytest.approx(0.2)}
    assert record["delivered"]["heard"] is False
    assert record["delivered"]["sound"]["pauses"]  # the silent second, measured
    assert record["request"]["purpose"] == "is the bar moving?"
    assert max(record["delivered"]["size"]) <= MAX_SIDE
    assert "16 frames" in seen.text and "not heard" in seen.text
    assert seen.image.startswith(b"\x89PNG")


def test_a_single_instant_gives_the_frame_showing_then(clips, project):
    seen = project.observe(clips["bframes"], "3.1")
    (frame,) = seen.record["delivered"]["frames"]
    assert frame["pts"] * Fraction(seen.record["delivered"]["time_base"]) == Fraction(31, 10)
    assert seen.record["recipe"]["level"] == "frame" and seen.record["delivered"]["sound"] is None


def test_a_boundary_shows_consecutive_frames_around_the_instant(clips, project):
    seen = project.observe(clips["bframes"], "2.5", focus="boundary")
    index = project.open(clips["bframes"]).index
    centre = index.position(Fraction(5, 2))
    assert seen.record["recipe"]["targets"] == [f.pts for f in index.frames[centre - 4 : centre + 4]]
    assert seen.record["delivered"]["sound"]["start"] == "3/2" and seen.record["delivered"]["sound"]["end"] == "7/2"


def test_a_changed_file_is_not_the_version_that_was_observed(clips, tmp_path):
    copy = shutil.copy(clips["bframes"], tmp_path / "clip.mp4")
    project = Project(tmp_path)
    seen = project.observe(copy, 1, 2)
    shutil.copy(clips["hevc"], copy)
    again = project.reproduce(seen.id)
    assert not again.exact and "not the version" in again.notes[0]


def test_a_past_observation_is_shown_again_without_the_file(clips, tmp_path):
    copy = shutil.copy(clips["bframes"], tmp_path / "clip.mp4")
    project = Project(tmp_path)
    seen = project.observe(copy, 1, 2)
    (tmp_path / "clip.mp4").unlink()
    shown = Project(tmp_path).show(seen.id)
    assert shown.image == seen.image and shown.text == seen.text


def test_the_log_cannot_be_rewritten(clips, project):
    project.observe(clips["bframes"], 1)
    for change in ("UPDATE observations SET focus = 'x'", "DELETE FROM observations"):
        with pytest.raises(sqlite3.DatabaseError, match="append-only"):
            project.log.db.execute(change)
    assert [r["id"] for r in project.log.observations()] == ["obs_000001"]


def test_the_command_line(clips, tmp_path, capsys):
    assert main(["--project", str(tmp_path), "observe", str(clips["bframes"]), "0:01", "0:03", "--focus", "delivery"]) == 0
    assert main(["--project", str(tmp_path), "reproduce"]) == 0
    assert "obs_000001: exact" in capsys.readouterr().out
    assert main(["--project", str(tmp_path), "observe", str(tmp_path / "missing.mp4"), "1"]) == 2
