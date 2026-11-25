"""The lab's pieces that can be checked without a model or a download."""

from __future__ import annotations

import http.server
import subprocess
import threading
from functools import partial
from pathlib import Path

import pytest

np = pytest.importorskip("numpy")

from uberseek.lab import beats, fetch, loudness, sounds  # noqa: E402

RATE = 44100


def clicks(bpm: float, first: float, seconds: float, hat: bool = False):
    """A low thud on each beat from `first`; with `hat`, a brighter tick half a beat after each."""
    out = np.zeros(int(seconds * RATE))
    rng = np.random.default_rng(3)
    for at in np.arange(first, seconds - 0.3, 60 / bpm):
        t = np.arange(int(0.2 * RATE)) / RATE
        start = int(at * RATE)
        out[start : start + len(t)] += np.sin(2 * np.pi * 60 * t) * np.exp(-t / 0.06)
        if hat:
            tick = np.diff(rng.uniform(-0.5, 0.5, int(0.05 * RATE)), prepend=0) * np.exp(-np.arange(int(0.05 * RATE)) / (0.012 * RATE))
            start = int((at + 30 / bpm) * RATE)
            out[start : start + len(tick)] += 0.6 * tick[: len(out) - start]
    return out


@pytest.mark.parametrize(("bpm", "first"), [(120, 0.25), (96, 0.5), (150, 0.1), (72, 0.4)])
def test_beats_land_on_the_clicks(bpm, first):
    found = beats.detect(clicks(bpm, first, 12), RATE)
    assert abs(found["tempo"] - bpm) < bpm * 0.02
    period = 60 / bpm
    for beat in found["beats"]:
        nearest = first + round((beat - first) / period) * period
        assert abs(beat - nearest) < 0.03
    assert len(found["beats"]) >= (12 - 0.3 - first) / period - 2


def test_beats_follow_the_kick_not_the_hat_and_stop_with_the_music():
    sound = np.concatenate([clicks(120, 0.25, 8.5, hat=True), np.zeros(RATE)])
    found = beats.detect(sound, RATE)
    assert abs(found["tempo"] - 120) < 3
    for i, beat in enumerate(found["beats"]):
        assert abs(beat - (0.25 + i * 0.5)) < 0.03
    assert found["beats"][-1] < 8.5


def test_beats_of_silence_and_a_grid():
    assert beats.detect(np.zeros(RATE * 4), RATE)["beats"] == []
    assert beats.grid(120, 0.3, 2.4) == {"tempo": 120, "beats": [0.3, 0.8, 1.3, 1.8, 2.3]}
    with pytest.raises(ValueError):
        beats.grid(0, 0, 10)


class _Ranges(http.server.SimpleHTTPRequestHandler):
    """A file server that answers byte ranges, as a media server does."""

    def log_message(self, *args):
        pass

    def send_head(self):
        path = Path(self.translate_path(self.path))
        if not path.is_file():
            self.send_error(404)
            return None
        size = path.stat().st_size
        first, last = 0, size - 1
        asked = self.headers.get("Range")
        if asked:
            a, _, b = asked.removeprefix("bytes=").partition("-")
            first, last = int(a), min(int(b) if b else size - 1, size - 1)
        self.send_response(206 if asked else 200)
        self.send_header("Content-Length", str(last - first + 1))
        self.send_header("Accept-Ranges", "bytes")
        self.end_headers()
        handle = path.open("rb")
        handle.seek(first)
        self._left = last - first + 1
        return handle

    def copyfile(self, source, out):
        out.write(source.read(self._left))


@pytest.fixture(scope="module")
def served(tmp_path_factory):
    """A 12-second QuickTime file with its index at the front, behind a local server."""
    folder = tmp_path_factory.mktemp("served")
    subprocess.run(
        ["ffmpeg", "-v", "error", "-y", "-f", "lavfi", "-i", "testsrc2=size=320x180:rate=30:duration=12"]
        + ["-f", "lavfi", "-i", "sine=frequency=440:duration=12", "-c:v", "libx264", "-g", "15", "-pix_fmt", "yuv420p"]
        + ["-c:a", "pcm_s16le", "-movflags", "+faststart", str(folder / "long.mov")],
        check=True,
    )
    server = http.server.ThreadingHTTPServer(("127.0.0.1", 0), partial(_Ranges, directory=str(folder)))
    threading.Thread(target=server.serve_forever, daemon=True).start()
    yield folder / "long.mov", f"http://127.0.0.1:{server.server_address[1]}/long.mov"
    server.shutdown()


def test_span_range_is_inside_the_file_and_smaller_than_it(served):
    path, _url = served
    data = path.read_bytes()
    head = data[: fetch.index_size(data[:65536])]
    lo, hi = fetch.span_range(head, 4, 7)
    assert len(head) <= lo < hi <= len(data)
    assert hi - lo < (len(data) - len(head)) * 0.6
    with pytest.raises(fetch.FetchError):
        fetch.span_range(head, 100, 200)


def test_fetch_span_brings_only_those_seconds_and_they_play(served, tmp_path, monkeypatch):
    path, url = served
    for name in ("http_proxy", "HTTP_PROXY", "https_proxy", "HTTPS_PROXY", "all_proxy", "ALL_PROXY"):
        monkeypatch.delenv(name, raising=False)
    out = fetch.fetch_span(url, 4, 7, tmp_path / "part.mov")
    probe = subprocess.run(
        ["ffprobe", "-v", "error", "-count_frames", "-select_streams", "v:0", "-show_entries", "stream=nb_read_frames", "-of", "csv=p=0"]
        + [str(out)],
        capture_output=True,
        text=True,
        check=True,
    )
    assert abs(int(probe.stdout.strip().strip(",")) - 90) <= 1
    assert not (tmp_path / "part.sparse.mov").exists()


def test_a_file_with_its_index_at_the_end_is_refused(tmp_path):
    late = tmp_path / "late.mov"
    subprocess.run(
        ["ffmpeg", "-v", "error", "-y", "-f", "lavfi", "-i", "testsrc2=size=160x90:rate=30:duration=2", "-c:v", "libx264", str(late)],
        check=True,
    )
    with pytest.raises(fetch.FetchError):
        fetch.index_size(late.read_bytes()[:65536])


def test_loudness_of_a_tone_and_of_silence(tmp_path):
    tone, quiet = tmp_path / "tone.wav", tmp_path / "quiet.wav"
    subprocess.run(
        ["ffmpeg", "-v", "error", "-y", "-f", "lavfi", "-i", "sine=frequency=1000:duration=4", "-af", "volume=0.5", str(tone)], check=True
    )
    subprocess.run(["ffmpeg", "-v", "error", "-y", "-f", "lavfi", "-i", "anullsrc=duration=4", str(quiet)], check=True)
    loud = loudness.measure(tone)
    assert -30 < loud["lufs"] < -5
    assert loud["true_peak"] <= 0
    assert loudness.measure(quiet)["lufs"] is None


def test_typing_is_six_presses_under_full_scale():
    click = np.sin(2 * np.pi * 2000 * np.arange(200) / sounds.RATE) * np.exp(-np.arange(200) / 40)
    burst = sounds.typing([click.astype(np.float32)])
    assert len(burst) == sounds.RATE // 2
    assert 0.6 < np.abs(burst).max() < 0.65
    loud = np.abs(burst) > 0.2
    starts = np.flatnonzero(loud & ~np.roll(loud, 1))
    # Six bursts: a new one starts wherever the sound comes back after 20 ms of quiet.
    assert 1 + int((np.diff(starts) > 0.02 * sounds.RATE).sum()) == 6
