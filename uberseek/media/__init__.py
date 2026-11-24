"""Host-side media services behind one interface. FFmpeg is the reference backend."""

from uberseek.media.backend import (
    AudioStream,
    Frame,
    FrameIndex,
    FrameRef,
    MediaBackend,
    MediaError,
    Segment,
    SourceInfo,
    VideoStream,
)
from uberseek.media.ffmpeg import FFmpegBackend

__all__ = [
    "AudioStream",
    "FFmpegBackend",
    "Frame",
    "FrameIndex",
    "FrameRef",
    "MediaBackend",
    "MediaError",
    "Segment",
    "SourceInfo",
    "VideoStream",
]
