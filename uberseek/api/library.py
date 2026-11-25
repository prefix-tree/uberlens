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
from uberseek.state import working
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
        "info", "find", "words", "gaps", "repeats", "pauses", "loudness", "onsets", "cuts", "shots", "change", "events",
        "freezes", "observe", "sheet", "overview", "seam", "observations", "coverage", "expand", "merge", "minus", "every",
        "mark", "selections", "clip", "verify", "note", "brief", "status", "videos",
    )  # fmt: skip

    LOOKS = ("observe", "sheet", "overview", "seam")  # the operations that show a picture

    def __init__(self, project: Project, videos: list[Path | str] | None = None):
        self.project = project
        self.allowed = {Path(v).name: Path(v) for v in videos} if videos is not None else None
        self.looks: list[Observation] = []  # pictures made by `observe`, for whoever delivers them to the model

    # Sources

    def _source(self, video: str) -> Source:
        made = select.clips_folder(self.project) / Path(video).name
        if self.allowed is None:
            path = made if not Path(video).exists() and made.exists() else Path(video)  # a clip is known by its name
        elif Path(video).name in self.allowed:
            path = self.allowed[Path(video).name]
        elif made.exists():
            path = made  # a clip cut in this project is a video like any other
        else:
            raise ApiError(f"no video named {video!r}. Available: {', '.join(self.allowed) or 'none'}")
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

    def gaps(self, video: str, start: float, end: float, shortest: float = 0.15) -> list[list[float]]:
        """The gaps between words in a span, as [start, end] pairs: where nobody is speaking, by the transcript.

        Unlike `pauses`, this works when music or noise runs under the speech, because it does not need
        silence. It is an estimate: an edge can be a few tenths of a second off.

        Args:
            video: Name or path of the video.
            start: Start of the span, in seconds.
            end: End of the span, in seconds.
            shortest: The shortest gap to report, in seconds.
        """
        said = self.words(video, start, end)
        return [[a["end"], b["start"]] for a, b in zip(said, said[1:], strict=False) if b["start"] - a["end"] >= shortest]

    def repeats(self, video: str, start: float, end: float) -> list[dict]:
        """Words or phrases said twice in a row in a span: a stumble, a restart, a repeated take.

        From the transcript, so it finds only what the transcript wrote down; a speech model often leaves
        out a stutter. Each result gives the span of both sayings, so cutting `first` leaves one.

        Args:
            video: Name or path of the video.
            start: Start of the span, in seconds.
            end: End of the span, in seconds.

        Returns:
            A list of {"text", "first": [start, end], "second": [start, end]}, in time order.
        """
        said = self.words(video, start, end)
        plain = ["".join(c for c in w["text"].lower() if c.isalnum()) for w in said]
        found, used = [], set()
        for size in (4, 3, 2, 1):
            for i in range(len(said) - 2 * size + 1):
                if (
                    plain[i : i + size] == plain[i + size : i + 2 * size]
                    and all(plain[i : i + size])
                    and not used & set(range(i, i + 2 * size))
                ):
                    used |= set(range(i, i + 2 * size))
                    first, second = said[i : i + size], said[i + size : i + 2 * size]
                    found.append(
                        {
                            "text": " ".join(w["text"].strip() for w in first),
                            "first": [first[0]["start"], first[-1]["end"]],
                            "second": [second[0]["start"], second[-1]["end"]],
                        }
                    )
        return sorted(found, key=lambda r: r["first"])

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

    def onsets(self, video: str, start: float | None = None, end: float | None = None, rise: float = 10) -> list[float]:
        """Instants where the sound gets suddenly louder: a hit, a beat, a word after a silence. Measured.

        Use it to see whether cuts follow the music, or to put a cut on a beat.

        Args:
            video: Name or path of the video.
            start: Start of the span, in seconds. Leave out for the beginning.
            end: End of the span, in seconds. Leave out for the end of the video.
            rise: How many decibels louder than the moment before. Lower finds more.
        """
        source = self._source(video)
        if source.info.audio is None:
            return []
        low, high = self._window(source, start, end)
        found = self.project.log.derived(source.hash, "onsets", lambda: signals.onsets(source.path))
        return [_f(t) for t, by in found["points"] if by >= rise and low <= Fraction(t) <= high]

    def _frames(self, source: Source, start: float | None, end: float | None) -> range:
        low, high = self._window(source, start, end)
        return range(max(1, source.index.position(low)), source.index.position(high) + 1)

    def change(self, video: str, start: float, end: float) -> list[list[float]]:
        """How much each frame in a span differs from the frame before it, as [time, whole, part] triples.

        `whole` is the mean difference over the frame (0 to 255): near zero means the frame repeats the one
        before. `part` is the largest difference in any one of 24 parts of the frame, so a change in a
        corner shows there. The first use on a video decodes all of it once.

        Args:
            video: Name or path of the video.
            start: Start of the span, in seconds.
            end: End of the span, in seconds.
        """
        source = self._source(video)
        whole, part, _ = self.project.change(source)
        at = source.index
        return [[_f(at.time(at.frames[p].pts)), whole[p], part[p]] for p in self._frames(source, start, end)]

    def events(self, video: str, start: float | None = None, end: float | None = None) -> list[dict]:
        """Instants where the picture changes abruptly, in the whole frame or in part of it. Measured.

        Finds what `cuts` cannot: a picture appearing in one part of the frame, a title popping on, a
        single flash frame. Each event is the first frame that differs. Ordinary motion is not an event.

        Args:
            video: Name or path of the video.
            start: Start of the span, in seconds. Leave out for the beginning.
            end: End of the span, in seconds. Leave out for the end of the video.

        Returns:
            A list of {"time", "frame", "amount", "area", "where", "kind"}. `area` is the share of the frame
            that changed, `where` its [left, top, right, bottom] as fractions of the frame (usable as a
            region), and `kind` is "whole", "part", or "flash" for one frame unlike both its neighbours.
        """
        source = self._source(video)
        _, part, grid = self.project.change(source)
        rows, columns, at = signals.CHANGE["rows"], signals.CHANGE["columns"], source.index
        found: list[dict] = []
        for p in self._frames(source, start, end):
            near = sorted(part[max(0, p - 15) : p] + part[p + 1 : p + 16])
            usual = near[len(near) // 2] if near else 0  # what is usual nearby; other events in the window do not move a median
            if part[p] < max(2 * signals.EVENT, 4 * usual + 4):  # twice what counts as changed, and well above what is usual here
                continue
            if found and found[-1]["frame"] == p - 1:
                found[-1]["kind"] = "flash"  # it differed from the frame before, and this one differs from it
                continue
            cells = [i for i, v in enumerate(grid[p]) if v >= max(signals.EVENT, part[p] // 3)]
            across, down = [i % columns for i in cells], [i // columns for i in cells]
            where = [min(across) / columns, min(down) / rows, (max(across) + 1) / columns, (max(down) + 1) / rows]
            area = len(cells) / (rows * columns)
            found.append(
                {
                    "time": _f(at.time(at.frames[p].pts)),
                    "frame": p,
                    "amount": part[p],
                    "area": round(area, 2),
                    "where": [round(v, 3) for v in where],
                    "kind": "whole" if area >= 0.6 else "part",
                }
            )
        return found

    def freezes(self, video: str, start: float | None = None, end: float | None = None, shortest: int = 3) -> list[dict]:
        """Stretches where the picture stops: each frame repeats the one before it. Measured.

        For a stuck or duplicated stretch, or a still. To remove the repeats and keep one frame, cut from
        `start` to `end`: the frame before `start` is the one that was held.

        Args:
            video: Name or path of the video.
            start: Start of the span, in seconds. Leave out for the beginning.
            end: End of the span, in seconds. Leave out for the end of the video.
            shortest: The fewest repeated frames in a row that count. Footage at a lower frame rate than its
                file repeats single frames all the time; three in a row is a stop.

        Returns:
            A list of {"start", "end", "first_frame", "frames"}: the time of the first repeated frame, the
            time of the first frame that moves again, the first repeated frame's number counted from 0, and
            how many frames repeat.
        """
        source = self._source(video)
        whole, _, _ = self.project.change(source)
        at, found = source.index, []
        frames = list(self._frames(source, start, end))
        still = [whole[p] < signals.STILL for p in frames]
        for i in range(1, len(frames) - 1):  # one noisy frame between two that repeat does not end a stop
            if not still[i] and whole[frames[i]] < signals.NEARLY and still[i - 1] and whole[frames[i + 1]] < signals.STILL:
                still[i] = True
        run: list[int] = []
        for p, stopped in [*zip(frames, still, strict=True), (None, False)]:
            if stopped:
                run.append(p)
                continue
            if len(run) >= shortest:
                after = run[-1] + 1
                ends = at.time(at.frames[after].pts) if after < len(at.frames) else max(source.info.duration, at.end)
                found.append({"start": _f(at.time(at.frames[run[0]].pts)), "end": _f(ends), "first_frame": run[0], "frames": len(run)})
            run = []
        return found

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

    def observe(
        self,
        video: str,
        start: float,
        end: float | None = None,
        focus: str = "visual",
        purpose: str = "",
        region: list[float] | None = None,
    ) -> dict:
        """Look at a span. The picture is shown to you after the program ends; a program cannot see it.

        You choose the span and the focus; how many frames and how large is chosen for you.

        Args:
            video: Name or path of the video.
            start: Start of the span, in seconds.
            end: End of the span. Leave out to see the single frame showing at `start`.
            focus: visual (what is in the picture), motion (dense frames), speech or delivery (sound and
                pauses, a few frames), boundary (frames and sound right around one instant), change (the
                frames where the picture changes most, each with the frame before it).
            purpose: The question this look should answer, in a few words. Kept in the log.
            region: The part of the frame to show, as [left, top, right, bottom] in fractions of its width
                and height: [0, 0.5, 1, 1] is the lower half. The part is shown larger. Leave out for all of it.

        Returns:
            {"id", "text"}: the observation's id and the statement of what it shows.
        """
        source = self._source(video)
        try:
            seen = self.project.observe(source.path, start, end, focus, purpose, region)
        except (MediaError, ValueError) as error:
            raise ApiError(str(error)) from error
        self.looks.append(seen)
        return {"id": seen.id, "text": seen.text}

    def sheet(
        self, video: str, times: list[float], labels: list[str] | None = None, purpose: str = "", region: list[float] | None = None
    ) -> dict:
        """Show frames from anywhere in a video as one picture, like a plot: one frame per time you give.

        Use it to scan or compare many places at the cost of one look: one frame per shot, one per
        candidate. The frames are small and are separate instants, so look closer at the one that matters
        with `observe`. The picture is shown to you after the program ends; a program cannot see it.

        Args:
            video: Name or path of the video.
            times: The instants to show, in seconds, in the order to draw them. At most 48. For a dense run
                at a steady rate, `every(start, end, step)` makes the list.
            labels: A short label to print under each frame, one per time (a rank, a length, a few words).
            purpose: The question this sheet should answer, in a few words. Kept in the log.
            region: The part of the frame to show, as [left, top, right, bottom] in fractions of its width
                and height. Leave out for all of it.

        Returns:
            {"id", "text"}: the observation's id and the statement of what it shows.
        """
        source = self._source(video)
        try:
            seen = self.project.sheet(source.path, times, labels, purpose, region)
        except (MediaError, ValueError) as error:
            raise ApiError(str(error)) from error
        self.looks.append(seen)
        return {"id": seen.id, "text": seen.text}

    def _board(self, items: list[tuple], columns: int, title: str, purpose: str) -> dict:
        try:
            seen = self.project.board(items, columns, title, purpose)
        except (MediaError, ValueError) as error:
            raise ApiError(str(error)) from error
        self.looks.append(seen)
        return {"id": seen.id, "text": seen.text}

    def overview(self, videos: list[str], per: int = 3, purpose: str = "") -> dict:
        """Show several videos on one picture: a few frames of each, in a row, with the video's name under each.

        For comparing clips, putting them in order, or matching them to descriptions, at the cost of one
        look where one look per clip would not fit in your context. Frames are spread from each video's
        first frame to its last. Every frame is drawn in the shape of the first video.

        Args:
            videos: Names or paths of the videos, in the order to draw them.
            per: How many frames of each video: 1 is its middle, 2 its first and last, 3 adds the middle.
                Videos times frames is at most 48.
            purpose: The question this picture should answer, in a few words. Kept in the log.

        Returns:
            {"id", "text"}: the observation's id and the statement of what it shows.
        """
        if not videos or per < 1:
            raise ApiError("overview needs at least one video and at least one frame of each")
        items = []
        for video in videos:
            source = self._source(video)
            last, at = len(source.index.frames) - 1, source.index
            spots = [last // 2] if per == 1 else [round(k * last / (per - 1)) for k in range(per)]
            items += [(source.path, at.time(at.frames[p].pts), f"{source.path.name} · {k}/{per}") for k, p in enumerate(spots, 1)]
        shape = self._source(videos[0]).info.video
        beside = max(1, round((len(items) * shape.height / shape.width * 4 / 3) ** 0.5 / per))  # videos side by side in a row
        return self._board(
            items, beside * per, f"{len(videos)} videos · {per} frame{'s' if per > 1 else ''} of each, first to last", purpose
        )

    def seam(self, first: str, second: str, frames: int = 3, purpose: str = "") -> dict:
        """Show how one video would run into another: the last frames of the first beside the first frames of the second.

        For judging whether two clips follow each other, or how a cut between them would look, before
        joining anything.

        Args:
            first: Name or path of the video that comes first.
            second: Name or path of the video that follows it.
            frames: How many consecutive frames of each to show, from 1 to 6.
            purpose: The question this picture should answer, in a few words. Kept in the log.

        Returns:
            {"id", "text"}: the observation's id and the statement of what it shows.
        """
        if not 1 <= frames <= 6:
            raise ApiError("seam shows from 1 to 6 frames of each video")
        a, b = self._source(first), self._source(second)
        items = []
        for back in range(min(frames, len(a.index.frames)) - 1, -1, -1):
            pts = a.index.frames[len(a.index.frames) - 1 - back].pts
            items.append((a.path, a.index.time(pts), f"{a.path.name} · {'last' if back == 0 else str(back) + ' before last'}"))
        for ahead in range(min(frames, len(b.index.frames))):
            label = f"{b.path.name} · {'first' if ahead == 0 else str(ahead) + ' after first'}"
            items.append((b.path, b.index.time(b.index.frames[ahead].pts), label))
        return self._board(items, len(items), f"{a.path.name} then {b.path.name} · the frames on each side of the join", purpose)

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
        out, notes = [], self.project.log.notes()
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
                    "note": notes.get(record["id"]),
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

    # Keeping track

    def note(self, observation: str, text: str) -> dict:
        """Write down what you concluded from a look, in a sentence. Pictures leave your context; notes stay.

        A picture can always be shown again. What you concluded from it cannot be recovered unless it is
        written here. Notes appear in `status` and in `observations`.

        Args:
            observation: The id of the look, like obs_000012.
            text: What you concluded, in a sentence: what is there, and what it means for the task.
        """
        try:
            self.project.log.get(observation)
        except (KeyError, ValueError) as error:
            raise ApiError(f"no observation {observation!r}: give the id of a look you made") from error
        self.project.log.append_note({"observation": observation, "text": str(text)[:500]})
        return {"observation": observation, "noted": True}

    def brief(self, text: str) -> dict:
        """Record the task exactly as it was given, so its requirements survive a shortened context.

        Copy the request word for word: lengths, formats, file names, what must and must not be in the
        result. Do not summarise it. It is shown at the top of `status`.

        Args:
            text: The task, word for word.
        """
        self.project.log.append_brief({"text": str(text)})
        return {"recorded": True, "characters": len(str(text))}

    def status(self) -> str:
        """Where the task stands: the brief word for word, the selections, the clips, and what each look concluded.

        Read it when you are unsure what you have already done, or after your context was shortened.
        """
        return working.render(self.project.log)

    def videos(self) -> list[dict]:
        """The videos you can use, and the clips made so far: length, size, and what is prepared for each."""
        made = sorted(select.clips_folder(self.project).glob("*.mp4"))
        names = [*(self.allowed or {}), *(path.name for path in made)]
        return [self.info(name) for name in dict.fromkeys(names)]

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
    every = staticmethod(spans.every)

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
