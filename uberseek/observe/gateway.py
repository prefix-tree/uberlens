"""The observe gateway: the one way footage reaches the model.

Every observation says what it delivered, is stored with its picture, and can be made again from its
log entry alone. `reproduce` is the proof: same file, same timestamps, same pixels.
"""

from __future__ import annotations

import hashlib
import statistics
import time
from dataclasses import dataclass, field
from fractions import Fraction
from functools import partial
from itertools import pairwise
from pathlib import Path

import PIL

from uberseek.ingest import signals, transcript
from uberseek.media import FFmpegBackend, FrameIndex, FrameRef, MediaBackend, MediaError, SourceInfo
from uberseek.observe import render
from uberseek.observe.plan import SAMPLE_RATE, WAVEFORM_MAX, plan, tile_size
from uberseek.state.log import Log
from uberseek.timecode import Seconds, clock, seconds


@dataclass(frozen=True)
class Source:
    path: Path
    hash: str
    info: SourceInfo
    index: FrameIndex


@dataclass(frozen=True)
class Observation:
    """What the model is given: one picture, and a plain statement of what it shows."""

    id: str
    image: bytes
    text: str
    record: dict

    media_type = "image/png"


@dataclass(frozen=True)
class Reproduction:
    id: str
    frames: bool  # every frame decoded again has the same pixels
    sound: bool  # the sound samples are the same
    picture: bool  # the picture drawn again is the same file, byte for byte
    notes: list[str] = field(default_factory=list)

    @property
    def exact(self) -> bool:
        return self.frames and self.sound and self.picture


def _fraction(value: Fraction) -> str:
    return f"{value.numerator}/{value.denominator}"


class Project:
    """A folder holding the log, the pictures shown and what was derived from each source."""

    def __init__(
        self,
        root: Path | str = ".",
        backend: MediaBackend | None = None,
        transcript_model: str = transcript.MODEL,
        words_in: tuple[str, ...] = ("picture", "text"),
    ):
        self.log = Log(Path(root))
        self.backend = backend or FFmpegBackend()
        self.transcript_model = transcript_model
        self.words_in = words_in  # where a look puts the words: under the pictures, in the text, or both

    def open(self, path: Path | str) -> Source:
        path = Path(path)
        digest = self.log.content_hash(path)
        info = self.backend.probe(path)
        if info.video is None:
            raise MediaError(f"{path.name} has no video stream")

        def index() -> dict:
            made = self.backend.frame_index(path)
            return {"time_base": _fraction(made.time_base), "frames": [[f.pts, int(f.key)] for f in made.frames]}

        cached = self.log.derived(digest, "frame_index", index)
        frames = tuple(FrameRef(pts, bool(key)) for pts, key in cached["frames"])
        return Source(path, digest, info, FrameIndex(Fraction(cached["time_base"]), frames))

    def observe(
        self,
        path: Path | str,
        start: Seconds | str | int,
        end: Seconds | str | int | None = None,
        focus: str = "visual",
        purpose: str = "",
    ) -> Observation:
        """Show a span of the footage. The caller sets the span and the focus; the harness sets the rest."""
        source = self.open(path)
        start = seconds(start)
        asked = (source.index, source.info.duration, source.info.audio is not None, start, start if end is None else seconds(end), focus)
        # Cuts cost a pass over the whole picture, so they are made only for a look that is planned by shots,
        # and used elsewhere when they already exist. The recipe says which, so the look can be made again.
        use_cuts = plan(*asked).level in ("section", "map") or self.log.has_derived(source.hash, "cuts")
        made = plan(*asked, cuts=self._cuts(source) if use_cuts else None)
        words = transcript.name(self.transcript_model)
        words = words if self.log.has_derived(source.hash, words) else None
        size, columns = tile_size((source.info.video.width, source.info.video.height), made.tile_long, len(made.targets))
        request = {
            "start": _fraction(made.start),
            "end": _fraction(made.end),
            "focus": focus,
            "purpose": purpose,
        }
        recipe = {
            "level": made.level,
            "targets": list(made.targets),
            "frame_size": list(size),
            "columns": columns,
            "sound": [_fraction(t) for t in made.sound] if made.sound else None,
            "mark": _fraction(made.mark) if made.mark is not None else None,
            "span": [_fraction(made.start), _fraction(made.end)],
            "focus": focus,
            "cuts": use_cuts,
            "shots": made.shots,
            "words": words,
            "words_in": list(self.words_in),
        }
        began = time.perf_counter()
        image, delivered = self._render(source, recipe)
        gaps = [float(b - a) * float(source.index.time_base) for a, b in pairwise(made.targets)]
        record = self.log.append(
            {
                "source": {"hash": source.hash, "path": str(source.path), "format": source.info.format},
                "request": request,
                "recipe": recipe,
                "delivered": {
                    **delivered,
                    "frames_in_span": made.in_span,
                    "gap_seconds": {"median": statistics.median(gaps), "max": max(gaps)} if gaps else None,
                    "heard": False,
                },
                "artifact": {
                    "sha256": self.log.put_artifact(image, ".png"),
                    "media_type": Observation.media_type,
                    "bytes": len(image),
                },
                "backend": {"name": self.backend.name, "version": self.backend.version, "pillow": PIL.__version__},
                "cost": {"seconds": round(time.perf_counter() - began, 3)},
                "relates": [],
            }
        )
        return Observation(record["id"], image, _describe(record, source), record)

    def transcribe(self, path: Path | str) -> dict:
        """Make the transcript of a source, once. Later looks at that source show its words."""
        source = self.open(path)
        if source.info.audio is None:
            raise MediaError(f"{source.path.name} has no sound to transcribe")
        model = self.transcript_model
        make = partial(transcript.transcribe, source.path, self.backend, source.info.duration, model)
        return self.log.derived(source.hash, transcript.name(model), make)

    def _cuts(self, source: Source) -> list[int]:
        return self.log.derived(source.hash, "cuts", lambda: signals.cuts(source.path))["pts"]

    def show(self, id: str) -> Observation:
        """A past observation again, from its stored picture. Nothing is decoded."""
        record = self.log.get(id)
        image = self.log.artifact(record["artifact"]["sha256"], ".png")
        return Observation(id, image, _describe(record, None), record)

    def reproduce(self, id: str, path: Path | str | None = None) -> Reproduction:
        """Make a logged observation again and compare it with what was shown."""
        record = self.log.get(id)
        source = self.open(path or record["source"]["path"])
        if source.hash != record["source"]["hash"]:
            return Reproduction(id, False, False, False, ["the file's content is not the version that was observed"])
        image, delivered = self._render(source, record["recipe"])
        was, notes = record["delivered"], []
        frames = delivered["frames"] == was["frames"]
        sound = delivered["sound"] == was["sound"]
        picture = hashlib.sha256(image).hexdigest() == record["artifact"]["sha256"]
        if not frames:
            notes.append("decoded frames differ")
        if not sound:
            notes.append("sound samples differ")
        if frames and sound and not picture:
            notes.append("same frames and sound, drawn differently: the renderer or the Pillow version has changed")
        return Reproduction(id, frames, sound, picture, notes)

    def _render(self, source: Source, recipe: dict) -> tuple[bytes, dict]:
        """Decode and draw exactly what the recipe says, and report what came out."""
        index, targets = source.index, recipe["targets"]
        frames = self.backend.frames(source.path, index, targets, tuple(recipe["frame_size"]))
        times = [index.time(pts) for pts in targets]
        span = [Fraction(t) for t in recipe.get("span") or (times[0], times[-1])]
        delivered: dict = {"time_base": _fraction(index.time_base), "frames": [], "size": None, "drawn": ["frames"], "sound": None}
        delivered["frames"] = [{"pts": f.pts, "pixels_sha256": f.pixel_hash} for f in frames]

        said, captions = [], None
        if recipe.get("words"):
            said = self.log.derived(source.hash, recipe["words"], _missing("the transcript"))
            captions = transcript.by_frame(said["words"], times, span[0], span[1])
            delivered["words"] = {"tool": said["tool"], "model": said["model"], "by_frame": captions}
            # No room is kept for words when nothing is said, or when the words go in the text only.
            captions = captions if any(captions) and "picture" in recipe.get("words_in", ["picture"]) else None
            delivered["drawn"] += ["words"] if captions else []
            said = said["words"]
        cuts = [index.time(pts) for pts in self._cuts(source)] if recipe.get("cuts") else []
        if recipe.get("cuts"):
            delivered["cuts"] = [_fraction(t) for t in cuts if span[0] < t <= span[1]]
        picture = render.sheet(frames, times, recipe["columns"], captions)

        if recipe["sound"]:
            start, end = (Fraction(t) for t in recipe["sound"])
            quiet = self.log.derived(source.hash, "silences", lambda: signals.silences(source.path))
            if end - start <= WAVEFORM_MAX:
                pcm = self.backend.audio(source.path, start, end - start, SAMPLE_RATE)
                wave, caption = render.envelope(pcm, picture.width), "sound wave (decibel scale)"
                delivered["sound"] = {"kind": "waveform", "rate": SAMPLE_RATE, "samples_sha256": hashlib.sha256(pcm).hexdigest()}
            else:
                loud = self.log.derived(source.hash, "loudness", lambda: signals.loudness(source.path))
                wave, caption = render.loudness_envelope(loud["points"], (start, end), picture.width), "measured loudness"
                delivered["sound"] = {"kind": "loudness", "tool": loud["tool"]}
            pauses = signals.within(quiet["spans"], start, end)
            delivered["sound"] |= {
                "start": _fraction(start),
                "end": _fraction(end),
                "pauses": [[_fraction(a), _fraction(b)] for a, b in pauses],
                "pause_rule": quiet["params"],
            }
            delivered["drawn"] += [delivered["sound"]["kind"], "silences"]
            mark = Fraction(recipe["mark"]) if recipe["mark"] else None
            on_strip = recipe.get("focus") in ("speech", "delivery", "boundary") and end - start <= WAVEFORM_MAX
            spoken = transcript.within(said, start, end) if on_strip else []
            caption += ", silences shaded, ticks are the numbered frames"
            caption += ", red lines are cuts" if cuts else ""
            caption += ", the yellow line is the instant asked about" if mark else ""
            strip = render.strip(picture.width, (start, end), wave, pauses, times, mark, caption, cuts, spoken)
            picture = render.stack(picture, strip)
        delivered["size"] = list(picture.size)
        return render.png(picture), delivered


def _missing(what: str):
    def fail():
        raise MediaError(f"{what} this observation used is not in this project")

    return fail


def _describe(record: dict, source: Source | None) -> str:
    """The text that goes to the model with the picture: what was asked, and what was actually delivered."""
    request, delivered, recipe = record["request"], record["delivered"], record["recipe"]
    base = Fraction(delivered["time_base"])
    times = [frame["pts"] * base for frame in delivered["frames"]]
    start, end = Fraction(request["start"]), Fraction(request["end"])
    span = clock(start) if start == end else f"{clock(start)} to {clock(end)}"
    lines = [
        f"{record['id']}: {Path(record['source']['path']).name}, {span}, focus {request['focus']}, level {recipe['level']}.",
    ]
    count, width, height = len(times), *recipe["frame_size"]
    if count == 1:
        lines.append(f"1 frame, at {clock(times[0])}, {width}x{height}.")
    else:
        gap = delivered["gap_seconds"]
        apart = f"{gap['median']:.3f} s apart" + (f" (at most {gap['max']:.3f} s)" if gap["max"] > gap["median"] * 1.01 else "")
        lines.append(
            f"{count} frames from {clock(times[0])} to {clock(times[-1])}, {apart}, {width}x{height} each, "
            f"in time order. Each picture has its number and its time printed in its corner; "
            f"a number in this text or on the strip means that picture, not a frame count of the video. "
            f"The span holds {delivered['frames_in_span']} frames."
        )
    if recipe.get("shots"):
        lines.append(f"One frame per shot: the span holds {recipe['shots']} shots.")
    if cuts := delivered.get("cuts"):
        shown = ", ".join(clock(Fraction(t)) for t in cuts[:12])
        lines.append(f"{len(cuts)} cut{'s' if len(cuts) > 1 else ''} in the span, at {shown}{' and later' if len(cuts) > 12 else ''}.")
    elif "cuts" in delivered:
        lines.append("No cuts in the span.")
    if (words := delivered.get("words")) and "text" in recipe.get("words_in", ["text"]):
        spoken = [f"{i}: {text[:200]}" for i, text in enumerate(words["by_frame"], start=1) if text]
        lines.append(
            f"Words under each frame, said from that frame until the next "
            f"(transcribed by {words['tool']} {words['model']}; an estimate, a word can be wrong): "
            + ("; ".join(spoken) if spoken else "none")
            + "."
        )
    sound = delivered["sound"]
    if sound:
        what = "its wave" if sound["kind"] == "waveform" else "its measured loudness"
        pauses = [f"{clock(Fraction(a))} to {clock(Fraction(b))}" for a, b in sound["pauses"]]
        rule = sound["pause_rule"]
        lines.append(
            f"Sound from {clock(Fraction(sound['start']))} to {clock(Fraction(sound['end']))} is drawn as {what}. "
            + (
                f"Pauses (quieter than {rule['noise_db']} dB for {rule['min_seconds']} s or more): {'; '.join(pauses)}. "
                if pauses
                else "No pauses measured. "
            )
            + "You have seen the sound, not heard it: treat any judgment about it as not heard."
        )
    else:
        lines.append("No sound is shown.")
    return "\n".join(lines)
