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
from uberseek.media import FFmpegBackend, Frame, FrameIndex, FrameRef, MediaBackend, MediaError, SourceInfo
from uberseek.observe import render
from uberseek.observe.plan import LADDER, SAMPLE_RATE, SHEET_MOST, WAVEFORM_MAX, plan, tile_size
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


def _region(region) -> list[float] | None:
    """The part of the frame to show: left, top, right, bottom as fractions of its width and height."""
    if region is None:
        return None
    if len(region) != 4 or not all(isinstance(v, (int, float)) for v in region):
        raise ValueError("a region is [left, top, right, bottom], each a fraction of the frame from 0 to 1")
    left, top, right, bottom = (round(float(v), 4) for v in region)
    if not (0 <= left < right <= 1 and 0 <= top < bottom <= 1):
        raise ValueError(f"the region {list(region)} is not inside the frame: it needs 0 <= left < right <= 1 and 0 <= top < bottom <= 1")
    return [left, top, right, bottom]


def _shown(source: Source, region: list[float] | None) -> tuple[int, int]:
    """The size of what is shown: the whole frame, or the region of it."""
    width, height = source.info.video.width, source.info.video.height
    if region:
        width, height = max(2, round(width * (region[2] - region[0]))), max(2, round(height * (region[3] - region[1])))
    return width, height


def _of(region: list[float] | None) -> str:
    return f" · region {region[0]:g},{region[1]:g} to {region[2]:g},{region[3]:g}" if region else ""


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
        region: list[float] | None = None,
    ) -> Observation:
        """Show a span of the footage. The caller sets the span, the focus and the region; the harness sets the rest."""
        source = self.open(path)
        region = _region(region)
        start = seconds(start)
        asked = (source.index, source.info.duration, source.info.audio is not None, start, start if end is None else seconds(end), focus)
        # Cuts cost a pass over the whole picture, so they are made only for a look that is planned by shots,
        # and used elsewhere when they already exist. The recipe says which, so the look can be made again.
        use_cuts = plan(*asked).level in ("section", "map") or self.log.has_derived(source.hash, "cuts")
        made = plan(*asked, cuts=self._cuts(source) if use_cuts else None, change=self.change(source)[1] if focus == "change" else None)
        words = transcript.name(self.transcript_model)
        words = words if self.log.has_derived(source.hash, words) else None
        size, columns = tile_size(_shown(source, region), made.tile_long, len(made.targets))
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
            "region": region,
            "title": f"{source.path.name} · {_span(made.start, made.end)} · {focus}{_of(region)}",
        }
        return self._look(source, request, recipe, list(made.targets), made.in_span)

    def sheet(
        self, path: Path | str, times: list, labels: list[str] | None = None, purpose: str = "", region: list[float] | None = None
    ) -> Observation:
        """Show frames picked from anywhere in a video as one picture, like a plot of chosen points.

        The caller chooses which instants to show and may label each; the harness still sets their size.
        These are separate instants, so there is no sound strip, and nothing between them counts as seen.
        """
        source = self.open(path)
        region = _region(region)
        if not times:
            raise ValueError("a sheet needs at least one time")
        if len(times) > SHEET_MOST:
            raise ValueError(f"a sheet shows at most {SHEET_MOST} frames, and {len(times)} were asked for: pick fewer, or make two sheets")
        if labels is not None and len(labels) != len(times):
            raise ValueError(f"{len(labels)} labels were given for {len(times)} times: give one label per time, or none")
        index = source.index
        targets = [index.frames[index.position(seconds(t))].pts for t in times]  # in the order asked, like a plot
        first, last = index.time(min(targets)), index.time(max(targets))
        size, columns = tile_size(_shown(source, region), LADDER["passage"][2], len(targets))
        request = {"start": _fraction(first), "end": _fraction(last), "focus": "sheet", "purpose": purpose}
        recipe = {
            "level": "sheet",
            "targets": targets,
            "frame_size": list(size),
            "columns": columns,
            "sound": None,
            "mark": None,
            "labels": [str(label) for label in labels] if labels else None,
            "region": region,
            "title": f"{source.path.name} · {len(targets)} frames between {_span(first, last)} · separate instants{_of(region)}",
        }
        return self._look(source, request, recipe, sorted(targets), index.position(last) - index.position(first) + 1)

    def board(self, items: list[tuple], columns: int, title: str, purpose: str = "") -> Observation:
        """Show frames from several videos as one picture. Each item is (path, time, label).

        Every frame is drawn at the size of the first video's frame, so a video of another shape is
        stretched. It is logged under the set of videos, not under any one of them.
        """
        if not items:
            raise ValueError("there is nothing to show")
        if len(items) > SHEET_MOST:
            raise ValueError(
                f"one picture shows at most {SHEET_MOST} frames, and {len(items)} were asked for: show fewer videos or fewer frames of each"
            )
        sources = {str(path): self.open(path) for path, _, _ in items}
        first = next(iter(sources.values()))
        size, columns = tile_size(_shown(first, None), LADDER["passage"][2], len(items), columns)
        placed = []
        for path, at, label in items:
            source = sources[str(path)]
            pts = source.index.frames[source.index.position(seconds(at))].pts
            placed.append(
                {"path": str(source.path), "hash": source.hash, "pts": pts, "time": _fraction(source.index.time(pts)), "label": str(label)}
            )
        recipe = {"level": "board", "items": placed, "frame_size": list(size), "columns": columns, "title": title}
        request = {"start": "0", "end": "0", "focus": "board", "purpose": purpose}
        together = Source(
            Path(f"{len(sources)} videos"),
            hashlib.sha256("".join(sorted(s.hash for s in sources.values())).encode()).hexdigest(),
            first.info,
            first.index,
        )
        return self._look(together, request, recipe, [], len(items))

    def _board(self, recipe: dict) -> tuple[bytes, dict]:
        """Decode and draw a picture of frames from several videos, and report what came out."""
        size, frames = tuple(recipe["frame_size"]), [None] * len(recipe["items"])
        for path in dict.fromkeys(item["path"] for item in recipe["items"]):
            source = self.open(path)
            mine = [(i, item) for i, item in enumerate(recipe["items"]) if item["path"] == path]
            if any(item["hash"] != source.hash for _, item in mine):
                raise MediaError(f"{Path(path).name} is not the version that was observed")
            for (i, _), frame in zip(
                mine, self.backend.frames(source.path, source.index, [item["pts"] for _, item in mine], size), strict=True
            ):
                frames[i] = frame
        times = [Fraction(item["time"]) for item in recipe["items"]]
        picture = render.sheet(frames, times, recipe["columns"], [item["label"] for item in recipe["items"]])
        picture = render.stack(render.header(picture.width, recipe["title"]), picture)
        delivered = {
            "time_base": "1/1000",  # a board has no one timeline: these stand in, so code that reads any look still can
            "frames": [{"pts": round(t * 1000), "pixels_sha256": f.pixel_hash} for t, f in zip(times, frames, strict=True)],
            "size": list(picture.size),
            "drawn": ["frames"],
            "sound": None,
        }
        return render.png(picture), delivered

    def change(self, source: Source) -> tuple[list[float], list[int], list[bytes]]:
        """How much each frame differs from the one before: the mean, the largest cell, and the cells themselves."""
        made = self.log.derived(source.hash, "change", lambda: signals.change(source.path, len(source.index.frames)))
        cells, each = bytes.fromhex(made["cells"]), made["params"]["rows"] * made["params"]["columns"]
        grid = [cells[i * each : (i + 1) * each] for i in range(len(made["mean"]))]
        return made["mean"], [max(cell) for cell in grid], grid

    def _look(self, source: Source, request: dict, recipe: dict, in_time_order: list[int], in_span: int) -> Observation:
        """Draw what the recipe says, log it, and return it with the statement of what it shows."""
        began = time.perf_counter()
        image, delivered = self._board(recipe) if recipe["level"] == "board" else self._render(source, recipe)
        gaps = [float(b - a) * float(source.index.time_base) for a, b in pairwise(in_time_order)]
        record = self.log.append(
            {
                "source": {"hash": source.hash, "path": str(source.path), "format": source.info.format},
                "request": request,
                "recipe": recipe,
                "delivered": {
                    **delivered,
                    "frames_in_span": in_span,
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
        if record["recipe"]["level"] == "board":
            try:
                image, delivered = self._board(record["recipe"])
            except (MediaError, FileNotFoundError) as error:
                return Reproduction(id, False, False, False, [str(error)])
        else:
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
        region = tuple(recipe["region"]) if recipe.get("region") else None
        frames: list[Frame] = self.backend.frames(source.path, index, targets, tuple(recipe["frame_size"]), region)
        times = [index.time(pts) for pts in targets]
        span = [Fraction(t) for t in recipe.get("span") or (times[0], times[-1])]
        delivered: dict = {"time_base": _fraction(index.time_base), "frames": [], "size": None, "drawn": ["frames"], "sound": None}
        delivered["frames"] = [{"pts": f.pts, "pixels_sha256": f.pixel_hash} for f in frames]

        said, captions = [], recipe.get("labels")  # a sheet's labels are written where the words would be
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
        if recipe.get("title"):  # the picture names its video and span, so several pictures cannot be mixed up
            picture = render.stack(render.header(picture.width, recipe["title"]), picture)
        delivered["size"] = list(picture.size)
        return render.png(picture), delivered


def _span(start: Fraction, end: Fraction) -> str:
    return clock(start) if start == end else f"{clock(start)} to {clock(end)}"


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
    span = _span(start, end)
    if recipe["level"] == "board":
        listed = "; ".join(
            f"{i}: {Path(item['path']).name} at {clock(Fraction(item['time']))}{' (' + item['label'] + ')' if item['label'] else ''}"
            for i, item in enumerate(recipe["items"], 1)
        )
        width, height = recipe["frame_size"]
        return (
            f"{record['id']}: {recipe['title']}.\n"
            f"{len(recipe['items'])} frames, {width}x{height} each, left to right and top to bottom: {listed}.\n"
            "Each picture has its number and its time in its own video printed in its corner, and its video named under it. "
            "These are separate instants: nothing between them was shown, and no sound is drawn. Look closer with observe."
        )
    of = recipe.get("region")
    part = f" Only part of each frame is shown: from {of[0]:g},{of[1]:g} to {of[2]:g},{of[3]:g} of its width and height." if of else ""
    if recipe["level"] == "sheet":
        labels = recipe.get("labels") or [""] * len(times)
        listed = "; ".join(
            f"{i}: {clock(t)}{' (' + label + ')' if label else ''}" for i, (t, label) in enumerate(zip(times, labels, strict=True), 1)
        )
        width, height = recipe["frame_size"]
        return (
            f"{record['id']}: {Path(record['source']['path']).name}, a sheet of {len(times)} frames picked by the caller.\n"
            f"In the order given, {width}x{height} each: {listed}.\n"
            "Each picture has its number and its time printed in its corner. These are separate instants, not a span: "
            "nothing between them was shown, and no sound is drawn. Look closer at one with observe." + part
        )
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
    if part:
        lines.append(part.strip())
    if request["focus"] == "change":
        lines.append("The frames are those where the picture changes most, each with the frame before it; the rest are spread evenly.")
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
