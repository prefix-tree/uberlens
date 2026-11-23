"""The backend returns exactly the frame asked for, however the file is built."""

from __future__ import annotations

import array
import re
import subprocess
from fractions import Fraction

import pytest

from uberseek.media import Frame, MediaError

SIZE = (160, 90)
CLIPS = ["bframes", "vfr", "hevc", "vp9", "offset", "trimmed", "rotated"]


def play_through(path, size) -> list[Frame]:
    """Ground truth: decode the whole file from its first frame, with no seeking."""
    width, height = size
    done = subprocess.run(
        ["ffmpeg", "-v", "info", "-nostats", "-copyts", "-i", str(path), "-map", "0:v:0", "-an",
         "-vf", f"showinfo=checksum=0,scale={width}:{height}:flags=bicubic+accurate_rnd+full_chroma_int+bitexact,setsar=1",
         "-fps_mode", "passthrough", "-f", "rawvideo", "-pix_fmt", "rgb24", "pipe:1"],
        capture_output=True, check=True,
    )  # fmt: skip
    stamps = [int(m) for m in re.findall(rb"\] n:\s*\d+ pts:\s*(-?\d+)", done.stderr)]
    step = width * height * 3
    return [Frame(pts, width, height, done.stdout[i * step : (i + 1) * step]) for i, pts in enumerate(stamps)]


@pytest.mark.parametrize("name", CLIPS)
def test_the_index_lists_exactly_the_frames_that_play(clips, backend, name):
    index = backend.frame_index(clips[name])
    size = SIZE[::-1] if name == "rotated" else SIZE
    assert [f.pts for f in index.frames] == [f.pts for f in play_through(clips[name], size)]


@pytest.mark.parametrize("name", CLIPS)
def test_every_frame_fetched_alone_equals_the_frame_played_through(clips, backend, name):
    path = clips[name]
    size = SIZE[::-1] if name == "rotated" else SIZE
    index = backend.frame_index(path)
    truth = {f.pts: f.pixel_hash for f in play_through(path, size)}
    for ref in index.frames:  # one seek and one decode per frame, the hardest case
        (frame,) = backend.frames(path, index, [ref.pts], size)
        assert frame.pixel_hash == truth[ref.pts], f"{name}: frame at pts {ref.pts}"


def test_frames_fetched_together_come_back_in_the_order_asked(clips, backend):
    index = backend.frame_index(clips["bframes"])
    truth = {f.pts: f.pixel_hash for f in play_through(clips["bframes"], SIZE)}
    asked = [index.frames[i].pts for i in (120, 3, 77, 3, 41)]
    got = backend.frames(clips["bframes"], index, asked, SIZE)
    assert [f.pts for f in got] == asked
    assert [f.pixel_hash for f in got] == [truth[p] for p in asked]


def test_a_timestamp_that_is_not_a_frame_is_refused(clips, backend):
    index = backend.frame_index(clips["bframes"])
    with pytest.raises(MediaError, match="no frame with pts"):
        backend.frames(clips["bframes"], index, [index.frames[5].pts + 1], SIZE)


def test_the_same_picture_whatever_the_container(clips, backend):
    """The .ts file is a copy of the .mp4 stream with other timestamps: frame n must look the same."""
    a, b = backend.frame_index(clips["bframes"]), backend.frame_index(clips["offset"])
    assert b.start > 1 and a.start == 0
    for n in (0, 59, 149):
        (x,) = backend.frames(clips["bframes"], a, [a.frames[n].pts], SIZE)
        (y,) = backend.frames(clips["offset"], b, [b.frames[n].pts], SIZE)
        assert x.pixel_hash == y.pixel_hash


def test_probe_reports_the_picture_as_displayed(clips, backend):
    upright, sideways = backend.probe(clips["bframes"]).video, backend.probe(clips["rotated"]).video
    assert (upright.width, upright.height, upright.rotation) == (320, 180, 0)
    assert (sideways.width, sideways.height) == (180, 320) and sideways.rotation in (90, 270)


def loud(pcm: bytes) -> list[bool]:
    """For each tenth of a second at 16 kHz: is there sound?"""
    samples = array.array("h", pcm)
    return [max(map(abs, samples[i : i + 1600]), default=0) > 500 for i in range(0, len(samples), 1600)]


def test_sound_is_cut_where_asked_and_is_the_same_every_time(clips, backend):
    path = clips["bframes"]  # a tone, silent from 2 s to 3 s
    pcm = backend.audio(path, Fraction(3, 2), Fraction(2), 16_000)
    assert len(pcm) == 2 * 16_000 * 2
    heard = loud(pcm)
    assert all(heard[:4]) and not any(heard[6:14]) and all(heard[16:])
    assert pcm == backend.audio(path, Fraction(3, 2), Fraction(2), 16_000)


def test_sound_that_starts_late_is_placed_where_it_belongs(clips, backend):
    heard = loud(backend.audio(clips["late_sound"], Fraction(0), Fraction(5), 16_000))
    assert not any(heard[:9]) and all(heard[11:39]) and not any(heard[41:])


def test_a_frame_the_index_lists_but_the_file_lacks_fails_loudly(clips, backend):
    from dataclasses import replace

    from uberseek.media import FrameRef

    index = backend.frame_index(clips["bframes"])
    ghost = index.frames[5].pts + 1
    wrong = replace(index, frames=tuple(sorted([*index.frames, FrameRef(ghost, False)], key=lambda f: f.pts)))
    with pytest.raises(MediaError, match="indexed but did not decode"):
        backend.frames(clips["bframes"], wrong, [index.frames[5].pts, ghost], SIZE)
