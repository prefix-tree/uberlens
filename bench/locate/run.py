"""Put locate tasks to a model through the host: `uv run python -m bench.locate.run`.

The model gets the tools of one surface (`code` or `tools`) and must name a span. The answer is compared
with the ranges in bench/footage/locate.toml. Those tasks are drafts until a person confirms them, so
what this prints shows that the surface works; it is not a measurement.
"""

from __future__ import annotations

import argparse
import asyncio
import json
import tomllib
from datetime import UTC, datetime
from pathlib import Path

from pydantic import BaseModel  # noqa: E402
from pydantic_ai import Agent, ModelRetry  # noqa: E402
from pydantic_ai.exceptions import ModelHTTPError  # noqa: E402
from pydantic_ai.messages import ToolCallPart  # noqa: E402

from bench import models  # noqa: E402
from bench.footage import fetch  # noqa: E402
from uberseek import Project  # noqa: E402
from uberseek.host.pydantic_ai import toolset  # noqa: E402

TASKS = Path(__file__).parent.parent / "footage" / "locate.toml"
RESULTS = Path(__file__).parent / "results"
MODELS = ["anthropic/claude-haiku-5.5", "openai/gpt-5.6-luna"]
INSTRUCTIONS = (
    "You find moments in video. Search first, then look at a candidate before you answer: a search result is a place "
    "to look, not an answer. Answer with the span, in seconds, that answers the question, as tightly as you can."
)


class Found(BaseModel):
    start: float
    end: float
    why: str


def overlap(found: Found, ranges: list[list[float]]) -> float:
    """Intersection over union with the best-matching labelled range."""
    best = 0.0
    for a, b in ranges:
        inter = max(0.0, min(found.end, b) - max(found.start, a))
        union = max(found.end, b) - min(found.start, a)
        best = max(best, inter / union if union > 0 else 0.0)
    return round(best, 3)


async def ask(model: str, surface: str, task: dict, project: Project, skill: bool) -> dict:
    video = fetch.path(task["video"])
    row = {
        "model": model,
        "surface": surface,
        "skill": skill,
        "video": task["video"],
        "question": task["question"],
        "ranges": task["ranges"],
    }
    agent = Agent(
        models.model(model),
        toolsets=[toolset(project, [video], surface, skill=skill)],
        output_type=Found,
        instructions=INSTRUCTIONS,
        model_settings=models.settings(model, 3000),
    )

    @agent.output_validator
    def has_length(found: Found) -> Found:
        """A model sometimes files an empty answer while it is still looking; that is sent back."""
        if found.end <= found.start:
            raise ModelRetry("The span has no length. Finish looking, then answer with a start and a later end, in seconds.")
        return found

    runs_before, looks_before = len(project.log.executions()), len(project.log.observations())
    for attempt in range(8):
        try:
            result = await agent.run(f"In {video.name}: {task['question']}")
            break
        except ModelHTTPError as error:
            if error.status_code != 429 or attempt == 7:
                return row | {"error": f"{type(error).__name__}: {error}"[:900]}
            await asyncio.sleep(20)
        except Exception as error:
            return row | {"error": f"{type(error).__name__}: {error}"[:900]}
    calls = [part.tool_name for message in result.all_messages() for part in message.parts if isinstance(part, ToolCallPart)]
    usage = result.usage
    programs = [{call["name"] for call in run["calls"]} for run in project.log.executions()[runs_before:]]
    return (
        row
        | {
            "found": [result.output.start, result.output.end],
            "why": result.output.why,
            "overlap": overlap(result.output, task["ranges"]),
            "tool_calls": [name for name in calls if name != "final_result"],
            "programs": len(programs),
            "programs_combining": sum(len(used) >= 2 for used in programs),  # programs that use two or more operations
            "looks": len(project.log.observations()) - looks_before,  # pictures sent to the model
            "sheets": sum(seen["recipe"]["level"] == "sheet" for seen in project.log.observations()[looks_before:]),
            "requests": usage.requests,
            "tokens": {"input": usage.input_tokens, "output": usage.output_tokens},
        }
    )


async def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--models", nargs="+", default=MODELS, help="OpenRouter model ids")
    parser.add_argument("--surfaces", nargs="+", default=["code", "tools"], choices=["code", "tools"])
    parser.add_argument("--skill", nargs="+", default=["on"], choices=["on", "off"], help="with the UberSeek skill, without it, or both")
    parser.add_argument("--match", nargs="*", default=[""], help="only tasks whose question contains one of these texts")
    parser.add_argument("--project", default="data/project", help="project folder holding transcripts and the log")
    parser.add_argument("--note", default="")
    args = parser.parse_args()

    tasks = [t for t in tomllib.loads(TASKS.read_text())["task"] if any(m.lower() in t["question"].lower() for m in args.match)]
    project = Project(args.project)
    cells = [(m, s, t, k == "on") for t in tasks for m in args.models for s in args.surfaces for k in args.skill]
    rows = [await ask(m, s, t, project, k) for m, s, t, k in cells]

    stamp = datetime.now(UTC).strftime("%Y-%m-%dT%H%M%S")
    RESULTS.mkdir(exist_ok=True)
    (RESULTS / f"{stamp}.json").write_text(json.dumps({"at": stamp, "note": args.note, "rows": rows}, indent=1))
    for row in rows:
        head = f"{row['model'].split('/')[1]} · {row['surface']} · skill {'on' if row['skill'] else 'off'} · {row['video']}"
        if "error" in row:
            print(f"{head} · failed: {row['error']}")
            continue
        print(f"{head} · found {row['found']} of {row['ranges']} · overlap {row['overlap']}")
        work = f"{row['looks']} looks ({row.get('sheets', 0)} sheets), {row['programs']} programs ({row['programs_combining']} combining steps)"
        print(f"    {work} · {row['requests']} requests · {row['tokens']['input']} tokens in, {row['tokens']['output']} out")

    print("\n| Surface | Skill | Runs | Hit (overlap over 0.3) | Looked first | Programs combining steps | Tokens in per run |")
    print("| --- | --- | --- | --- | --- | --- | --- |")
    done = [row for row in rows if "error" not in row]
    for surface in args.surfaces:
        for skill in (True, False):
            cell = [row for row in done if row["surface"] == surface and row["skill"] == skill]
            if cell:
                made, combined = sum(row["programs"] for row in cell), sum(row["programs_combining"] for row in cell)
                tokens = sum(row["tokens"]["input"] for row in cell) // len(cell)
                hits, looked = sum(row["overlap"] > 0.3 for row in cell), sum(row["looks"] > 0 for row in cell)
                combining = f"{combined} of {made}" if surface == "code" else "n/a"
                print(f"| {surface} | {'on' if skill else 'off'} | {len(cell)} | {hits} | {looked} | {combining} | {tokens:,} |")


if __name__ == "__main__":
    asyncio.run(main())
