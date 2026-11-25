"""A small command line, for trying the observation contract by hand."""

from __future__ import annotations

import argparse
import json
import re
import sys
from fractions import Fraction
from pathlib import Path

from uberseek import Project, guide, select
from uberseek.api import ApiError, Library
from uberseek.media import MediaError
from uberseek.observe.plan import FOCUSES
from uberseek.state import working
from uberseek.timecode import clock, seconds

VIDEO = {".mp4", ".mov", ".mkv", ".webm", ".m4v", ".avi", ".ts", ".mxf"}
COMMANDS = ("observe", "reproduce", "transcript", "find", "run", "guide", "skill", "selections", "clip", "verify")
COMMANDS += ("export", "note", "brief", "status", "log")
PLAIN = tuple(name for name in Library.OPERATIONS if name not in COMMANDS)  # operations with no command written for them


def here() -> list[Path]:
    """The video files in the current folder: what a program or `videos` may use when none is named."""
    return sorted(path for path in Path.cwd().iterdir() if path.suffix.lower() in VIDEO)


def value(text: str):
    """One argument of an operation given on the command line: a number, a JSON list, a clock time or a word."""
    try:
        return json.loads(text)
    except ValueError:
        if text in ("None", "none", "null", "-"):
            return None  # an argument left out on purpose
        return float(seconds(text)) if re.fullmatch(r"\d+(:\d+)+(\.\d+)?", text) else text


FLAGS = {"observe": ("focus", "purpose", "out", "region"), "find": ("limit",)}  # commands whose named arguments are flags


def one_style(argv: list[str]) -> list[str]:
    """Let a named argument be written either way everywhere: `--reason "x"` or `reason="x"`."""
    at = 2 if argv[:1] == ["--project"] else 0
    command, out = (argv[at] if len(argv) > at else ""), argv[: at + 1]
    rest = argv[at + 1 :]
    while rest:
        word = rest.pop(0)
        if command in PLAIN and word.startswith("--") and rest and len(word) > 2:
            out.append(f"{word[2:].replace('-', '_')}={rest.pop(0)}")
        elif command in FLAGS and "=" in word and word.split("=", 1)[0] in FLAGS[command]:
            out += [f"--{word.split('=', 1)[0]}", word.split("=", 1)[1]]
        else:
            out.append(word)
    return out


def plain(project: Project, name: str, given: list[str]) -> int:
    """Run one operation as written: `uberseek pauses talk.mp4 50 60`, `uberseek find talk.mp4 moon limit=3`."""
    named = {a.split("=", 1)[0]: value(a.split("=", 1)[1]) for a in given if re.match(r"[a-z_]+=", a)}
    library = Library(project, here()) if name == "videos" else Library(project)
    result = getattr(library, name)(*[value(a) for a in given if not re.match(r"[a-z_]+=", a)], **named)
    print(result["text"] if name in Library.LOOKS else result if isinstance(result, str) else json.dumps(result))
    for seen in library.looks:
        print(f"Picture: {(project.log.root / 'artifacts' / (seen.record['artifact']['sha256'] + '.png')).resolve()}")
    return 0


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="uberseek", description="Measure and look inside video files. `uberseek guide` explains it.")
    parser.add_argument("--project", default=".", help="folder that holds the log (default: here)")
    commands = parser.add_subparsers(dest="command", required=True)

    observe = commands.add_parser("observe", help="show a span of a video as one picture")
    observe.add_argument("video")
    observe.add_argument("start", help="seconds or H:MM:SS.mmm")
    observe.add_argument("end", nargs="?", help="leave out for a single frame")
    observe.add_argument("--focus", choices=FOCUSES, default="visual")
    observe.add_argument("--purpose", default="", help="what the look is for")
    observe.add_argument("--out", help="also write the picture here")
    observe.add_argument("--region", type=json.loads, help="the part of the frame to show: '[left, top, right, bottom]' as fractions")

    reproduce = commands.add_parser("reproduce", help="make a logged observation again and compare")
    reproduce.add_argument("id", nargs="*", help="observation ids (default: all)")

    transcribe = commands.add_parser("transcript", help="transcribe a video once; later looks show its words")
    transcribe.add_argument("video")

    find = commands.add_parser("find", help="find where words are said, as JSON")
    find.add_argument("video")
    find.add_argument("query")
    find.add_argument("--limit", type=int, default=8)

    run = commands.add_parser("run", help="run a program against the library; prints its result and its pictures")
    run.add_argument("program", help="a file with the program, or - for standard input")
    run.add_argument("--video", action="append", help="a video the program may use (repeat for more; default: those in this folder)")

    read = commands.add_parser("guide", help="print the UberSeek skill, or one part of it")
    read.add_argument("topic", nargs="?", choices=guide.TOPICS)

    skill = commands.add_parser("skill", help="install the skill where an agent will find it")
    skill.add_argument("action", choices=["install"])
    skill.add_argument("folder", nargs="?", default=".claude/skills")

    commands.add_parser("selections", help="list the selections saved so far")

    clipping = commands.add_parser("clip", help="cut selections into one video file")
    clipping.add_argument("given", nargs="+", help="a name for the clip, and the selection ids in the order they should play")

    checking = commands.add_parser("verify", help="check a clip by code, and list where its joins are")
    checking.add_argument("name")

    exporting = commands.add_parser("export", help="print a clip as data: selections, reasons and the command that cut it")
    exporting.add_argument("name")

    noting = commands.add_parser("note", help="write down what a look showed; notes outlive the picture")
    noting.add_argument("observation")
    noting.add_argument("text")

    briefing = commands.add_parser("brief", help="record the task word for word (text, or - to read standard input)")
    briefing.add_argument("text")

    commands.add_parser("status", help="where the task stands: brief, selections, clips and what each look concluded")

    log = commands.add_parser("log", help="list observations")
    log.add_argument("--json", action="store_true")

    for name in PLAIN:
        doc = (getattr(Library, name).__doc__ or "").strip().splitlines()[0]
        commands.add_parser(name, help=doc).add_argument(
            "given", nargs="*", help="the operation's arguments, in order; name=value for a named one"
        )

    args = parser.parse_args(one_style(list(sys.argv[1:] if argv is None else argv)))
    if args.command == "guide":
        print(guide.topic(args.topic) if args.topic else guide.core("shell"))
        return 0
    if args.command == "skill":
        print(f"Installed: {guide.install(Path(args.folder))}")
        return 0
    project = Project(args.project)
    try:
        if args.command == "observe":
            seen = Library(project)._source(args.video)  # so a clip opens by its name
            seen = project.observe(
                seen.path,
                args.start,
                None if args.end in ("None", "none", "null", "-") else args.end,
                args.focus,
                args.purpose,
                args.region,
            )
            print(seen.text)
            path = project.log.root / "artifacts" / f"{seen.record['artifact']['sha256']}.png"
            if args.out:
                path = Path(args.out)
                path.write_bytes(seen.image)
            print(f"Picture: {path}")
        elif args.command == "find":
            print(json.dumps(Library(project, [args.video]).find(Path(args.video).name, args.query, limit=args.limit), indent=1))
        elif args.command == "run":
            from uberseek.exec import Executor

            program = sys.stdin.read() if args.program == "-" else Path(args.program).read_text()
            done = Executor(project, args.video or here()).run_sync(program)
            print(done.text)
            for seen in done.looks:
                print(f"Picture: {project.log.root / 'artifacts' / (seen.record['artifact']['sha256'] + '.png')}")
            return 1 if done.error else 0
        elif args.command == "selections":
            print(json.dumps(Library(project).selections(), indent=1))
        elif args.command == "clip":
            ids = [word for word in args.given if re.fullmatch(r"sel_\d+", word)]
            names = [word for word in args.given if word not in ids]
            if len(names) != 1 or not ids:
                raise ValueError(
                    "clip takes one name for the clip and the ids of the selections to join, like: clip answer sel_000001 sel_000002"
                )
            made = Library(project).clip(ids, names[0])
            print(json.dumps(made, indent=1))
            print(f"File: {select.clips_folder(project) / made['clip']}")
        elif args.command == "verify":
            checked = select.verify(project, args.name)
            print(json.dumps(checked, indent=1))
            return 0 if checked["ok"] else 1
        elif args.command == "export":
            print(json.dumps(select.export(project, args.name), indent=1))
        elif args.command == "note":
            Library(project).note(args.observation, args.text)
            print(f"Noted on {args.observation}.")
        elif args.command == "brief":
            Library(project).brief(sys.stdin.read() if args.text == "-" else args.text)
            print(f"Recorded. It is kept word for word in {project.log.root / working.NAME}.")
        elif args.command == "status":
            print(Library(project).status(), end="")
        elif args.command == "transcript":
            words = project.transcribe(args.video)["words"]
            print(" ".join(f"[{clock(Fraction(w[0]))}] {w[2]}" if i % 12 == 0 else w[2] for i, w in enumerate(words)))
        elif args.command == "reproduce":
            ids = args.id or [record["id"] for record in project.log.observations()]
            failed = 0
            for id in ids:
                again = project.reproduce(id)
                failed += not again.exact
                print(f"{id}: {'exact' if again.exact else 'DIFFERS: ' + '; '.join(again.notes)}")
            return 1 if failed else 0
        elif args.command in PLAIN:
            return plain(project, args.command, args.given)
        else:
            for record in project.log.observations():
                print(json.dumps(record) if args.json else project.show(record["id"]).text.splitlines()[0])
    except (MediaError, ApiError, KeyError, ValueError, TypeError, FileNotFoundError) as error:
        print(f"uberseek: {error}", file=sys.stderr)
        return 2
    return 0


if __name__ == "__main__":
    sys.exit(main())
