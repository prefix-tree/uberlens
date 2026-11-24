"""A small command line, for trying the observation contract by hand."""

from __future__ import annotations

import argparse
import json
import sys
from fractions import Fraction
from pathlib import Path

from uberseek import Project, guide, select
from uberseek.api import ApiError, Library
from uberseek.media import MediaError
from uberseek.observe.plan import FOCUSES
from uberseek.timecode import clock, seconds


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="uberseek", description="Explore video: observe a span, and prove it can be made again.")
    parser.add_argument("--project", default=".", help="folder that holds the log (default: here)")
    commands = parser.add_subparsers(dest="command", required=True)

    observe = commands.add_parser("observe", help="show a span of a video as one picture")
    observe.add_argument("video")
    observe.add_argument("start", help="seconds or H:MM:SS.mmm")
    observe.add_argument("end", nargs="?", help="leave out for a single frame")
    observe.add_argument("--focus", choices=FOCUSES, default="visual")
    observe.add_argument("--purpose", default="", help="what the look is for")
    observe.add_argument("--out", help="also write the picture here")

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
    run.add_argument("--video", action="append", help="a video the program may use, by name (repeat for more)")

    read = commands.add_parser("guide", help="print the UberSeek skill, or one part of it")
    read.add_argument("topic", nargs="?", choices=guide.TOPICS)

    skill = commands.add_parser("skill", help="install the skill where an agent will find it")
    skill.add_argument("action", choices=["install"])
    skill.add_argument("folder", nargs="?", default=".claude/skills")

    marking = commands.add_parser("mark", help="save a span as a selection for a clip")
    marking.add_argument("video")
    marking.add_argument("start")
    marking.add_argument("end")
    marking.add_argument("--reason", default="")

    commands.add_parser("selections", help="list the selections saved so far")

    clipping = commands.add_parser("clip", help="cut selections into one video file")
    clipping.add_argument("name")
    clipping.add_argument("selection", nargs="+", help="selection ids, in the order they should play")

    checking = commands.add_parser("verify", help="check a clip by code, and list where its joins are")
    checking.add_argument("name")

    exporting = commands.add_parser("export", help="print a clip as data: selections, reasons and the command that cut it")
    exporting.add_argument("name")

    log = commands.add_parser("log", help="list observations")
    log.add_argument("--json", action="store_true")

    args = parser.parse_args(argv)
    if args.command == "guide":
        print(guide.topic(args.topic) if args.topic else guide.core("shell"))
        return 0
    if args.command == "skill":
        print(f"Installed: {guide.install(Path(args.folder))}")
        return 0
    project = Project(args.project)
    try:
        if args.command == "observe":
            seen = project.observe(args.video, args.start, args.end, args.focus, args.purpose)
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
            done = Executor(project, args.video).run_sync(program)
            print(done.text)
            for seen in done.looks:
                print(f"Picture: {project.log.root / 'artifacts' / (seen.record['artifact']['sha256'] + '.png')}")
            return 1 if done.error else 0
        elif args.command == "mark":
            print(json.dumps(Library(project).mark(args.video, seconds(args.start), seconds(args.end), args.reason), indent=1))
        elif args.command == "selections":
            print(json.dumps(Library(project).selections(), indent=1))
        elif args.command == "clip":
            made = Library(project).clip(args.selection, args.name)
            print(json.dumps(made, indent=1))
            print(f"File: {select.clips_folder(project) / made['clip']}")
        elif args.command == "verify":
            checked = select.verify(project, args.name)
            print(json.dumps(checked, indent=1))
            return 0 if checked["ok"] else 1
        elif args.command == "export":
            print(json.dumps(select.export(project, args.name), indent=1))
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
        else:
            for record in project.log.observations():
                print(json.dumps(record) if args.json else project.show(record["id"]).text.splitlines()[0])
    except (MediaError, ApiError, KeyError, ValueError, FileNotFoundError) as error:
        print(f"uberseek: {error}", file=sys.stderr)
        return 2
    return 0


if __name__ == "__main__":
    sys.exit(main())
