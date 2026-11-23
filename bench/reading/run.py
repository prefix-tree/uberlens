"""Run the reading check: `uv run python -m bench.reading.run`.

Each question is put to each model several times through Pydantic AI. The model calls `observe` itself;
its answer is compared with what the log says that observation showed.
"""

from __future__ import annotations

import argparse
import asyncio
import json
import os
import re
import tempfile
from collections import defaultdict
from datetime import UTC, datetime
from pathlib import Path

os.environ.setdefault("PYDANTIC_AI_NO_BANNER", "1")
# The key is added to requests by the environment's network proxy; the client only needs a value to start.
os.environ.setdefault("OPENROUTER_API_KEY", "proxy-injected")

from pydantic_ai import Agent  # noqa: E402
from pydantic_ai.messages import ToolReturnPart  # noqa: E402
from pydantic_ai.models.openrouter import OpenRouterModel  # noqa: E402

from bench.reading.questions import Question, questions  # noqa: E402
from uberseek import Project  # noqa: E402
from uberseek.host.pydantic_ai import toolset  # noqa: E402

MODELS = ["anthropic/claude-sonnet-5.5", "openai/gpt-5.6-terra"]
RESULTS = Path(__file__).parent / "results"
MAX_TOKENS = 2000  # an answer is a number or two; this also bounds what a run can cost
INSTRUCTIONS = "You examine video with the observe tool. Make the one look you are asked to make, then answer from the picture alone."


def _same(answer: object, expected: object) -> bool:
    if isinstance(expected, str):
        return str(answer).strip() == expected
    return json.loads(json.dumps(answer)) == json.loads(json.dumps(expected))


async def ask(model: str, question: Question, project: Project, limit: asyncio.Semaphore) -> dict:
    row = {"model": model, "kind": question.kind, "question": question.name, "correct": False}
    agent = Agent(
        OpenRouterModel(model),
        toolsets=[toolset(project)],
        output_type=question.answer_type,
        instructions=INSTRUCTIONS,
        model_settings={"max_tokens": MAX_TOKENS},
    )
    prompt = f"Look at the video {question.video} {question.look}. {question.ask}"
    async with limit:
        try:
            result = await agent.run(prompt)
        except Exception as error:  # a failed run counts as a wrong answer, and is kept
            return row | {"error": f"{type(error).__name__}: {error}"[:300]}
    shown = [
        match[0]
        for message in result.all_messages()
        for part in message.parts
        if isinstance(part, ToolReturnPart)
        and (match := re.match(r"obs_\d+", str(part.content[0] if isinstance(part.content, list) else part.content)))
    ]
    if not shown:
        return row | {"error": "answered without looking", "answer": result.output}
    expected = question.expected(project.log.get(shown[-1]))
    usage = result.usage
    return row | {
        "answer": result.output,
        "expected": expected,
        "correct": _same(result.output, expected),
        "observations": shown,
        "tokens": {"input": usage.input_tokens, "output": usage.output_tokens},
    }


def table(rows: list[dict]) -> str:
    kinds = list(dict.fromkeys(row["kind"] for row in rows))
    models = list(dict.fromkeys(row["model"] for row in rows))
    score = defaultdict(list)
    for row in rows:
        score[row["model"], row["kind"]].append(row["correct"])
        score[row["model"], "all"].append(row["correct"])
    lines = ["| Question | " + " | ".join(models) + " |", "| --- |" + " --- |" * len(models)]
    for kind in [*kinds, "all"]:
        cells = [f"{sum(score[m, kind])}/{len(score[m, kind])}" for m in models]
        lines.append(f"| {kind} | " + " | ".join(cells) + " |")
    return "\n".join(lines)


async def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--models", nargs="+", default=MODELS, help="OpenRouter model ids")
    parser.add_argument("--repeats", type=int, default=3)
    parser.add_argument("--only", help="run only questions of this kind")
    parser.add_argument("--note", default="", help="what this run is testing, kept with the results")
    args = parser.parse_args()

    with tempfile.TemporaryDirectory() as work:
        asked = [q for q in questions(Path(work) / "clips") if args.only in (None, q.kind)]
        project, limit = Project(work), asyncio.Semaphore(6)
        jobs = [ask(m, q, project, limit) for m in args.models for q in asked for _ in range(args.repeats)]
        rows = await asyncio.gather(*jobs)

    summary = table(rows)
    stamp = datetime.now(UTC).strftime("%Y-%m-%dT%H%M%S")
    RESULTS.mkdir(exist_ok=True)
    (RESULTS / f"{stamp}.json").write_text(json.dumps({"at": stamp, "note": args.note, "repeats": args.repeats, "rows": rows}, indent=1))
    print(summary)
    for row in rows:
        if not row["correct"]:
            said, was = row.get("answer"), row.get("expected")
            print(f"  wrong: {row['model']} · {row['question']} · said {said!r}, was {was!r} {row.get('error', '')}")


if __name__ == "__main__":
    asyncio.run(main())
