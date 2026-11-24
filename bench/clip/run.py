"""Ask a model to build a clip: `uv run python -m bench.clip.run`.

One request, the tools of one surface, and at the end a file. What is recorded is whether the loop was
closed: a clip exists, it passes the checks, it is about the length asked for, it holds the moment asked
for, and the model looked at its own output. Whether the clip is good is not measured.
"""

from __future__ import annotations

import argparse
import asyncio
import json
from datetime import UTC, datetime
from fractions import Fraction
from pathlib import Path

from pydantic import BaseModel
from pydantic_ai import Agent
from pydantic_ai.exceptions import ModelHTTPError

from bench import models
from bench.footage import fetch
from uberseek import Project, select
from uberseek.host.pydantic_ai import harness

RESULTS = Path(__file__).parent / "results"
MODELS = ["anthropic/claude-haiku-5.5", "openai/gpt-5.6-luna"]
INSTRUCTIONS = (
    "You build video clips with the tools you are given. Finish only when the clip exists, has passed verify, and you have looked at it."
)

# The request, the video, the length asked for and the spans that hold the moment (from bench/footage/locate.toml).
REQUEST = "Make a clip of about 15 seconds of her answer about how many nights they slept in the cave."
VIDEO, SECONDS, HOLDS = "interview", 15, [[64.3, 69.9], [505.7, 509.4]]


class Built(BaseModel):
    clip: str  # the clip's name
    why: str


async def ask(model: str, surface: str, forget: bool, cache: bool, project: Project) -> dict:
    video = fetch.path(VIDEO)
    row = {"model": model, "surface": surface, "forget": forget, "cache": cache}
    agent = Agent(
        models.model(model),
        capabilities=harness(project, [video], surface, forget=forget),
        output_type=Built,
        instructions=INSTRUCTIONS,
        model_settings=models.settings(model, 4000, cache),
    )
    looks_before, notes_before = len(project.log.observations()), len(project.log.notes())
    for attempt in range(8):
        try:
            result = await agent.run(f"In {video.name}. {REQUEST}")
            break
        except ModelHTTPError as error:
            if error.status_code != 429 or attempt == 7:
                return row | {"error": f"{type(error).__name__}: {error}"[:600]}
            await asyncio.sleep(20)
        except Exception as error:
            return row | {"error": f"{type(error).__name__}: {error}"[:600]}
    usage, name = result.usage, result.output.clip.removesuffix(".mp4")
    row |= {
        "clip": name,
        "why": result.output.why,
        "requests": usage.requests,
        "tokens": {
            "input": usage.input_tokens,
            "output": usage.output_tokens,
            "cache_read": usage.cache_read_tokens,
            "cache_write": usage.cache_write_tokens,
        },
    }
    made = [clip for clip in project.log.clips() if clip["name"] == name]
    if not made:
        return row | {"built": False}
    checked, record = select.verify(project, name), made[-1]
    spans = [[float(Fraction(t)) for t in part["source"]] for part in record["segments"]]
    looks = project.log.observations()[looks_before:]
    return row | {
        "built": True,
        "verified": checked["ok"],
        "problems": checked["problems"],
        "edges_not_seen": sum("without a look" in warning for warning in checked["warnings"]),
        "seconds": checked["duration"],
        "source_spans": spans,
        "holds_the_moment": any(a <= hi and b >= lo for a, b in spans for lo, hi in HOLDS),
        "looked_at_the_clip": sum(look["source"]["hash"] == record["hash"] for look in looks),
        "looks": len(looks),
        "notes": len(project.log.notes()) - notes_before,
    }


async def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--models", nargs="+", default=MODELS, help="OpenRouter model ids")
    parser.add_argument("--surfaces", nargs="+", default=["code"], choices=["code", "tools"])
    parser.add_argument(
        "--forget", nargs="+", default=["on"], choices=["on", "off"], help="take pictures out of the context after one step"
    )
    parser.add_argument("--cache", action="store_true", help="ask the provider to cache the instructions, the tools and the history")
    parser.add_argument("--project", default="data/project", help="project folder holding transcripts and the log")
    parser.add_argument("--note", default="")
    args = parser.parse_args()

    project = Project(args.project)
    cells = [(model, surface, forget == "on") for model in args.models for surface in args.surfaces for forget in args.forget]
    rows = [await ask(model, surface, forget, args.cache, project) for model, surface, forget in cells]
    stamp = datetime.now(UTC).strftime("%Y-%m-%dT%H%M%S")
    RESULTS.mkdir(exist_ok=True)
    (RESULTS / f"{stamp}.json").write_text(json.dumps({"at": stamp, "note": args.note, "request": REQUEST, "rows": rows}, indent=1))
    for row in rows:
        head = f"{row['model'].split('/')[1]} · {row['surface']} · forget {'on' if row['forget'] else 'off'}"
        if "error" in row or not row.get("built"):
            print(f"{head} · no clip: {row.get('error', 'the clip named in the answer does not exist')}")
            continue
        print(
            f"{head} · {row['clip']} · {row['seconds']} s from {row['source_spans']} · verified {row['verified']} · "
            f"holds the moment {row['holds_the_moment']} · looked at the clip {row['looked_at_the_clip']} times · "
            f"{row['edges_not_seen']} edges not looked at · {row['looks']} looks, {row['notes']} notes · "
            f"{row['requests']} requests, {row['tokens']['input']} tokens in ({row['tokens']['cache_read']} read from cache)"
        )


if __name__ == "__main__":
    asyncio.run(main())
