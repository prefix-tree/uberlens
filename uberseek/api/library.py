"""The library: every public method here is one operation an agent can use.

Values are plain (numbers, strings, lists, dicts) so they pass into a sandboxed program unchanged, and
times are seconds. Frames are still chosen by exact timestamp on the host side.
"""

from __future__ import annotations

import inspect
from fractions import Fraction
from pathlib import Path

from uberseek import select
from uberseek.api import search, spans
from uberseek.ingest import signals, transcript
from uberseek.media import MediaError
from uberseek.observe.gateway import Observation, Project, Source
from uberseek.timecode import seconds


class ApiError(ValueError):
    """A request the library cannot serve, said so the caller can fix it."""


def signature(function) -> str:
    """A function's parameters and return type as they would be written, without `self`."""
    parts = []
    for name, parameter in inspect.signature(function).parameters.items():
        if name == "self":
            continue
        default = "" if parameter.default is parameter.empty else f" = {parameter.default!r}"
        parts.append(f"{name}: {parameter.annotation}{default}")
    return f"({', '.join(parts)}) -> {inspect.signature(function).return_annotation}"


def _f(value: Fraction | str) -> float:
    return round(float(Fraction(value)), 3)


class Library:
    """The operations, bound to one project and to the videos an agent may use."""

    OPERATIONS = (
        "info", "find", "words", "pauses", "loudness", "cuts", "shots", "observe", "sheet",
        "observations", "coverage", "expand", "merge", "minus", "mark", "selections", "clip", "verify",
    )  # fmt: skip

    def __init__(self, project: Project, videos: list[Path | str] | None = None):
        self.project = project
        self.videos = {Path(v).name: Path(v) for v in videos} if videos is not None else None
        self.looks: list[Observation] = []  # pictures made by `observe`, for whoever delivers them to the model

    # Sources

    def _source(self, video: str) -> Source:
        if self.videos is None:
            path = Path(video)
        elif Path(video).name in self.videos:
            path = self.videos[Path(video).name]
        elif (made := select.clips_folder(self.project) / Path(video).name).exists():
            path = made  # a clip cut in this project is a video like any other
        else:
            raise ApiError(f"no video named {video!r}. Available: {', '.join(self.videos) or 'none'}")
        try:
            return self.project.open(path)
        except (FileNotFoundError, MediaError) as error:
            raise ApiError(f"cannot open {video!r}: {error}") from error

    def _window(self, source: Source, start: float | None, end: float | None) -> tuple[Fraction, Fraction]:
        low = seconds(start) if start is not None else Fraction(0)
        high = seconds(end) if end is not None else max(source.info.duration, source.index.end, low)
        if high < low:
            raise ApiError(f"the span ends ({end}) before it starts ({start})")
        return low, high

    def _transcript(self, source: Source) -> list[list]:
        if source.info.audio is None:
            raise ApiError(f"{source.path.name} has no sound, so it has no words")
        try:
            return self.project.transcribe(source.path)["words"]
        except MediaError as error:
            raise ApiError(str(error)) from error

    def info(self, video: str) -> dict:
        """Facts about a video: its length in seconds, its size, and what has been prepared for it.

        Args:
            video: Name or path of the video.
        """
        source = self._source(video)
        log, key = self.project.log, transcript.name(self.project.transcript_model)
        return {
            "video": source.path.name,
            "duration": _f(source.info.duration),
            "frames": len(source.index.frames),
            "width": source.info.video.width,
            "height": source.info.video.height,
            "has_sound": source.info.audio is not None,
            "has_transcript": log.has_derived(source.hash, key),
            "has_cuts": log.has_derived(source.hash, "cuts"),
        }

    # Searching

    def find(
        self,
        video: str,
        query: str = "",
        after: float | None = None,
        before: float | None = None,
        limit: int = 8,
        like: list[float] | None = None,
    ) -> list[dict]:
        """Find candidate spans where the words of `query` are said. Best first.

        It searches the transcript and matches words, not meaning: rephrase with words the speaker
        would use. A candidate is a place to look, not an answer, and an empty list does not mean the
        moment is absent: look at the map, or ask `coverage` what has not been looked at.

        Args:
            video: Name or path of the video.
            query: Words to look for.
            after: Only candidates that start at or after this time, in seconds.
            before: Only candidates that end at or before this time, in seconds.
            limit: The most candidates to return.
            like: Not available yet: a span to find lookalikes of.

        Returns:
            A list of {"start", "end", "text", "score", "how"}. "how" is "words"; "score" is an estimate.
        """
        if like is not None:
            raise ApiError("find(like=...) needs the picture index, which is not built yet. Search by words, or look with observe")
        source = self._source(video)
        low, high = self._window(source, after, before)
        found = [p for p in search.passages(self._transcript(source)) if p["start"] >= low and p["end"] <= high]
        return search.rank(found, query, max(1, min(int(limit), 50)))

    def words(self, video: str, start: float, end: float) -> list[dict]:
        """The words said in a span, each with its start and end time. From the transcript: an estimate.

        Args:
            video: Name or path of the video.
            start: Start of the span, in seconds.
            end: End of the span, in seconds.
        """
        source = self._source(video)
        low, high = self._window(source, start, end)
        said = transcript.within(self._transcript(source), low, high)
        return [{"start": _f(a), "end": _f(b), "text": text} for a, b, text in said]

    # Measurements

    def pauses(self, video: str, start: float | None = None, end: float | None = None) -> list[list[float]]:
        """Measured silent stretches in a span, as [start, end] pairs. A quarter of a second or longer.

        Args:
            video: Name or path of the video.
            start: Start of the span, in seconds. Leave out for the beginning.
            end: End of the span, in seconds. Leave out for the end of the video.
        """
        source = self._source(video)
        if source.info.audio is None:
            return []
        low, high = self._window(source, start, end)
        quiet = self.project.log.derived(source.hash, "silences", lambda: signals.silences(source.path))
        return [[_f(a), _f(b)] for a, b in signals.within(quiet["spans"], low, high)]

    def loudness(self, video: str, start: float, end: float) -> list[list[float]]:
        """Measured loudness in a span, as [time, LUFS] pairs every tenth of a second. Louder is nearer zero.

        Args:
            video: Name or path of the video.
            start: Start of the span, in seconds.
            end: End of the span, in seconds. At most 120 seconds after `start`.
        """
        source = self._source(video)
        if source.info.audio is None:
            return []
        low, high = self._window(source, start, end)
        if high - low > 120:
            raise ApiError("loudness covers at most 120 seconds at a time; ask for a shorter span")
        loud = self.project.log.derived(source.hash, "loudness", lambda: signals.loudness(source.path))
        return [[_f(t), float(v)] for t, v in loud["points"] if low <= Fraction(t) <= high]

    def cuts(self, video: str, start: float | None = None, end: float | None = None) -> list[float]:
        """Times where the picture cuts to a new shot, measured. The first use on a video scans all of it.

        Args:
            video: Name or path of the video.
            start: Start of the span, in seconds. Leave out for the beginning.
            end: End of the span, in seconds. Leave out for the end of the video.
        """
        source = self._source(video)
        low, high = self._window(source, start, end)
        times = [source.index.time(pts) for pts in self.project._cuts(source)]
        return [_f(t) for t in times if low <= t <= high]

    def shots(self, video: str, start: float | None = None, end: float | None = None) -> list[list[float]]:
        """The shots in a span, as [start, end] pairs: the stretches between cuts.

        Args:
            video: Name or path of the video.
            start: Start of the span, in seconds. Leave out for the beginning.
            end: End of the span, in seconds. Leave out for the end of the video.
        """
        source = self._source(video)
        low, high = self._window(source, start, end)
        edges = [_f(low), *self.cuts(video, start, end), _f(high)]
        return [[a, b] for a, b in zip(edges, edges[1:], strict=False) if b > a]

    # Looking

    def observe(self, video: str, start: float, end: float | None = None, focus: str = "visual", purpose: str = "") -> dict:
        """Look at a span. The picture is shown to you after the program ends; a program cannot see it.

        You choose the span and the focus; how many frames and how large is chosen for you.

        Args:
            video: Name or path of the video.
            start: Start of the span, in seconds.
            end: End of the span. Leave out to see the single frame showing at `start`.
            focus: visual (what is in the picture), motion (dense frames), speech or delivery (sound and
                pauses, a few frames), boundary (frames and sound right around one instant).
            purpose: The question this look should answer, in a few words. Kept in the log.

        Returns:
            {"id", "text"}: the observation's id and the statement of what it shows.
        """
        source = self._source(video)
        try:
            seen = self.project.observe(source.path, start, end, focus, purpose)
        except (MediaError, ValueError) as error:
            raise ApiError(str(error)) from error
        self.looks.append(seen)
        return {"id": seen.id, "text": seen.text}

    def sheet(self, video: str, times: list[float], labels: list[str] | None = None, purpose: str = "") -> dict:
        """Show frames from anywhere in a video as one picture, like a plot: one frame per time you give.

        Use it to scan or compare many places at the cost of one look: one frame per shot, one per
        candidate. The frames are small and are separate instants, so look closer at the one that matters
        with `observe`. The picture is shown to you after the program ends; a program cannot see it.

        Args:
            video: Name or path of the video.
            times: The instants to show, in seconds, in the order to draw them. At most 24.
            labels: A short label to print under each frame, one per time (a rank, a length, a few words).
            purpose: The question this sheet should answer, in a few words. Kept in the log.

        Returns:
            {"id", "text"}: the observation's id and the statement of what it shows.
        """
        source = self._source(video)
        try:
            seen = self.project.sheet(source.path, times, labels, purpose)
        except (MediaError, ValueError) as error:
            raise ApiError(str(error)) from error
        self.looks.append(seen)
        return {"id": seen.id, "text": seen.text}

    # Memory

    def observations(
        self, video: str | None = None, focus: str | None = None, start: float | None = None, end: float | None = None
    ) -> list[dict]:
        """Looks already made, oldest first: what was asked, what was shown, and why.

        Args:
            video: Only looks at this video.
            focus: Only looks with this focus.
            start: Only looks that reach past this time, in seconds.
            end: Only looks that begin before this time, in seconds.
        """
        source = self._source(video) if video else None
        out = []
        for record in self.project.log.observations(source.hash if source else None):
            request, delivered = record["request"], record["delivered"]
            a, b = _f(request["start"]), _f(request["end"])
            if (focus and request["focus"] != focus) or (start is not None and b < start) or (end is not None and a > end):
                continue
            gap = delivered["gap_seconds"]
            out.append(
                {
                    "id": record["id"],
                    "video": Path(record["source"]["path"]).name,
                    "start": a,
                    "end": b,
                    "focus": request["focus"],
                    "purpose": request["purpose"],
                    "level": record["recipe"]["level"],
                    "frames": len(delivered["frames"]),
                    "gap": round(gap["max"], 3) if gap else 0.0,
                }
            )
        return out

    def coverage(self, video: str, start: float | None = None, end: float | None = None) -> dict:
        """What has been looked at in a span, how closely, and what has not been looked at at all.

        Args:
            video: Name or path of the video.
            start: Start of the span, in seconds. Leave out for the beginning.
            end: End of the span, in seconds. Leave out for the end of the video.

        Returns:
            {"looked": [{"start", "end", "gap", "id"}], "sheets": [{"id", "times"}], "never": [[start, end]]}.
            "gap" is the most seconds between two frames shown in that look: a small gap is a close look.
            A sheet shows separate instants, so it is listed apart and covers nothing in between.
        """
        source = self._source(video)
        low, high = (_f(t) for t in self._window(source, start, end))
        looked, sheets = [], []
        for record in self.project.log.observations(source.hash):
            base = Fraction(record["delivered"]["time_base"])
            times = [frame["pts"] * base for frame in record["delivered"]["frames"]]
            if record["recipe"]["level"] == "sheet":
                inside = sorted(_f(t) for t in times if low <= _f(t) <= high)
                sheets += [{"id": record["id"], "times": inside}] if inside else []
                continue
            a, b = max(low, min(_f(times[0]), _f(record["request"]["start"]))), min(high, max(_f(times[-1]), _f(record["request"]["end"])))
            if b >= a and not (b < low or a > high):
                gap = record["delivered"]["gap_seconds"]
                looked.append({"start": a, "end": b, "gap": round(gap["max"], 3) if gap else 0.0, "id": record["id"]})
        return {"looked": looked, "sheets": sheets, "never": spans.minus([low, high], [[s["start"], s["end"]] for s in looked])}

    # Building a clip

    def mark(self, video: str, start: float, end: float, reason: str = "", replaces: str | None = None) -> dict:
        """Save a span as a selection to use in a clip. It snaps to whole frames.

        The selection records which of your looks it rests on. If you never looked at its first or last
        frame, it is still saved and says so: look at the edge with focus "boundary", then mark again.

        Args:
            video: Name or path of the video.
            start: Where the selection starts, in seconds.
            end: Where it ends, in seconds. The frame showing at this time is the first one left out.
            reason: Why this span, in a few words. Kept with the selection.
            replaces: The id of an earlier selection this one corrects.

        Returns:
            {"id", "video", "start", "end", "frames", "edges_not_seen", "rests_on"}.
        """
        source = self._source(video)
        try:
            made = select.mark(self.project, source.path, start, end, reason, replaces)
        except (MediaError, ValueError) as error:
            raise ApiError(str(error)) from error
        return self._selection(made)

    @staticmethod
    def _selection(made: dict) -> dict:
        return {
            "id": made["id"],
            "video": Path(made["source"]["path"]).name,
            "start": _f(made["start"]),
            "end": _f(made["end"]),
            "frames": made["frames"],
            "reason": made["reason"],
            "edges_not_seen": made["edges_not_seen"],
            "rests_on": made["rests_on"],
        }

    def selections(self) -> list[dict]:
        """The selections saved so far, oldest first, leaving out any that a later one replaced."""
        return [self._selection(made) for made in select.selections(self.project)]

    def clip(self, selections: list[str], name: str) -> dict:
        """Cut selections, in the order given, into one video file with hard cuts. Frame-exact.

        The clip is then a video like any other: look at it with `observe`, by the name returned.

        Args:
            selections: Ids of selections, in the order they should play.
            name: A short name for the clip: letters, digits, "-" or "_".

        Returns:
            {"clip", "duration", "segments"}: the clip's file name, its length, and for each selection where
            it came from in its source and where it sits in the clip.
        """
        try:
            made = select.cut(self.project, selections, name)
        except (MediaError, ValueError) as error:
            raise ApiError(str(error)) from error
        parts = [
            {"selection": p["selection"], "video": p["video"], "source": [_f(t) for t in p["source"]], "clip": [_f(t) for t in p["clip"]]}
            for p in made["segments"]
        ]
        return {"clip": f"{made['name']}.mp4", "duration": _f(made["duration"]), "segments": parts}

    def verify(self, clip: str) -> dict:
        """Check a clip by code: it decodes, has the right number of frames, and each part starts and ends on the frame chosen.

        It also lists where the joins are, so you can look at them. Passing these checks does not mean the
        clip is good: look at it.

        Args:
            clip: The clip's name, as `clip` returned it.

        Returns:
            {"ok", "problems", "warnings", "duration", "joins", "next"}. "joins" are times in the clip.
        """
        try:
            return select.verify(self.project, clip)
        except (MediaError, ValueError) as error:
            raise ApiError(str(error)) from error

    # Spans

    expand = staticmethod(spans.expand)
    merge = staticmethod(spans.merge)
    minus = staticmethod(spans.minus)

    def reference(self) -> str:
        """The operations with their signatures, what each does and what it returns, generated from this class."""
        lines = []
        for name in self.OPERATIONS:
            function = getattr(self, name)
            parts = inspect.getdoc(function).split("\n\n")
            says = [parts[0].replace("\n", " ")]
            says += [" ".join(part.split()) for part in parts[1:] if part.startswith("Returns:")]
            lines.append(f"{name}{signature(function)}\n" + "\n".join(f"    {line}" for line in says))
        return "\n".join(lines)
