"""Run the reading check: `uv run python -m bench.reading.run`.

Each question is put to each model several times through Pydantic AI. The model calls `observe` itself;
its answer is compared with what the log says that observation showed.
"""

from __future__ import annotations

import argparse
import asyncio
import json
import re
import tempfile
from collections import defaultdict
from datetime import UTC, datetime
from pathlib import Path

from pydantic_ai import Agent  # noqa: E402
from pydantic_ai.exceptions import ModelHTTPError  # noqa: E402
from pydantic_ai.messages import ToolReturnPart  # noqa: E402

from bench import models  # noqa: E402
from bench.reading.questions import Pair, Question, questions, spoken  # noqa: E402
from uberseek import Project  # noqa: E402
from uberseek.host.pydantic_ai import toolset  # noqa: E402

MODELS = ["anthropic/claude-sonnet-5.5", "openai/gpt-5.6-terra"]
RESULTS = Path(__file__).parent / "results"
RETRIES = 10
MAX_TOKENS = 2000  # an answer is a number or two; this also bounds what a run can cost
INSTRUCTIONS = "You examine video with the observe tool. Make the one look you are asked to make, then answer from the picture alone."


def _same(answer: object, expected: object) -> bool:
    if isinstance(expected, str):  # a time: the answer may wrap it in a sentence
        return re.findall(r"\d+:\d\d\.\d{3}", str(answer)) == [expected]
    if isinstance(answer, Pair):
        answer = (answer.first, answer.second)
    return json.loads(json.dumps(answer)) == json.loads(json.dumps(expected))


async def ask(model: str, question: Question, project: Project, limit: asyncio.Semaphore) -> dict:
    row = {"model": model, "kind": question.kind, "question": question.name, "correct": False}
    agent = Agent(
        models.model(model),
        toolsets=[toolset(project)],
        output_type=question.answer_type,
        instructions=INSTRUCTIONS,
        model_settings=models.settings(model, MAX_TOKENS),
    )
    prompt = f"Look at the video {question.video} {question.look}. {question.ask}"
    async with limit:
        for attempt in range(RETRIES):
            try:
                result = await agent.run(prompt)
                break
            except ModelHTTPError as error:
                if error.status_code != 429 or attempt == RETRIES - 1:
                    return row | {"error": f"{type(error).__name__}: {error}"[:300]}
                await asyncio.sleep(20)  # a rate limit: wait and ask again
            except Exception as error:  # the run failed for another reason: kept, and not counted as an answer
                return row | {"error": f"{type(error).__name__}: {error}"[:300]}
    shown = [
        match[0]
        for message in result.all_messages()
        for part in message.parts
        if isinstance(part, ToolReturnPart)
        and (match := re.match(r"obs_\d+", str(part.content[0] if isinstance(part.content, list) else part.content)))
    ]
    if not shown:
        return row | {"error": "answered without looking"}
    # A model that looks more than once may answer about any of its looks: the answer is right if it fits one.
    fits = [question.expected(project.log.get(id)) for id in shown]
    expected = next((e for e in fits if _same(result.output, e)), fits[-1])
    usage = result.usage
    return row | {
        "answer": [result.output.first, result.output.second] if isinstance(result.output, Pair) else result.output,
        "expected": expected,
        "correct": _same(result.output, expected),
        "observations": shown,
        "tokens": {"input": usage.input_tokens, "output": usage.output_tokens},
    }


def table(rows: list[dict]) -> str:
    """Right answers out of answers given, per kind of question. A run that failed is not an answer."""
    answered = [row for row in rows if "error" not in row]
    kinds = list(dict.fromkeys(row["kind"] for row in rows))
    models = list(dict.fromkeys(row["model"] for row in rows))
    score = defaultdict(list)
    for row in answered:
        score[row["model"], row["kind"]].append(row["correct"])
        score[row["model"], "all"].append(row["correct"])
    lines = ["| Question | " + " | ".join(models) + " |", "| --- |" + " --- |" * len(models)]
    for kind in [*kinds, "all"]:
        cells = [f"{sum(score[m, kind])}/{len(score[m, kind])}" for m in models]
        lines.append(f"| {kind} | " + " | ".join(cells) + " |")
    failed = len(rows) - len(answered)
    return "\n".join(lines) + (f"\n\n{failed} runs failed and are not counted." if failed else "")


async def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--models", nargs="+", default=MODELS, help="OpenRouter model ids")
    parser.add_argument("--repeats", type=int, default=3)
    parser.add_argument("--only", help="run only questions of this kind")
    parser.add_argument("--parallel", type=int, default=2, help="runs at once per model")
    parser.add_argument("--spoken", metavar="PROJECT", help="ask the questions on real footage, using this project's transcripts")
    parser.add_argument("--words-in", nargs="+", default=["picture", "text"], choices=["picture", "text"])
    parser.add_argument("--note", default="", help="what this run is testing, kept with the results")
    args = parser.parse_args()

    with tempfile.TemporaryDirectory() as work:
        if args.spoken:
            project = Project(args.spoken, words_in=tuple(args.words_in))
            asked = spoken(project, Path("data/footage"))
        else:
            project = Project(work)
            asked = [q for q in questions(Path(work) / "clips") if args.only in (None, q.kind)]
        limits = {m: asyncio.Semaphore(args.parallel) for m in args.models}
        jobs = [ask(m, q, project, limits[m]) for m in args.models for q in asked for _ in range(args.repeats)]
        rows = await asyncio.gather(*jobs)

    summary = table(rows)
    stamp = datetime.now(UTC).strftime("%Y-%m-%dT%H%M%S")
    RESULTS.mkdir(exist_ok=True)
    (RESULTS / f"{stamp}.json").write_text(
        json.dumps({"at": stamp, "note": args.note, "words_in": args.words_in, "repeats": args.repeats, "rows": rows}, indent=1)
    )
    print(summary)
    for row in rows:
        if not row["correct"]:
            said, was = row.get("answer"), row.get("expected")
            print(f"  wrong: {row['model']} · {row['question']} · said {said!r}, was {was!r} {row.get('error', '')}")


if __name__ == "__main__":
    asyncio.run(main())
