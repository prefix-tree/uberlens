"""Stumbles and pauses in speech: repeats, restarts, fillers, sound the transcript has no word for, and gaps under music."""

from __future__ import annotations

import subprocess
from fractions import Fraction as F
from pathlib import Path

import pytest

from uberseek import Project
from uberseek.api import ApiError, Library, stumbles
from uberseek.ingest import signals, transcript

GAP, HUM = 0.4, 0.4  # quiet either side of the hum, and the hum itself: an "um" the transcript leaves out


def said(text: str, start: float = 0) -> list[tuple[F, F, str]]:
    """Words a third of a second long with a tenth of a second between them."""
    out, at = [], F(start)
    for word in text.split():
        out.append((at, at + F(3, 10), word))
        at += F(4, 10)
    return out


def found(text: str) -> list[tuple[str, str, list[float]]]:
    return [(f["kind"], f["text"], [float(t) for t in f["cut"]]) for f in stumbles.from_words(said(text))]


def test_a_word_said_twice_is_a_repeat_and_the_cut_keeps_the_last_try():
    assert found("the the company") == [("repeat", "the the", [0.0, 0.4])]
    assert found("I I I think so.") == [("repeat", "I I I", [0.0, 0.8])]  # one stumble, not two
    assert found("we had we had no money") == [("repeat", "we had we had", [0.0, 0.8])]


def test_a_phrase_begun_again_a_few_words_later_is_a_restart():
    assert found("We had no, we had nothing left.") == [("restart", "We had no, we had", [0.0, 1.2])]


def test_ordinary_speech_is_not_a_stumble():
    assert found("one of the best of the year") == []  # "of the" twice is how sentences are built
    assert found("the then mayor said so") == []  # "the" is not a broken-off "then"
    assert found("we had nothing left and nobody believed in us") == []


def test_a_restart_long_after_the_first_try_is_not_one():
    words = said("we had") + said("we had", start=10)
    assert stumbles.from_words(words) == []


def test_fillers_and_broken_off_words_are_found_and_a_filler_inside_a_repeat_is_part_of_it():
    assert found("So, um, the plan") == [("filler", "um,", [0.4, 0.7])]
    assert found("Uh. Right") == [("filler", "Uh.", [0.0, 0.3])]
    assert found("I, um, I think") == [("repeat", "I, um, I", [0.0, 0.8])]
    assert found("it was compa- company money") == [("cut-off", "compa- company", [0.8, 1.2])]
    assert found("we went to the mar market") == [("cut-off", "mar market", [1.6, 2.0])]


def test_sound_between_words_that_is_not_a_pause_is_reported():
    words = [(F(0), F(1), "so"), (F(2), F(3), "right")]
    pauses = [(F(1), F(13, 10)), (F(17, 10), F(2))]
    (sound,) = stumbles.unworded(words, pauses)
    assert (sound["kind"], sound["start"], sound["end"]) == ("sound", F(13, 10), F(17, 10))
    assert stumbles.unworded(words, [(F(1), F(2))]) == []  # the whole gap is a pause
    assert stumbles.unworded([(F(0), F(1), "so"), (F(9), F(10), "right")], []) == []  # too long a gap to guess at


def levels(*parts: tuple[float, float]) -> list[tuple[F, float]]:
    """A level every 20 ms: each part is (seconds, dB)."""
    out, at = [], F(0)
    for seconds, db in parts:
        for _ in range(round(seconds / 0.02)):
            out.append((at, db))
            at += F(1, 50)
    return out


def test_a_pause_is_judged_against_the_speech_around_it_not_one_threshold():
    clean = levels((2, -20), (0.5, -70), (2, -20))
    under_music = levels((2, -18), (0.5, -30), (2, -18))  # nothing here is quieter than -35 dB
    for heard in (clean, under_music):
        ((start, end),) = signals.quiet_stretches(heard)
        assert start == F(2) and end == F(5, 2)
    assert signals.quiet_stretches(levels((2, -18), (0.1, -30), (2, -18))) == []  # shorter than a quarter second


def test_a_long_stretch_of_music_between_lines_is_still_a_pause():
    heard = levels((3, -18), (20, -30), (3, -18))  # in the middle, music alone for longer than the window
    ((start, end),) = signals.quiet_stretches(heard)
    assert start == F(3) and end == F(23)
    assert signals.quiet_stretches(levels((10, -30))) == []  # music with no speech anywhere: nothing to tell apart


def _seconds(path: Path) -> float:
    done = subprocess.run(
        ["ffprobe", "-v", "error", "-show_entries", "format=duration", "-of", "csv=p=0", str(path)], capture_output=True, text=True
    )
    return float(done.stdout)


@pytest.fixture(scope="module")
def stumbling(tmp_path_factory) -> dict:
    """A voice saying "We had", a hum with no word, then "we had nothing left": clean, and under music."""
    filters = subprocess.run(["ffmpeg", "-hide_banner", "-filters"], capture_output=True, text=True).stdout
    if " flite " not in filters:
        pytest.skip("this FFmpeg has no speech synthesis (flite)")
    d = tmp_path_factory.mktemp("stumbles")
    run = ["ffmpeg", "-v", "error", "-y"]
    lines = []
    for i, text in enumerate(["We had", "we had nothing left"]):
        path = d / f"line{i}.wav"
        subprocess.run([*run, "-f", "lavfi", "-i", f"flite=text='{text}':voice=slt", "-ar", "16000", "-ac", "1", str(path)], check=True)
        lines.append(path)
    first, second = (_seconds(path) for path in lines)
    quiet = f"anullsrc=r=16000:cl=mono:d={GAP}"
    hum = f"sine=f=600:r=16000:d={HUM}"
    parts = ["anullsrc=r=16000:cl=mono:d=1", None, quiet, hum, quiet, None, "anullsrc=r=16000:cl=mono:d=1"]
    inputs, files = [], iter(lines)
    for part in parts:
        inputs += ["-i", str(next(files))] if part is None else ["-f", "lavfi", "-i", part]
    joined = "".join(f"[{i}]aformat=sample_rates=16000:channel_layouts=mono[a{i}];" for i in range(len(parts)))
    joined += "".join(f"[a{i}]" for i in range(len(parts))) + f"concat=n={len(parts)}:v=0:a=1[s]"
    voice = d / "voice.wav"
    subprocess.run([*run, *inputs, "-filter_complex", joined, "-map", "[s]", str(voice)], check=True)
    length = _seconds(voice)
    music = (
        f"sine=f=220:d={length}[x];sine=f=330:d={length}[y];sine=f=554:d={length}[z];anoisesrc=d={length}:c=pink:a=0.05[n];"
        "[x][y][z][n]amix=inputs=4:normalize=0,volume=0.3[m];[0][m]amix=inputs=2:normalize=0[s]"
    )
    picture = ["-f", "lavfi", "-i", f"color=c=gray:size=160x90:rate=10:duration={length}"]
    encode = ["-map", "1:v", "-map", "[s]", "-c:v", "libx264", "-c:a", "aac", "-shortest"]
    clean, mixed = d / "clean.mp4", d / "music.mp4"
    subprocess.run([*run, "-i", str(voice), *picture, "-filter_complex", "[0]anull[s]", *encode, str(clean)], check=True)
    subprocess.run([*run, "-i", str(voice), *picture, "-filter_complex", music, *encode, str(mixed)], check=True)
    hum_at = 1 + first + GAP
    return {"clean": clean, "music": mixed, "first": first, "second": second, "hum": (hum_at, hum_at + HUM)}


def _covered(spans: list[list[float]], t: float) -> bool:
    return any(a <= t <= b for a, b in spans)


def test_speech_pauses_are_found_under_music_where_silences_are_not(stumbling, tmp_path):
    library = Library(Project(tmp_path), [stumbling["clean"], stumbling["music"]])
    before, after = stumbling["hum"][0] - GAP / 2, stumbling["hum"][1] + GAP / 2  # the middle of each quiet gap
    hum = sum(stumbling["hum"]) / 2
    assert _covered(library.pauses("clean.mp4"), before)
    assert library.pauses("music.mp4") == []  # music fills every gap: nothing is quiet outright
    for video in ("clean.mp4", "music.mp4"):
        gaps = library.pauses(video, kind="speech")
        assert _covered(gaps, before) and _covered(gaps, after) and not _covered(gaps, hum), video
        assert all(isinstance(t, float) for gap in gaps for t in gap)
    with pytest.raises(ApiError, match="use 'silence', or 'speech'"):
        library.pauses("clean.mp4", kind="music")


def _seed(project: Project, video: Path, first: float, second: float, start: float) -> None:
    """A transcript as Whisper would write it: the words, and no word for the hum."""
    words = [["1.000", f"{1 + first / 2:.3f}", "We", 0.9], [f"{1 + first / 2:.3f}", f"{1 + first:.3f}", "had", 0.9]]
    step = second / 4
    words += [[f"{start + i * step:.3f}", f"{start + (i + 1) * step:.3f}", w, 0.9] for i, w in enumerate(["we", "had", "nothing", "left."])]
    source = project.open(video)
    data = {"kind": "estimated", "tool": "test", "model": project.transcript_model, "language": "en", "words": words}
    project.log.derived(source.hash, transcript.name(project.transcript_model), lambda: data)


@pytest.mark.parametrize("video", ["clean", "music"])
def test_stumbles_finds_the_repeat_and_the_hum_the_transcript_left_out(stumbling, tmp_path, video):
    project = Project(tmp_path)
    second_try = 1 + stumbling["first"] + 2 * GAP + HUM
    _seed(project, stumbling[video], stumbling["first"], stumbling["second"], second_try)
    library = Library(project, [stumbling[video]])
    name = stumbling[video].name
    found = library.stumbles(name)
    repeats = [f for f in found if f["kind"] == "repeat"]
    assert [(f["text"], f["cut"]) for f in repeats] == [("We had we had", [1.0, round(second_try, 3)])]
    sounds = [f for f in found if f["kind"] == "sound"]
    low, high = stumbling["hum"]
    assert len(sounds) == 1 and sounds[0]["start"] < (low + high) / 2 < sounds[0]["end"], found
    assert sounds[0]["start"] > low - 0.15 and sounds[0]["end"] < high + 0.15  # the hum, not the quiet around it
    assert library.stumbles(name, 0, 0.9) == []
