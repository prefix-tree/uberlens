"""Selections and clips.

A selection is a span chosen for use, pinned to the file version it was chosen from and to the looks it
rests on. A clip is selections cut one after another into a file, with a map from source time to clip
time. `verify` checks the file by code. None of this judges whether the clip is good.
"""

from __future__ import annotations

import re
from fractions import Fraction
from pathlib import Path

from uberseek.media import MediaError, Segment
from uberseek.observe.gateway import Project, Source, _fraction
from uberseek.timecode import Seconds, clock, seconds

NEAR = Fraction(1, 2)  # a look counts for an edge when it shows a frame within this many seconds of it
COMPARE = (96, 54)  # frames are compared at this size
ALIKE = 25.0  # mean difference per channel, of 255, above which a frame is not the picture chosen
NEXT = "These checks do not say the clip is good. Look at it: a boundary look at each join, and at its start and end. Sound is not heard."
SLACK = 0.5  # a neighbouring frame must match better by more than this to count as the closer one


def clips_folder(project: Project) -> Path:
    folder = project.log.root / "clips"
    folder.mkdir(exist_ok=True)
    return folder


def _looks(project: Project, source: Source) -> list[tuple[str, list[Seconds]]]:
    out = []
    for record in project.log.observations(source.hash):
        base = Fraction(record["delivered"]["time_base"])
        out.append((record["id"], [frame["pts"] * base for frame in record["delivered"]["frames"]]))
    return out


def mark(project: Project, path: Path | str, start, end, reason: str = "", replaces: str | None = None) -> dict:
    """Save a span as a selection. It runs from the frame showing at `start` up to the frame showing at `end`."""
    source = project.open(path)
    index, frames = source.index, source.index.frames
    first, stop = index.position(seconds(start)), index.position(seconds(end))
    if seconds(end) > index.time(frames[-1].pts):  # past the last frame: keep it
        stop = len(frames)
    if stop <= first:
        raise ValueError(f"the selection would hold no frames: it ends ({end}) at or before it starts ({start})")
    tail = frames[-1].pts + (frames[-1].pts - frames[-2].pts if len(frames) > 1 else 1)
    in_pts, out_pts = frames[first].pts, frames[stop].pts if stop < len(frames) else tail
    begins, last_shown = index.time(in_pts), index.time(frames[stop - 1].pts)

    looks = _looks(project, source)
    rests_on = [id for id, times in looks if any(begins <= t <= last_shown for t in times)]
    seen = {
        "in": any(abs(t - begins) <= NEAR for _, times in looks for t in times),
        "out": any(abs(t - last_shown) <= NEAR for _, times in looks for t in times),
    }
    return project.log.append_selection(
        {
            "source": {"hash": source.hash, "path": str(source.path)},
            "time_base": _fraction(index.time_base),
            "in_pts": in_pts,
            "out_pts": out_pts,
            "start": _fraction(begins),
            "end": _fraction(index.time(out_pts)),
            "frames": stop - first,
            "reason": reason,
            "rests_on": rests_on,
            "edges_not_seen": [edge for edge, was in seen.items() if not was],
            "heard": False,
            "replaces": replaces,
        }
    )


def selections(project: Project) -> list[dict]:
    """The selections in force: every one that no later selection replaces."""
    every = project.log.selections()
    replaced = {s["replaces"] for s in every if s.get("replaces")}
    return [s for s in every if s["id"] not in replaced]


def cut(project: Project, ids: list[str], name: str) -> dict:
    """Cut selections, in the order given, into one clip. Refuses a source that has changed since it was selected."""
    if not ids:
        raise ValueError("a clip needs at least one selection")
    if not re.fullmatch(r"[A-Za-z0-9][A-Za-z0-9_-]{0,60}", name):
        raise ValueError(f"the name {name!r} must be letters, digits, '-' or '_', and at most 61 characters")
    known = {s["id"]: s for s in project.log.selections()}
    if missing := [id for id in ids if id not in known]:
        raise ValueError(f"no selection {missing[0]}. Selections: {', '.join(known) or 'none yet; make one with mark'}")
    chosen, segments, sources = [known[id] for id in ids], [], []
    for selection in chosen:
        source = project.open(selection["source"]["path"])
        if source.hash != selection["source"]["hash"]:
            raise ValueError(f"{source.path.name} has changed since {selection['id']} was selected; select again from the new file")
        sources.append(source)
        segments.append(Segment(source.path, source.index, selection["in_pts"], selection["out_pts"]))

    sound = all(source.info.audio is not None for source in sources)
    width, height = sources[0].info.video.width, sources[0].info.video.height
    out = clips_folder(project) / f"{name}.mp4"
    command = project.backend.join(segments, out, (width - width % 2, height - height % 2), sound)

    at, parts = Fraction(0), []
    for selection in chosen:
        length = Fraction(selection["end"]) - Fraction(selection["start"])
        parts.append(
            {
                "selection": selection["id"],
                "video": Path(selection["source"]["path"]).name,
                "source": [selection["start"], selection["end"]],
                "clip": [_fraction(at), _fraction(at + length)],
                "frames": selection["frames"],
            }
        )
        at += length
    made = project.open(out)
    return project.log.append_clip(
        {
            "name": name,
            "path": str(out),
            "hash": made.hash,
            "duration": _fraction(at),
            "sound": sound,
            "segments": parts,
            "command": command,
        }
    )


def _difference(a: bytes, b: bytes) -> float:
    return sum(abs(x - y) for x, y in zip(a, b, strict=True)) / len(a)


def _wrong_frame(project: Project, clip: Source, in_clip: int, source: Source, in_source: int) -> str | None:
    """Is the clip's frame the source frame it should be? Says what is wrong, or nothing.

    Encoding again changes pixels a little, so equality cannot be asked for. The frame must look like the one
    chosen, and no less like it than like the frame before or after: that catches a cut one frame off.
    """
    frames = source.index.frames
    near = [i for i in (in_source - 1, in_source, in_source + 1) if 0 <= i < len(frames)]
    (got,) = project.backend.frames(clip.path, clip.index, [clip.index.frames[in_clip].pts], COMPARE)
    wanted = project.backend.frames(source.path, source.index, [frames[i].pts for i in near], COMPARE)
    apart = {i: _difference(got.rgb, frame.rgb) for i, frame in zip(near, wanted, strict=True)}
    at = clock(source.index.time(frames[in_source].pts))
    if apart[in_source] > ALIKE:
        return f"is not the frame chosen at {at} (difference {apart[in_source]:.0f} of 255)"
    closest = min(apart, key=apart.get)
    if apart[closest] + SLACK < apart[in_source]:
        return f"is the frame {'before' if closest < in_source else 'after'} the one chosen at {at}"
    return None


def _clip(project: Project, name: str) -> dict:
    name = name.removesuffix(".mp4")
    made = [c for c in project.log.clips() if c["name"] == name]
    if not made:
        raise ValueError(f"no clip named {name!r}. Clips: {', '.join(sorted({c['name'] for c in project.log.clips()})) or 'none yet'}")
    return made[-1]


def verify(project: Project, name: str) -> dict:
    """Check a clip by code: it decodes, has its streams, has the right frames, and starts and ends each part on the frame chosen.

    These checks say the file is what was asked for. They do not say the clip is good.
    """
    record = _clip(project, name)
    path, problems, warnings = Path(record["path"]), [], []
    known = {s["id"]: s for s in project.log.selections()}
    try:
        clip = project.open(path)
    except (MediaError, FileNotFoundError) as error:
        return {"clip": path.name, "ok": False, "problems": [f"the clip cannot be opened: {error}"], "warnings": [], "joins": []}
    if clip.hash != record["hash"]:
        problems.append("the file is not the one that was cut: its content has changed")
    problems += [f"it does not decode cleanly: {line}" for line in project.backend.decodes(path)]
    if record["sound"] and clip.info.audio is None:
        problems.append("it has no sound, and its sources do")

    wanted = sum(part["frames"] for part in record["segments"])
    if len(clip.index.frames) != wanted:
        problems.append(f"it has {len(clip.index.frames)} frames, and the selections hold {wanted}")
    else:
        position = 0
        for part in record["segments"]:
            selection = known[part["selection"]]
            try:
                source = project.open(selection["source"]["path"])
            except (MediaError, FileNotFoundError):
                warnings.append(f"{part['selection']}: its source is gone, so its frames were not compared")
                position += part["frames"]
                continue
            if source.hash != selection["source"]["hash"]:
                warnings.append(f"{part['selection']}: its source has changed since, so its frames were not compared")
                position += part["frames"]
                continue
            first = source.index.position(Fraction(selection["start"]))
            last = first + part["frames"] - 1
            for edge, in_clip, in_source in (("first", position, first), ("last", position + part["frames"] - 1, last)):
                if wrong := _wrong_frame(project, clip, in_clip, source, in_source):
                    problems.append(f"{part['selection']}: its {edge} frame in the clip {wrong}")
            position += part["frames"]

    for part in record["segments"]:
        for edge in known[part["selection"]]["edges_not_seen"]:
            warnings.append(f"{part['selection']}: its {edge} point was chosen without a look at it")
    joins = [float(Fraction(part["clip"][1])) for part in record["segments"][:-1]]
    return {
        "clip": path.name,
        "ok": not problems,
        "problems": problems,
        "warnings": warnings,
        "duration": round(float(Fraction(record["duration"])), 3),
        "joins": [round(t, 3) for t in joins],
        "next": NEXT,
    }


def export(project: Project, name: str) -> dict:
    """A clip as data: its selections with their reasons and the looks behind them, and the command that cut it."""
    record = _clip(project, name)
    known = {s["id"]: s for s in project.log.selections()}
    parts = []
    for part in record["segments"]:
        selection = known[part["selection"]]
        parts.append(
            part | {"reason": selection["reason"], "rests_on": selection["rests_on"], "edges_not_seen": selection["edges_not_seen"]}
        )
    return {
        "name": record["name"],
        "file": record["path"],
        "duration": record["duration"],
        "sound": record["sound"],
        "segments": parts,
        "command": record["command"],
    }
