"""The decision for the language the model writes: Python, run by Monty.

This is a check of the sandbox, not the executor (that is M1). A program of the kind a model would
write calls host functions, keeps its working data to itself and returns a compact result; it cannot
read files, reach the network or run for ever.
"""

from __future__ import annotations

import asyncio
from fractions import Fraction

import pytest

monty = pytest.importorskip("pydantic_monty")

from uberseek import Project  # noqa: E402

LIMITS = {"max_feed_duration_secs": 2.0, "max_memory": 64 * 1024 * 1024, "max_recursion_depth": 200}

PROGRAM = """
info = source_info(video)
quiet = pauses(video)
# Working data stays here: every pause, with the second before it.
candidates = [{"start": max(0, p[0] - 1), "end": p[1], "pause": p[1] - p[0]} for p in quiet]
longest = max(candidates, key=lambda c: c["pause"])
seen = observe(video, longest["start"], longest["end"], "delivery")
{"frames": info["frames"], "candidates": len(candidates), "looked_at": seen}
"""


def run(code: str, inputs: dict | None = None, functions: dict | None = None):
    async def go():
        async with monty.AsyncMonty() as pool, pool.checkout(limits=LIMITS) as session:
            return await session.feed_run(code, inputs=inputs or {}, external_lookup=functions or {})

    return asyncio.run(go())


def test_a_program_computes_in_the_sandbox_and_looks_through_the_host(clips, tmp_path):
    project = Project(tmp_path)

    def source_info(video: str) -> dict:
        source = project.open(video)
        return {"frames": len(source.index.frames), "duration": float(source.info.duration)}

    def pauses(video: str) -> list:
        source = project.open(video)
        from uberseek.ingest import signals

        found = project.log.derived(source.hash, "silences", lambda: signals.silences(source.path))
        return [[float(Fraction(a)), float(Fraction(b))] for a, b in found["spans"]]

    def observe(video: str, start: float, end: float, focus: str) -> str:
        return project.observe(video, start, end, focus).id  # the picture goes to the model, not into the program

    functions = {"source_info": source_info, "pauses": pauses, "observe": observe}
    result = run(PROGRAM, {"video": str(clips["bframes"])}, functions)

    assert result == {"frames": 150, "candidates": 1, "looked_at": "obs_000001"}
    (logged,) = project.log.observations()
    assert logged["request"]["focus"] == "delivery" and Fraction(logged["request"]["start"]) == pytest.approx(1.02, abs=0.05)


@pytest.mark.parametrize(
    ("code", "refused"),
    [
        ("open('/etc/passwd').read()", "Permission denied"),
        ("import os\nos.listdir('/')", "Permission denied"),
        ("import os\nos.environ['HOME']", "not supported"),
        ("import socket", "No module named"),
        ("import subprocess", "No module named"),
        ("while True:\n    pass", "time limit"),
        ("x = [0] * 10**9", "memory limit"),
    ],
)
def test_a_program_cannot_reach_outside_or_run_away(code, refused):
    with pytest.raises(monty.MontyRuntimeError, match=refused):
        run(code)
