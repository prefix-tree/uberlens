"""Change from frame to frame: flashes, held frames and parts of the picture that change while the rest holds."""

from __future__ import annotations

import pytest

from uberseek import Project
from uberseek.api import ApiError, Library
from uberseek.ingest import signals

FRAME = 1 / 30


@pytest.fixture(scope="module")
def library(clips, tmp_path_factory):
    names = ("flash_freeze", "strips", "three_shots", "bframes")
    return Library(Project(tmp_path_factory.mktemp("changes")), [clips[name] for name in names])


def test_one_pass_measures_every_frame_on_the_files_own_timeline(clips, backend):
    index = backend.frame_index(clips["flash_freeze"])
    made = signals.changes(clips["flash_freeze"])
    assert made["kind"] == "measured" and made["pts"] == [f.pts for f in index.frames]
    assert len(made["whole"]) == len(made["part"]) == len(index.frames) and made["whole"][0] == 0
    assert all(0 <= w <= p <= 100 for w, p in zip(made["whole"], made["part"], strict=True))


def test_a_single_flash_frame_is_found_and_a_cut_is_not_a_flash(library):
    ((start, end),) = library.flashes("flash_freeze.mp4")
    assert start == pytest.approx(1.5, abs=0.001) and end == pytest.approx(1.5 + FRAME, abs=0.001)
    assert library.flashes("three_shots.mp4") == [] and library.flashes("strips.mp4") == []
    assert library.flashes("flash_freeze.mp4", 2, 4) == []


def test_a_held_frame_is_found_and_moving_footage_is_not(library):
    ((start, end),) = library.freezes("flash_freeze.mp4")
    assert start == pytest.approx(80 * FRAME, abs=1.5 * FRAME) and end == pytest.approx(110 * FRAME, abs=1.5 * FRAME)
    assert library.freezes("bframes.mp4") == []  # a pattern that moves on every frame
    assert library.freezes("flash_freeze.mp4", 3, 3.2) == [[3.0, 3.2]]  # a hold is cut to the span asked about


def test_short_holds_are_left_out_unless_asked_for(library):
    assert library.freezes("strips.mp4") == [[0, 1], [pytest.approx(50 * FRAME, abs=0.001), 3]]  # before the strips, and after
    every = library.freezes("strips.mp4", shortest=0)
    between = every[1:-1]  # the ground held between one strip and the next
    assert len(every) == 7 and all(b - a == pytest.approx(4 * FRAME, abs=0.002) for a, b in between)


def test_each_strip_of_a_collage_is_a_change_of_one_part_where_cuts_see_nothing(library):
    found = library.part_changes("strips.mp4")
    assert library.cuts("strips.mp4") == [] and len(found) == 6
    for k, event in enumerate(found):
        assert event["start"] == pytest.approx((30 + 4 * k) * FRAME, abs=0.001)
        left, top, right, bottom = event["where"]
        assert (top, bottom) == (0, 1) and right - left <= 0.25  # a strip, to the nearest eighth
        assert left <= k / 6 and right >= (k + 1) / 6 - 1 / 8 and event["change"] > 30
    assert library.part_changes("three_shots.mp4") == []  # a cut changes the whole frame, not a part
    assert library.part_changes("flash_freeze.mp4") == [] and library.part_changes("bframes.mp4") == []


def test_the_measure_frame_by_frame_tells_a_cut_a_part_and_a_hold_apart(library):
    rows = library.change("strips.mp4", 0.9, 1.2)
    assert [t for t, _, _ in rows] == pytest.approx([n * FRAME for n in range(27, 37)], abs=0.001)
    by_time = {round(t / FRAME): (whole, part) for t, whole, part in rows}
    whole, part = by_time[30]
    assert part > 30 and whole < part / 3  # a strip: one part changed
    assert by_time[29] == (0, 0) and by_time[31] == (0, 0)  # held around it
    cut = next(row for row in library.change("three_shots.mp4", 2.4, 2.6) if row[0] == 2.5)
    assert cut[1] > 10 and cut[1] > cut[2] / 3  # a cut: the whole frame changed
    with pytest.raises(ApiError, match="at most 60 seconds"):
        library.change("strips.mp4", 0, 61)


def test_the_measure_is_made_once_and_kept(library):
    assert library.info("strips.mp4")["has_changes"]
    assert library.project.log.derived(library._source("strips.mp4").hash, "changes", lambda: pytest.fail("made again"))
