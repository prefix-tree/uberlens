"""The working file: the state of a task in one place, outside the model's context.

A host compacts an agent's context when it fills, and summaries silently lose rules: studies of coding
agents found about a third of a task's constraints gone after one round. So the brief is kept here word
for word, with what was concluded and chosen, and the file is rewritten after every step. An agent that
has lost its context reads this file and carries on.
"""

from __future__ import annotations

from fractions import Fraction
from pathlib import Path

NAME = "WORKING.md"
LIMIT = 12_000  # characters; older looks without a note are counted, not listed
RECENT = 12  # looks without a note that are still listed


def _clock(value: str) -> str:
    seconds = float(Fraction(value))
    return f"{int(seconds // 60)}:{seconds % 60:06.3f}"


def _look(record: dict, note: str | None) -> str:
    request, name = record["request"], Path(record["source"]["path"]).name
    span = _clock(request["start"]) if request["start"] == request["end"] else f"{_clock(request['start'])} to {_clock(request['end'])}"
    said = f'note: "{note}"' if note else "no note"
    asked = f" (asked: {request['purpose']})" if request["purpose"] else ""
    return f"- {record['id']} · {name} · {span} · {request['focus']}{asked} · {said}"


def render(log) -> str:
    brief, notes = log.brief(), log.notes()
    looks, selections, clips = log.observations(), log.selections(), log.clips()
    replaced = {s["replaces"] for s in selections if s.get("replaces")}
    lines = [
        "# Working state",
        "",
        "Kept by UberSeek and rewritten after every step. If your context was shortened, this is where things stand.",
        "",
        "## The brief, word for word",
        "",
        brief if brief else "Not recorded. Record the task exactly as given with `brief`, so its requirements survive.",
        "",
        f"## Selections ({len([s for s in selections if s['id'] not in replaced])})",
        "",
    ]
    for selection in selections:
        if selection["id"] in replaced:
            continue
        unseen = f"; {' and '.join(selection['edges_not_seen'])} point not looked at" if selection["edges_not_seen"] else ""
        span = f"{_clock(selection['start'])} to {_clock(selection['end'])}"
        lines.append(
            f"- {selection['id']} · {Path(selection['source']['path']).name} · {span} · {selection['reason'] or 'no reason given'}{unseen}"
        )
    lines += ["", f"## Clips ({len(clips)})", ""]
    for clip in clips:
        parts = ", ".join(part["selection"] for part in clip["segments"])
        lines.append(f"- {clip['name']}.mp4 · {float(Fraction(clip['duration'])):.3f} s · from {parts}")

    noted = [record for record in looks if record["id"] in notes]
    plain = [record for record in looks if record["id"] not in notes]
    lines += ["", f"## What was concluded ({len(noted)} looks with a note)", ""]
    lines += [_look(record, notes[record["id"]]) for record in reversed(noted)]
    lines += ["", f"## Looks without a note ({len(plain)}; the last {min(RECENT, len(plain))} listed)", ""]
    lines += [_look(record, None) for record in reversed(plain[-RECENT:])]
    lines += [
        "",
        "Any look can be shown again by its id. A picture can be recovered; what you concluded from it cannot, unless it is in a note.",
    ]
    text = "\n".join(lines)
    if len(text) > LIMIT:  # the brief and the choices come first, so what is cut is the oldest of the looks
        text = text[:LIMIT].rsplit("\n", 1)[0] + "\n- (older entries left out; `observations` lists them all)"
    return text + "\n"


def write(log) -> None:
    (log.root / NAME).write_text(render(log))
