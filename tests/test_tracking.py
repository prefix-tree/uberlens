"""Keeping track outside the context: the brief word for word, a note per look, and a working file that is always current."""

from __future__ import annotations

import sqlite3

import pytest

from uberseek import Project
from uberseek.api import ApiError, Library
from uberseek.cli import main
from uberseek.state import working

BRIEF = (
    "Make a clip of EXACTLY 15.0 seconds. Output: /workspace/output/repurpose.mp4, 1080x1920, no captions.\nDo not use the first minute."
)


def test_the_working_file_holds_the_brief_word_for_word_and_what_was_concluded(clips, tmp_path):
    library = Library(Project(tmp_path), [clips["bframes"]])
    file = tmp_path / ".uberseek" / working.NAME
    library.brief(BRIEF)
    first = library.observe("bframes.mp4", 1, 2, purpose="what moves?")
    library.observe("bframes.mp4", 3, focus="boundary")
    library.note(first["id"], "the bar sweeps right")
    library.mark("bframes.mp4", 1, 2, reason="the sweep")
    text = file.read_text()  # rewritten after every step, with no call to ask for it
    assert BRIEF in text and text == library.status()
    assert '- obs_000001 · bframes.mp4 · 0:01.000 to 0:02.000 · visual (asked: what moves?) · note: "the bar sweeps right"' in text
    assert "- obs_000002 · bframes.mp4 · 0:03.000 · boundary · no note" in text
    assert "- sel_000001 · bframes.mp4 · 0:01.000 to 0:02.000 · the sweep" in text
    assert text.index("The brief, word for word") < text.index("Selections") < text.index("What was concluded")
    assert library.observations("bframes.mp4")[0]["note"] == "the bar sweeps right"


def test_a_later_note_replaces_the_earlier_one_and_nothing_is_erased(clips, tmp_path):
    library = Library(Project(tmp_path), [clips["bframes"]])
    seen = library.observe("bframes.mp4", 1)
    library.note(seen["id"], "first reading")
    library.note(seen["id"], "second reading, after a closer look")
    assert library.project.log.notes() == {seen["id"]: "second reading, after a closer look"}
    with pytest.raises(sqlite3.DatabaseError, match="append-only"):
        library.project.log.db.execute("DELETE FROM notes")
    with pytest.raises(ApiError, match="no observation 'obs_000042'"):
        library.note("obs_000042", "nothing")


def test_a_long_task_keeps_the_brief_and_the_choices_and_counts_the_oldest_looks(clips, tmp_path):
    library = Library(Project(tmp_path), [clips["bframes"]])
    library.brief(BRIEF)
    library.mark("bframes.mp4", 1, 2, reason="kept")
    for i in range(40):
        library.observe("bframes.mp4", 1 + (i % 30) / 10, purpose="a look that was never written up, with a long reason " * 4)
    text = library.status()
    assert len(text) <= working.LIMIT + 100 and BRIEF in text and "sel_000001" in text
    assert f"Looks without a note (40; the last {working.RECENT} listed)" in text and text.count("- obs_") == working.RECENT


def test_videos_lists_what_can_be_used_and_what_was_made(clips, tmp_path):
    library = Library(Project(tmp_path), [clips["bframes"], clips["three_shots"]])
    chosen = library.mark("bframes.mp4", 1, 2)
    library.clip([chosen["id"]], "made")
    listed = {video["video"]: video for video in library.videos()}
    assert list(listed) == ["bframes.mp4", "three_shots.mp4", "made.mp4"]
    assert listed["made.mp4"]["duration"] == 1 and listed["three_shots.mp4"]["has_sound"] is False


def test_the_command_line_keeps_track(clips, tmp_path, capsys):
    run = ["--project", str(tmp_path)]
    assert main([*run, "brief", BRIEF]) == 0
    assert main([*run, "observe", str(clips["bframes"]), "1", "2"]) == 0
    assert main([*run, "note", "obs_000001", "the bar sweeps right"]) == 0
    capsys.readouterr()
    assert main([*run, "status"]) == 0
    out = capsys.readouterr().out
    assert BRIEF in out and 'note: "the bar sweeps right"' in out
    assert main([*run, "note", "obs_000009", "nothing"]) == 2
