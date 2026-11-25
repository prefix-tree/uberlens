"""What real use asked for: where the picture changes or stops, looks that follow change, part of the frame, several videos at once."""

from __future__ import annotations

import pytest

from tests.conftest import make
from uberseek import Project
from uberseek.api import ApiError, Library
from uberseek.cli import main

H264 = ["-c:v", "libx264", "-bf", "2", "-g", "40", "-pix_fmt", "yuv420p"]


@pytest.fixture(scope="module")
def happening(tmp_path_factory):
    """Four seconds of a bar crossing a flat picture. A white box appears top right at 2 s; frame 90 is held for 12 more frames.

    The sound is silent for the first second, then a tone.
    """
    graph = (
        "color=c=0x224466:s=320x180:r=30:d=4[bg];color=c=0xddaa22:s=40x180:r=30:d=4[bar];color=c=white:s=80x45:r=30:d=4[box];"
        "[bg][bar]overlay=x='mod(t*120,280)'[a];[a][box]overlay=x=240:y=0:enable='gte(t,2)',loop=loop=12:size=1:start=90[v]"
    )
    sound = ["-f", "lavfi", "-i", "sine=frequency=440:duration=4.4", "-af", "volume=enable='lt(t,1)':volume=0"]
    path = tmp_path_factory.mktemp("change") / "happening.mp4"
    return make(path, *sound, "-filter_complex", graph, "-map", "[v]", "-map", "0:a", *H264, "-c:a", "aac")


def test_a_change_in_part_of_the_frame_is_found_where_cuts_find_nothing(happening, tmp_path):
    library = Library(Project(tmp_path), [happening])
    assert library.cuts("happening.mp4") == []
    found = library.events("happening.mp4")
    box = next(e for e in found if e["frame"] == 60)
    assert box["time"] == 2.0 and box["kind"] == "part" and box["area"] < 0.2
    assert box["where"][0] >= 0.66 and box["where"][3] <= 0.5  # the top right, usable as a region
    assert not [e for e in found if e["frame"] < 60 and e["frame"] != 70]  # the bar's steady motion is not an event
    whole = library.change("happening.mp4", 1.9, 2.1)
    assert max(part for _, _, part in whole) == box["amount"]


def test_a_held_frame_is_a_freeze_with_its_frame_numbers(happening, tmp_path):
    library = Library(Project(tmp_path), [happening])
    # The held frame is number 89: frames 90 to 101 repeat it.
    assert library.freezes("happening.mp4") == [{"start": 3.0, "end": 3.4, "first_frame": 90, "frames": 12}]
    assert library.freezes("happening.mp4", shortest=13) == []
    assert library.freezes("happening.mp4", 0, 2.9) == []


def test_a_look_with_focus_change_shows_the_frames_either_side_of_what_happens(happening, tmp_path):
    project = Project(tmp_path)
    even = project.observe(happening, 0, 4.4)
    seen = project.observe(happening, 0, 4.4, "change")
    at = [frame["pts"] * 30 // 15360 for frame in seen.record["delivered"]["frames"]]
    assert {59, 60} <= set(at)  # the frame before the box and the first frame with it
    assert {59, 60} - {frame["pts"] * 30 // 15360 for frame in even.record["delivered"]["frames"]}  # an even spread steps over it
    assert "where the picture changes most" in seen.text
    assert project.reproduce(seen.id).exact


def test_a_region_shows_part_of_the_frame_and_is_made_again_exactly(happening, tmp_path):
    project = Project(tmp_path)
    corner = project.observe(happening, 2.5, None, region=[0.75, 0, 1, 0.25])
    assert corner.record["recipe"]["frame_size"] == [80, 45] and "region 0.75,0 to 1,0.25" in corner.record["recipe"]["title"]
    assert "Only part of each frame is shown" in corner.text
    assert project.reproduce(corner.id).exact
    sheet = project.sheet(happening, [1.5, 2.5], region=[0.75, 0, 1, 0.25])
    before, after = (frame["pixels_sha256"] for frame in sheet.record["delivered"]["frames"])
    assert before != after  # the corner without the box, and with it
    with pytest.raises(ValueError, match="not inside the frame"):
        project.observe(happening, 1, region=[0.5, 0, 0.2, 1])


def test_several_videos_on_one_picture_and_a_join_between_two(happening, clips, tmp_path):
    project = Project(tmp_path)
    library = Library(project, [happening, clips["bframes"], clips["three_shots"]])
    seen = library.overview(["happening.mp4", "bframes.mp4", "three_shots.mp4"], per=3)
    assert "3 videos" in seen["text"] and "(bframes.mp4 · 2/3)" in seen["text"]
    join = library.seam("bframes.mp4", "three_shots.mp4", frames=2)
    assert "bframes.mp4 · last" in join["text"] and "three_shots.mp4 · first" in join["text"]
    assert all(project.reproduce(look["id"]).exact for look in (seen, join))
    assert library.coverage("bframes.mp4", 0, 5)["looked"] == []  # a picture of several videos is no look at any one span
    with pytest.raises(ApiError, match="at most 48 frames"):
        library.overview(["bframes.mp4"] * 17, per=3)


def test_sound_onsets_gaps_between_words_and_repeated_words(happening, tmp_path, monkeypatch):
    library = Library(Project(tmp_path), [happening])
    assert library.onsets("happening.mp4") == [pytest.approx(1.0, abs=0.05)]
    said = [
        ("I", 0.0, 0.2),
        ("think", 0.2, 0.5),
        ("we", 0.9, 1.0),
        ("should,", 1.0, 1.3),
        ("we", 1.6, 1.7),
        ("should", 1.7, 2.0),
        ("go.", 2.05, 2.3),
    ]
    monkeypatch.setattr(library, "words", lambda video, start, end: [{"start": a, "end": b, "text": text} for text, a, b in said])
    assert library.gaps("happening.mp4", 0, 3) == [[0.5, 0.9], [1.3, 1.6]]
    assert library.repeats("happening.mp4", 0, 3) == [{"text": "we should,", "first": [0.9, 1.3], "second": [1.6, 2.0]}]
    assert library.every(0, 1, 0.25) == [0.0, 0.25, 0.5, 0.75, 1.0]


def test_a_clip_keeps_the_size_of_a_source_whose_pixels_are_almost_square(tmp_path):
    odd = make(tmp_path / "odd.mp4", "-f", "lavfi", "-i", "testsrc2=size=854x480:rate=30:duration=2", "-vf", "setsar=1280/1281", *H264)
    project = Project(tmp_path)
    library = Library(project, [odd])
    assert library.info("odd.mp4")["width"] == 854
    made = library.clip([library.mark("odd.mp4", 0.5, 1.5)["id"]], "same-size")
    assert library.info(made["clip"])["width"] == 854 and library.verify("same-size")["problems"] == []


def test_named_arguments_work_either_way_and_a_clip_opens_by_its_name(clips, tmp_path, monkeypatch, capsys):
    monkeypatch.chdir(clips["bframes"].parent)
    run = ["--project", str(tmp_path)]
    assert main([*run, "mark", "bframes.mp4", "1", "2", "--reason", "with a flag"]) == 0
    assert main([*run, "mark", "bframes.mp4", "3", "4", "reason=with a name"]) == 0
    assert main([*run, "clip", "sel_000001", "either", "sel_000002"]) == 0  # the name can come anywhere
    assert main([*run, "observe", "either.mp4", "1", "focus=boundary"]) == 0
    assert "either.mp4, 0:01.000, focus boundary" in capsys.readouterr().out
    assert main([*run, "observe", "bframes.mp4", "2", "--region", "[0, 0.5, 1, 1]"]) == 0
    assert main([*run, "clip", "sel_000001"]) == 2  # no name
