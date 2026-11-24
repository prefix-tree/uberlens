"""The transcript: words with their timings, from Whisper.

A transcript is an estimate, not a measurement: it is kept with the model that produced it, and a word
may be wrong or misplaced. Times are on the file's own timeline, like every other signal.
"""

from __future__ import annotations

import os
from fractions import Fraction
from pathlib import Path

from uberseek.media.backend import MediaBackend, MediaError
from uberseek.timecode import Seconds

# The Whisper model. A smaller one (base, tiny) is faster where the clock is short; set UBERSEEK_TRANSCRIPT_MODEL.
MODEL = os.environ.get("UBERSEEK_TRANSCRIPT_MODEL", "small")
RATE = 16_000


def name(model: str = MODEL) -> str:
    """The key the transcript is cached under."""
    return f"transcript:{model}"


def transcribe(path: Path, backend: MediaBackend, duration: Seconds, model: str = MODEL) -> dict:
    """Words as [start, end, text, probability], with times in seconds as decimal strings."""
    try:
        import faster_whisper
        import numpy
    except ImportError as error:
        raise MediaError("transcription needs the 'transcript' extra: uv sync --extra transcript") from error

    pcm = backend.audio(path, Fraction(0), duration, RATE)  # from time zero, so Whisper's clock is the file's
    samples = numpy.frombuffer(pcm, dtype=numpy.int16).astype(numpy.float32) / 32768
    whisper = faster_whisper.WhisperModel(model, device="cpu", compute_type="int8")
    segments, info = whisper.transcribe(samples, word_timestamps=True, vad_filter=True, beam_size=5)
    words = [
        [f"{word.start:.3f}", f"{word.end:.3f}", word.word.strip(), round(float(word.probability), 3)]
        for segment in segments
        for word in segment.words or []
    ]
    return {
        "kind": "estimated",
        "tool": "faster-whisper",
        "version": faster_whisper.__version__,
        "model": model,
        "language": info.language,
        "words": words,
    }


def by_frame(words: list[list], times: list[Seconds], start: Seconds, end: Seconds) -> list[str]:
    """For each frame shown, the words that start from its time until the next frame's time.

    The first frame also takes the words from the start of the span, and the last takes them to its end,
    so every word in the span is under some frame.
    """
    edges = [min(start, times[0]), *times[1:], max(end, times[-1])]
    out = []
    for i in range(len(times)):
        last = i == len(times) - 1
        said = [w[2] for w in words if edges[i] <= Fraction(w[0]) < edges[i + 1] or (last and Fraction(w[0]) == edges[i + 1])]
        out.append(" ".join(said))
    return out


def within(words: list[list], start: Seconds, end: Seconds) -> list[tuple[Seconds, Seconds, str]]:
    return [(Fraction(w[0]), Fraction(w[1]), w[2]) for w in words if Fraction(w[1]) > start and Fraction(w[0]) < end]
