"""Compositional tasks on both surfaces: `uv run python -m bench.compose.run` (`--dry` prints the answers only).

The same tasks, model and limits on the `code` surface and the `tools` surface. Each run is scored on A
and on B separately, so a wrong link from A to B shows apart from a wrong A.
"""

from __future__ import annotations

import argparse
import asyncio
import json
import time
import urllib.request
from datetime import UTC, datetime
from pathlib import Path

from pydantic import BaseModel
from pydantic_ai import Agent
from pydantic_ai.exceptions import ModelHTTPError

from bench import models
from bench.compose.tasks import TASKS, Task, near, right_b
from bench.footage import fetch
from uberseek import Project
from uberseek.api import Library
from uberseek.host.pydantic_ai import toolset

RESULTS = Path(__file__).parent / "results"
MODEL = "anthropic/claude-sonnet-5.5"
INSTRUCTIONS = "You answer questions about a video from its transcript and measurements. Times are seconds. Be exact."


class Answer(BaseModel):
    a: list[float]  # the span of A, as [start, end]
    b_span: list[float] | None = None  # B, when it is a span
    b_text: str | None = None  # B, when it is words
    b_number: float | None = None  # B, when it is a number


def spent() -> float:
    request = urllib.request.Request("https://openrouter.ai/api/v1/credits", headers={"Authorization": "Bearer proxy-injected"})
    with urllib.request.urlopen(request, timeout=30) as reply:
        return json.load(reply)["data"]["total_usage"]


async def ask(model: str, surface: str, task: Task, truth: dict, project: Project) -> dict:
    video = fetch.path(task.video)
    row = {"model": model, "surface": surface, "task": task.name, "relation": task.relation, "truth": truth}
    agent = Agent(
        models.model(model),
        toolsets=[toolset(project, [video], surface)],
        output_type=Answer,
        instructions=INSTRUCTIONS,
        model_settings=models.settings(model, 4000),
    )
    runs_before, began = len(project.log.executions()), time.perf_counter()
    for attempt in range(8):
        try:
            result = await agent.run(f"In {video.name}. {task.question}")
            break
        except ModelHTTPError as error:
            if error.status_code != 429 or attempt == 7:
                return row | {"error": f"{type(error).__name__}: {error}"[:600]}
            await asyncio.sleep(20)
        except Exception as error:
            return row | {"error": f"{type(error).__name__}: {error}"[:600]}
    found, usage = result.output, result.usage
    b = {"span": found.b_span, "text": found.b_text, "number": found.b_number}[task.b]
    programs = [{call["name"] for call in run["calls"]} for run in project.log.executions()[runs_before:]]
    return row | {
        "found": {"a": found.a, "b": b},
        "a_right": near(found.a, truth["a"]),
        "b_right": right_b(task, b, truth["b"]),
        "requests": usage.requests,
        "tokens": {"input": usage.input_tokens, "output": usage.output_tokens},
        "seconds": round(time.perf_counter() - began, 1),
        "programs": len(programs),
        "programs_combining": sum(len(used) >= 2 for used in programs),  # programs that use two or more operations
    }


HEADS = [
    "Surface",
    "Runs",
    "A right",
    "B right",
    "Both right",
    "Requests",
    "Tokens in",
    "Tokens out",
    "Seconds",
    "Programs combining steps",
]


def table(rows: list[dict], surfaces: list[str]) -> str:
    """Per surface: how often A, B and both were right, and the mean cost of a run."""
    done = [row for row in rows if "error" not in row]
    lines = ["| " + " | ".join(HEADS) + " |", "|" + " --- |" * len(HEADS)]
    for surface in surfaces:
        cell = [row for row in done if row["surface"] == surface]
        if not cell:
            continue
        count = len(cell)
        means = [
            f"{sum(row['requests'] for row in cell) / count:.1f}",
            f"{sum(row['tokens']['input'] for row in cell) / count:,.0f}",
            f"{sum(row['tokens']['output'] for row in cell) / count:,.0f}",
            f"{sum(row['seconds'] for row in cell) / count:.0f}",
        ]
        made, combined = sum(row["programs"] for row in cell), sum(row["programs_combining"] for row in cell)
        right = [
            sum(row["a_right"] for row in cell),
            sum(row["b_right"] for row in cell),
            sum(row["a_right"] and row["b_right"] for row in cell),
        ]
        combining = f"{combined} of {made}" if surface == "code" else "n/a"
        lines.append("| " + " | ".join([surface, str(count), *map(str, right), *means, combining]) + " |")
    failed = len(rows) - len(done)
    return "\n".join(lines) + (f"\n\n{failed} runs failed and are not counted." if failed else "")


async def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--model", default=MODEL, help="OpenRouter model id")
    parser.add_argument("--surfaces", nargs="+", default=["code", "tools"], choices=["code", "tools"])
    parser.add_argument("--repeats", type=int, default=3)
    parser.add_argument("--only", nargs="*", help="only tasks whose name contains one of these texts")
    parser.add_argument("--budget", type=float, default=3.0, help="stop when this run has spent this many dollars")
    parser.add_argument("--project", default="data/project", help="project folder holding transcripts and the log")
    parser.add_argument("--dry", action="store_true", help="print the reference answers and call no model")
    parser.add_argument("--note", default="")
    args = parser.parse_args()

    project = Project(args.project)
    library = Library(project, [fetch.path(name) for name in fetch.videos()])
    tasks = [t for t in TASKS if not args.only or any(text in t.name for text in args.only)]
    truths = {task.name: task.reference(library) for task in tasks}
    if args.dry:
        for task in tasks:
            print(f"{task.name} ({task.video}, by {task.relation})\n    {task.question}\n    {truths[task.name]}")
        return

    start, rows = spent(), []
    for task in tasks:
        if (used := spent() - start) > args.budget:
            print(f"Stopped before '{task.name}': ${used:.2f} spent, the budget is ${args.budget:.2f}.")
            break
        for surface in args.surfaces:
            for _ in range(args.repeats):
                rows.append(await ask(args.model, surface, task, truths[task.name], project))
        print(f"{task.name}: done, ${spent() - start:.2f} spent so far", flush=True)

    stamp = datetime.now(UTC).strftime("%Y-%m-%dT%H%M%S")
    RESULTS.mkdir(exist_ok=True)
    record = {
        "at": stamp,
        "note": args.note,
        "model": args.model,
        "repeats": args.repeats,
        "dollars": round(spent() - start, 2),
        "rows": rows,
    }
    (RESULTS / f"{stamp}.json").write_text(json.dumps(record, indent=1))
    for row in rows:
        if "error" in row:
            print(f"{row['surface']} · {row['task']} · failed: {row['error']}")
        else:
            marks = f"A {'right' if row['a_right'] else 'WRONG'}, B {'right' if row['b_right'] else 'WRONG'}"
            cost = f"{row['requests']} requests, {row['tokens']['input']} in, {row['programs']} programs"
            cost += f" ({row['programs_combining']} combining)"
            print(f"{row['surface']} · {row['task']} · {marks} · found {row['found']} · {cost}")
    print()
    print(table(rows, args.surfaces))


if __name__ == "__main__":
    asyncio.run(main())
