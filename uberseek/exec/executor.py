"""The executor: a program written by a model runs in Monty, with the library as its only way out.

Monty is an interpreter for a subset of Python that runs in its own worker process and has no files,
network or environment. Limits are enforced here, on the host side, so a program cannot ask its way
around them. Every run is logged, whether it worked or not.
"""

from __future__ import annotations

import asyncio
import json
import time
from dataclasses import dataclass, field
from pathlib import Path

import pydantic_monty as monty

from uberseek.api import ApiError, Library
from uberseek.observe.gateway import Observation, Project


@dataclass(frozen=True)
class Limits:
    seconds: float = 20.0  # of the program's own running time; time inside host calls is not counted
    memory: int = 64 * 1024 * 1024
    calls: int = 200  # host calls per program
    looks: int = 4  # `observe` calls per program
    result: int = 6000  # characters of result returned to the model
    printed: int = 2000


@dataclass(frozen=True)
class Execution:
    id: str
    text: str  # what the model is told: the result, what was printed, or the error
    result: object = None
    looks: list[Observation] = field(default_factory=list)
    error: str | None = None


def clip(text: str, limit: int, what: str) -> str:
    if len(text) <= limit:
        return text
    advice = "ask for less, for example a shorter span, a count or the top few items"
    return f"{text[:limit]}\n[{what} cut at {limit} of {len(text)} characters: {advice}]"


class Executor:
    def __init__(self, project: Project, videos: list[Path | str] | None = None, limits: Limits | None = None):
        self.project, self.videos, self.limits = project, videos, limits or Limits()

    def reference(self) -> str:
        return Library(self.project, self.videos).reference()

    def run_sync(self, program: str) -> Execution:
        return asyncio.run(self.run(program))

    async def run(self, program: str) -> Execution:
        library, limits = Library(self.project, self.videos), self.limits
        calls: list[dict] = []

        def host(name: str):
            function = getattr(library, name)

            def call(*args, **kwargs):
                if len(calls) >= limits.calls:
                    raise ApiError(f"this program made more than {limits.calls} calls to the library; do less per program")
                if name == "observe" and len(library.looks) >= limits.looks:
                    raise ApiError(
                        f"a program can look at most {limits.looks} times; return, see the pictures, then decide what to look at next"
                    )
                entry = {"name": name, "args": json.dumps([args, kwargs], default=str)[:300]}
                calls.append(entry)
                began = time.perf_counter()
                try:
                    return function(*args, **kwargs)
                except Exception as error:
                    entry["error"] = f"{type(error).__name__}: {error}"[:300]
                    if isinstance(error, ApiError | TypeError):
                        raise ValueError(str(error)) from None  # reaches the program as an ordinary error it can read
                    raise
                finally:
                    entry["seconds"] = round(time.perf_counter() - began, 3)

            return call

        printed: list[str] = []
        result, error, began = None, None, time.perf_counter()
        sandbox = {"max_feed_duration_secs": limits.seconds, "max_memory": limits.memory}
        try:
            async with monty.AsyncMonty() as pool, pool.checkout(limits=sandbox) as session:
                result = await session.feed_run(
                    program,
                    external_lookup={name: host(name) for name in Library.OPERATIONS},
                    print_callback=lambda stream, text: printed.append(text),
                )
        except monty.MontyError as failure:
            show = getattr(failure, "display", None)
            error = show() if callable(show) else str(failure)

        out = "".join(printed)
        parts = []
        if error:
            parts.append(f"The program failed.\n{error}")
        else:
            parts.append(clip(json.dumps(result, default=str), limits.result, "result"))
        if out:
            parts.append("Printed:\n" + clip(out, limits.printed, "printed text"))
        for number, seen in enumerate(library.looks, start=1):
            parts.append(f"Picture {number} of {len(library.looks)}, titled with its video and span:\n{seen.text}")
        record = self.project.log.append_execution(
            {
                "program": program,
                "calls": calls,
                "result": None if error else json.loads(json.dumps(result, default=str)),
                "printed": out[: limits.printed],
                "error": error,
                "observations": [seen.id for seen in library.looks],
                "seconds": round(time.perf_counter() - began, 3),
            }
        )
        return Execution(record["id"], "\n\n".join(parts), None if error else result, library.looks, error)
