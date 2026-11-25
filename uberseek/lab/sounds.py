"""Sounds for a clip, made here so they are free to share: a music bed, and key clicks for text that types in.

    python -m uberseek.lab.sounds <Kenney interface-sounds folder> <out folder>

The music is synthesized: 40 s at 96 BPM, a pad on four chords, a plucked arpeggio that echoes left and right, a
soft kick and a sub. The key sounds are built from Kenney's Interface Sounds (CC0, kenney.nl): one click, and a
burst of six for a line that types itself in. Needs numpy.

Chosen blind: an agent cannot hear, so these were picked by length and pitch, and a person judged the mix.
"""

from __future__ import annotations

import subprocess
import sys
import wave
from pathlib import Path

import numpy as np

RATE = 48000


def write(path: Path, samples: np.ndarray) -> None:
    """A 16-bit WAV of samples in -1..1: one column per channel, or a flat array for mono."""
    samples = np.clip(samples, -1, 1)
    if samples.ndim == 1:
        samples = samples[:, None]
    with wave.open(str(path), "wb") as out:
        out.setnchannels(samples.shape[1])
        out.setsampwidth(2)
        out.setframerate(RATE)
        out.writeframes((samples * 32767).astype("<i2").tobytes())


def load(path: Path, ffmpeg: str = "ffmpeg") -> np.ndarray:
    raw = subprocess.run(
        [ffmpeg, "-v", "error", "-i", str(path), "-ac", "1", "-ar", str(RATE), "-f", "f32le", "-"], capture_output=True, check=True
    ).stdout
    return np.frombuffer(raw, np.float32)


def typing(clicks: list[np.ndarray]) -> np.ndarray:
    """Six key presses in 0.4 s, uneven like typing, from a few different click sounds."""
    presses = [(0, 0.00, 1.0), (1, 0.065, 0.8), (2, 0.14, 0.95), (3, 0.20, 0.7), (0, 0.275, 0.9), (1, 0.345, 0.85)]
    out = np.zeros(int(0.5 * RATE), np.float32)
    for which, at, gain in presses:
        click = clicks[which % len(clicks)][: int(0.08 * RATE)]
        start = int(at * RATE)
        out[start : start + len(click)] += gain * click
    return out / np.abs(out).max() * 10 ** (-4 / 20)


def _note(midi: int) -> float:
    return 440 * 2 ** ((midi - 69) / 12)


def music(seconds: float = 40.0, bpm: float = 96) -> np.ndarray:
    """The bed, in stereo, peaking at -3 dBFS and fading over its last two seconds."""
    beat = 60 / bpm
    bar = 4 * beat
    n = int(seconds * RATE)
    left, right = np.zeros(n), np.zeros(n)
    chords = [[57, 60, 64, 67], [53, 57, 60, 64], [48, 52, 55, 60], [55, 59, 62, 67]]  # Am7, Fmaj7, C, G

    def add(channel: np.ndarray, at: float, sound: np.ndarray) -> None:
        start = int(at * RATE)
        if start < n:
            sound = sound[: n - start]
            channel[start : start + len(sound)] += sound

    for index in range(int(seconds / bar) + 1):
        chord = chords[(index // 2) % 4]
        at = index * bar
        # Pad: each chord tone as a few soft harmonics, two voices slightly apart for width, slow in and out.
        t = np.arange(int((bar + 0.6) * RATE)) / RATE
        envelope = np.minimum(1, t / 0.5) * np.minimum(1, (t[-1] - t) / 0.6)
        for k, pitch in enumerate(chord):
            for channel, detune in ((left, 0.997), (right, 1.003)):
                voice = sum(np.sin(2 * np.pi * _note(pitch) * detune * h * t + k) / h**2 for h in (1, 2, 3, 4))
                add(channel, at, 0.05 * envelope * voice)
        # Sub on the root, and a soft kick on beats one and three.
        t = np.arange(int(bar * RATE)) / RATE
        sub = 0.16 * np.sin(2 * np.pi * _note(chord[0] - 12) * t) * np.minimum(1, t / 0.05) * np.minimum(1, (t[-1] - t) / 0.2)
        add(left, at, sub)
        add(right, at, sub)
        t = np.arange(int(0.3 * RATE)) / RATE
        kick = 0.5 * np.sin(2 * np.pi * (45 * t + 2.6 * (1 - np.exp(-t / 0.03)))) * np.exp(-t / 0.09)
        for on in (0, 2):
            add(left, at + on * beat, kick)
            add(right, at + on * beat, kick)
        # Arpeggio: eighth notes up the chord, an octave above, each pluck echoed on the other side.
        t = np.arange(int(0.5 * RATE)) / RATE
        for eighth in range(8):
            f = _note(chord[eighth % 4] + 12 + (12 if eighth in (3, 7) else 0))
            pluck = 0.11 * (np.sin(2 * np.pi * f * t) + 0.4 * np.sin(4 * np.pi * f * t)) * np.exp(-t / 0.12) * np.minimum(1, t / 0.003)
            near, far = (left, right) if eighth % 2 == 0 else (right, left)
            add(near, at + eighth * beat / 2, pluck)
            add(far, at + eighth * beat / 2 + beat * 0.75, 0.45 * pluck)
            add(near, at + eighth * beat / 2 + beat * 1.5, 0.2 * pluck)
    mix = np.stack([left, right], 1)
    mix *= np.minimum(1, (seconds - np.arange(n) / RATE) / 2.0)[:, None]
    mix = np.tanh(mix * 1.6)
    return mix / np.abs(mix).max() * 10 ** (-3 / 20)


if __name__ == "__main__":
    if len(sys.argv) != 3:
        sys.exit(__doc__)
    kenney, out = Path(sys.argv[1]), Path(sys.argv[2])
    clicks = [load(kenney / f"click_00{i}.ogg") for i in (2, 5, 3, 1)]
    write(out / "click.wav", clicks[0])
    write(out / "type.wav", typing(clicks))
    write(out / "music.wav", music())
    print(f"click.wav, type.wav and music.wav in {out}")
