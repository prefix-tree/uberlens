"""The beats of a piece of music: where they fall, and the tempo.

An onset envelope from the spectral flux, the tempo from its autocorrelation, and the beats by dynamic programming
that rewards beats on onsets one period apart (Ellis, "Beat Tracking by Dynamic Programming", 2007). Ported from
UberScene's detector (`packages/render/src/beats.ts`), which `uberscene add` runs.

    python -m uberseek.lab.beats song.mp3

What it was tested on: synthetic click tracks from 72 to 180 BPM, and one synthesized groove; not recorded music.
A fast song may come out at half its tempo, every other beat.
"""

from __future__ import annotations

import subprocess
import sys

import numpy as np

FRAME = 1024
HOP = 512
MIN_BPM, MAX_BPM, PREFER_BPM = 60, 200, 120
# How much a beat off the period costs: higher keeps the beats steadier.
TIGHTNESS = 100
# Below this, an onset is a kick or a bass note: what a listener taps a foot to.
LOW_HZ = 200


def onset_envelope(samples: np.ndarray, rate: int) -> np.ndarray:
    """How much louder each frequency got since the last frame, summed, per hop; 0 to 1.

    The low end counts once more on its own, as much as all the rest: a hat between the beats is bright and wide,
    and without this it can outweigh the kick and pull the beats half a period off.
    """
    count = max(0, (len(samples) - FRAME) // HOP + 1)
    if count < 2:
        return np.zeros(count)
    index = np.arange(FRAME)[None, :] + HOP * np.arange(count)[:, None]
    spectrum = np.abs(np.fft.rfft(samples[index] * np.hanning(FRAME), axis=1))[:, : FRAME // 2]
    rise = np.maximum(0, np.diff(np.log1p(1000 * spectrum), axis=0, prepend=np.zeros((1, FRAME // 2))))
    rise[0] = 0
    low_bins = max(2, int(np.ceil(LOW_HZ * FRAME / rate)))
    everything, low = rise.sum(axis=1), rise[:, :low_bins].sum(axis=1)
    flux = everything / (everything.max() or 1) + low / (low.max() or 1)
    # Take away the local mean (about half a second), so a loud passage does not count as onsets.
    span = 21
    padded = np.pad(flux, span, mode="edge")
    mean = np.convolve(padded, np.ones(2 * span + 1) / (2 * span + 1), mode="valid")
    out = np.maximum(0, flux - mean)
    return out / out.max() if out.max() > 0 else out


def _smooth(x: np.ndarray, sigma: float) -> np.ndarray:
    radius = int(np.ceil(sigma * 3))
    kernel = np.exp(-0.5 * (np.arange(-radius, radius + 1) / sigma) ** 2)
    return np.convolve(x, kernel / kernel.sum(), mode="same")


def tempo_period(onset: np.ndarray, hops_per_second: float) -> float:
    """The beat period in hops: the lag where the envelope best matches itself, leaning toward PREFER_BPM."""
    # Smoothed first, so a period that falls between two whole hops still makes one broad peak.
    onset = _smooth(onset, 2)
    shortest = max(1, int(60 / MAX_BPM * hops_per_second))
    longest = min(len(onset) - 1, int(np.ceil(60 / MIN_BPM * hops_per_second)))
    top = min(len(onset) - 1, 2 * longest + 1)
    match = np.zeros(top + 2)
    for lag in range(max(1, shortest - 1), top + 1):
        match[lag] = float(np.dot(onset[lag:], onset[:-lag])) / (len(onset) - lag)

    def near(lag: int) -> float:
        return 0.0 if lag < 1 or lag > top else (match[lag - 1] + 2 * match[lag] + match[lag + 1]) / 4

    best, best_score = 0, 0.0
    for lag in range(shortest, longest + 1):
        # A beat's period also matches at twice the lag: counting that keeps a tempo from being heard at half speed.
        weight = np.exp(-0.5 * np.log2(lag / (60 / PREFER_BPM * hops_per_second)) ** 2)
        score = (near(lag) + 0.5 * near(2 * lag)) * weight
        if score > best_score:
            best, best_score = lag, score
    if best == 0:
        return 0.0
    a, b, c = match[best - 1], match[best], match[best + 1]
    bend = a - 2 * b + c
    return best + 0.5 * (a - c) / bend if bend < 0 else float(best)


def track(onset: np.ndarray, period: float) -> list[int]:
    """The beat frames: each beat on an onset, about one period after the last."""
    n = len(onset)
    score = np.zeros(n)
    came_from = np.full(n, -1)
    nearest, farthest = max(1, round(period / 2)), round(period * 2)
    for t in range(n):
        back = np.arange(nearest, min(farthest, t) + 1)
        if len(back):
            cost = score[t - back] - TIGHTNESS * np.log(back / period) ** 2
            pick = int(np.argmax(cost))
            if cost[pick] > 0:
                score[t] = cost[pick]
                came_from[t] = t - back[pick]
        score[t] += onset[t]
    last = n - round(period) + int(np.argmax(score[max(0, n - round(period)) :])) if n > period else int(np.argmax(score))
    frames = []
    t = max(0, last)
    while t >= 0:
        frames.append(t)
        t = int(came_from[t])
    frames.reverse()

    # A beat counted on into silence, before the music starts or after it stops, is not one.
    def sounds(f: int) -> bool:
        return onset[max(0, f - 1) : f + 2].max() > 0.05

    while frames and not sounds(frames[-1]):
        frames.pop()
    while frames and not sounds(frames[0]):
        frames.pop(0)
    return frames


def _peak_offset(onset: np.ndarray, f: int) -> float:
    """How far the onset's peak is from frame f, in hops: the top of a parabola through it and its neighbours."""
    if f < 1 or f + 1 >= len(onset):
        return 0.0
    a, b, c = onset[f - 1], onset[f], onset[f + 1]
    bend = a - 2 * b + c
    return float(np.clip(0.5 * (a - c) / bend, -0.5, 0.5)) if b >= a and b >= c and bend < 0 else 0.0


def detect(samples: np.ndarray, rate: int) -> dict:
    """{"tempo": beats per minute, "beats": [seconds, ...]} for mono samples. No tempo found gives no beats."""
    onset = onset_envelope(np.asarray(samples, dtype=np.float64), rate)
    if len(onset) < 8:
        return {"tempo": 0.0, "beats": []}
    period = tempo_period(onset, rate / HOP)
    if period == 0:
        return {"tempo": 0.0, "beats": []}
    # An onset frame's time is its centre.
    times = [((f + _peak_offset(onset, f)) * HOP + FRAME / 2) / rate for f in track(onset, period)]
    return {"tempo": round(60 / (period * HOP / rate), 2), "beats": [round(t, 3) for t in times]}


def grid(bpm: float, first: float, duration: float) -> dict:
    """Beats evenly spaced from `first` seconds at `bpm`, for a song whose tempo is known."""
    if bpm <= 0 or first < 0:
        raise ValueError("a tempo is positive, and the first beat is at 0 s or later")
    return {"tempo": round(bpm, 2), "beats": [round(t, 3) for t in np.arange(first, duration - 1e-6, 60 / bpm)]}


def of_file(path: str, rate: int = 44100, ffmpeg: str = "ffmpeg") -> dict:
    """The beats of a sound or video file's first sound track."""
    raw = subprocess.run(
        [ffmpeg, "-v", "error", "-i", path, "-map", "0:a:0", "-ac", "1", "-ar", str(rate), "-f", "f32le", "-"],
        capture_output=True,
        check=True,
    ).stdout
    return detect(np.frombuffer(raw, np.float32), rate)


if __name__ == "__main__":
    if len(sys.argv) != 2:
        sys.exit(__doc__)
    found = of_file(sys.argv[1])
    print(f"{len(found['beats'])} beats at {found['tempo']} BPM")
    print(found["beats"])
