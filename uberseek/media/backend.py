"""What a media backend must provide: file facts, the frame index, exact frames and sound samples.

Signals and pictures are computed above this interface, from decoded frames and samples, so a second
backend only has to match these four calls.
"""

from __future__ import annotations

import hashlib
from bisect import bisect_right
from dataclasses import dataclass
from fractions import Fraction
from pathlib import Path
from typing import Protocol

from uberseek.timecode import Seconds

Region = tuple[float, float, float, float]  # the part of a frame to keep: left, top, right, bottom, as fractions


class MediaError(RuntimeError):
    """The backend could not read the file, or did not return what was asked for."""


@dataclass(frozen=True)
class VideoStream:
    codec: str
    width: int  # as displayed: after rotation and with square pixels
    height: int
    time_base: Fraction
    rotation: int


@dataclass(frozen=True)
class AudioStream:
    codec: str
    sample_rate: int
    channels: int


@dataclass(frozen=True)
class SourceInfo:
    format: str
    duration: Seconds
    video: VideoStream | None
    audio: AudioStream | None


@dataclass(frozen=True)
class FrameRef:
    pts: int
    key: bool


@dataclass(frozen=True)
class FrameIndex:
    """Every displayed frame of a video stream, in presentation order."""

    time_base: Fraction
    frames: tuple[FrameRef, ...]

    def time(self, pts: int) -> Seconds:
        return pts * self.time_base

    @property
    def start(self) -> Seconds:
        return self.time(self.frames[0].pts)

    @property
    def end(self) -> Seconds:
        """When the last frame starts. Its length is not known for every container."""
        return self.time(self.frames[-1].pts)

    def position(self, t: Seconds) -> int:
        """Index of the frame showing at t: the last one starting at or before t."""
        ticks = t / self.time_base
        return max(0, bisect_right(self.frames, ticks, key=lambda f: f.pts) - 1)

    def keyframes_before(self, pts: int) -> list[int]:
        """Keyframe timestamps at or before pts, nearest first."""
        return [f.pts for f in reversed(self.frames) if f.key and f.pts <= pts]


@dataclass(frozen=True)
class Frame:
    pts: int
    width: int
    height: int
    rgb: bytes

    @property
    def pixel_hash(self) -> str:
        head = f"{self.width}x{self.height}:rgb24:".encode()
        return hashlib.sha256(head + self.rgb).hexdigest()


@dataclass(frozen=True)
class Segment:
    """A run of frames of one file: from the frame at `first` up to, not including, the frame at `end`."""

    path: Path
    index: FrameIndex
    first: int  # timestamp of the first frame kept
    end: int  # timestamp of the first frame not kept


class MediaBackend(Protocol):
    name: str
    version: str

    def probe(self, path: Path) -> SourceInfo: ...

    def frame_index(self, path: Path) -> FrameIndex: ...

    def frames(self, path: Path, index: FrameIndex, pts: list[int], size: tuple[int, int], region: Region | None = None) -> list[Frame]:
        """Decode exactly the frames with these timestamps, scaled to size. Fails if any is missing.

        A region is the part of the frame to keep: left, top, right, bottom as fractions of its width and height.
        """
        ...

    def audio(self, path: Path, start: Seconds, duration: Seconds, rate: int) -> bytes:
        """Mono signed 16-bit samples for [start, start + duration), silence where there is no sound."""
        ...

    def join(self, segments: list[Segment], out: Path, size: tuple[int, int], sound: bool) -> list[str]:
        """Write the segments one after another into one file, cut on exact frames. Returns the command run."""
        ...

    def decodes(self, path: Path) -> list[str]:
        """Decode the whole file. Returns what went wrong, or nothing."""
        ...
