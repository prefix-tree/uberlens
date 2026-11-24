"""From a chosen span to a checked clip: selections are pinned to frames and looks, cuts are frame-exact, the file is checked."""

from __future__ import annotations

import shutil
import sqlite3
import subprocess
from fractions import Fraction

import pytest

from uberseek import Project, select
from uberseek.api import ApiError, Library
from uberseek.cli import main


def test_a_selection_snaps_to_frames_and_records_the_looks_it_rests_on(clips, tmp_path):
    project = Project(tmp_path)
    unseen = select.mark(project, clips["bframes"], "1.01", "2.02", reason="no look yet")
    # It starts on the frame showing at 1.01 and stops before the frame showing at 2.02: frames 30 to 59.
    assert (Fraction(unseen["start"]), Fraction(unseen["end"])) == (Fraction(1), Fraction(2))
    assert unseen["frames"] == 30 and unseen["edges_not_seen"] == ["in", "out"] and unseen["rests_on"] == []
    assert unseen["heard"] is False

    project.observe(clips["bframes"], 1, focus="boundary")
    project.observe(clips["bframes"], 2, focus="boundary")
    project.observe(clips["bframes"], 4, 5)  # elsewhere: not part of this selection
    seen = select.mark(project, clips["bframes"], 1, 2, reason="both edges looked at", replaces=unseen["id"])
    assert seen["edges_not_seen"] == [] and seen["rests_on"] == ["obs_000001", "obs_000002"]
    assert [s["id"] for s in select.selections(project)] == [seen["id"]]  # the corrected one replaces the first
    with pytest.raises(ValueError, match="would hold no frames"):
        select.mark(project, clips["bframes"], 3, 3)
    with pytest.raises(sqlite3.DatabaseError, match="append-only"):
        project.log.db.execute("DELETE FROM selections")


@pytest.mark.parametrize("name", ["bframes", "vfr", "offset", "rotated", "hevc"])
def test_a_clip_holds_exactly_the_frames_selected_however_the_file_is_built(clips, tmp_path, name):
    project = Project(tmp_path)
    start = project.open(clips[name]).index.start
    late = select.mark(project, clips[name], start + Fraction(7, 2), start + Fraction(21, 5))
    early = select.mark(project, clips[name], start + 1, start + 2)
    made = select.cut(project, [late["id"], early["id"]], "two-parts")  # played in the order given, not in source order
    clip = project.open(made["path"])
    assert len(clip.index.frames) == late["frames"] + early["frames"]
    assert [part["selection"] for part in made["segments"]] == [late["id"], early["id"]]
    assert Fraction(made["segments"][1]["clip"][0]) == Fraction(late["end"]) - Fraction(late["start"])
    checked = select.verify(project, "two-parts")
    assert checked["ok"], checked["problems"]
    assert checked["joins"] == [pytest.approx(float(Fraction(made["segments"][0]["clip"][1])), abs=0.001)]
    assert len(checked["warnings"]) == 4 and "without a look" in checked["warnings"][0]  # no edge was looked at


def test_verify_catches_a_clip_that_is_one_frame_off_or_a_frame_short(clips, tmp_path):
    project = Project(tmp_path)
    chosen = select.mark(project, clips["bframes"], 1, 2)
    made = select.cut(project, [chosen["id"]], "exact")
    assert select.verify(project, "exact")["ok"]

    def replace(*trim: str) -> dict:
        """Put another cut of the same source in the clip's place, as a faulty cutter would."""
        args = ["ffmpeg", "-v", "error", "-y", "-i", str(clips["bframes"]), *trim, "-an", "-c:v", "libx264", "-crf", "18", made["path"]]
        subprocess.run(args, check=True)
        return select.verify(project, "exact")

    shifted = replace("-vf", "trim=start_frame=31:end_frame=61,setpts=PTS-STARTPTS")  # the right length, one frame late
    assert not shifted["ok"] and any("is the frame after the one chosen" in problem for problem in shifted["problems"])
    short = replace("-vf", "trim=start_frame=30:end_frame=59,setpts=PTS-STARTPTS")
    assert not short["ok"] and any("it has 29 frames, and the selections hold 30" in problem for problem in short["problems"])


def test_a_source_that_changed_since_it_was_selected_is_not_cut(clips, tmp_path):
    copy = shutil.copy(clips["bframes"], tmp_path / "source.mp4")
    project = Project(tmp_path)
    chosen = select.mark(project, copy, 1, 2)
    shutil.copy(clips["hevc"], copy)
    with pytest.raises(ValueError, match="has changed since sel_000001 was selected"):
        select.cut(project, [chosen["id"]], "stale")


def test_a_clip_is_a_video_like_any_other(clips, tmp_path):
    library = Library(Project(tmp_path), [clips["bframes"]])
    library.observe("bframes.mp4", 1, focus="boundary")
    a = library.mark("bframes.mp4", 1, 2, reason="first")
    b = library.mark("bframes.mp4", 3.5, 4.5, reason="second")
    assert a["edges_not_seen"] == ["out"] and library.selections() == [a, b]
    made = library.clip([a["id"], b["id"]], "pair")
    assert made["clip"] == "pair.mp4" and made["duration"] == 2 and made["segments"][1]["clip"] == [1, 2]
    assert library.info("pair.mp4")["frames"] == 60  # no need to be given the clip: it was made here
    seen = library.observe("pair.mp4", 1, focus="boundary", purpose="does the join land cleanly?")
    assert "pair.mp4, 0:01.000, focus boundary" in seen["text"]
    assert library.project.reproduce(seen["id"]).exact
    assert library.verify("pair")["joins"] == [1.0]
    quiet = library.pauses("pair.mp4")  # the tone's silent second, 2 s to 3 s in the source, is not in either part
    assert quiet == []
    with pytest.raises(ApiError, match="no selection sel_000009"):
        library.clip(["sel_000009"], "none")
    with pytest.raises(ApiError, match="must be letters, digits"):
        library.clip([a["id"]], "../escape")
    with pytest.raises(ApiError, match="no clip named 'missing'"):
        library.verify("missing")


def test_the_command_line_builds_and_checks_a_clip(clips, tmp_path, capsys):
    run = ["--project", str(tmp_path)]
    assert main([*run, "mark", str(clips["bframes"]), "1", "2", "--reason", "the tone"]) == 0
    assert main([*run, "clip", "tone", "sel_000001"]) == 0
    assert main([*run, "verify", "tone"]) == 0
    assert main([*run, "export", "tone"]) == 0
    out = capsys.readouterr().out
    assert (
        '"reason": "the tone"' in out
        and '"ok": true' in out
        and "ffmpeg" in out
        and (tmp_path / ".uberseek" / "clips" / "tone.mp4").exists()
    )
    assert main([*run, "clip", "tone", "sel_000007"]) == 2
