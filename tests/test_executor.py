"""A program runs in the sandbox with the library as its only way out, inside limits, and is logged."""

from __future__ import annotations

import pytest

pytest.importorskip("pydantic_monty")

from uberseek import Project  # noqa: E402
from uberseek.exec import Executor, Limits  # noqa: E402

PROGRAM = """
shots = shots("three_shots.mp4")
longest = max(shots, key=lambda s: s[1] - s[0])
middle = (longest[0] + longest[1]) / 2
seen = observe("three_shots.mp4", middle - 0.5, middle + 0.5, "visual", "what is in the longest shot?")
print("shots:", len(shots))
{"longest": longest, "looked": seen["id"]}
"""


@pytest.fixture
def executor(clips, tmp_path) -> Executor:
    limits = Limits(seconds=2.0, calls=20, looks=2, result=200)
    return Executor(Project(tmp_path), [clips["three_shots"], clips["bframes"]], limits)


def test_a_program_computes_looks_and_returns_something_small(executor):
    done = executor.run_sync(PROGRAM)
    assert done.error is None and done.result == {"longest": [0, 2.5], "looked": "obs_000001"}
    assert done.text.startswith('{"longest": [0.0, 2.5], "looked": "obs_000001"}')
    assert "Printed:\nshots: 3" in done.text and "obs_000001: three_shots.mp4, 0:00.750 to 0:01.750" in done.text
    (look,) = done.looks  # the picture is handed over beside the result; it never entered the program
    assert look.image.startswith(b"\x89PNG")


def test_every_run_is_logged_with_its_calls(executor):
    executor.run_sync(PROGRAM)
    executor.run_sync("cuts('nope.mp4')")
    worked, failed = executor.project.log.executions()
    assert worked["id"] == "exec_000001" and worked["program"] == PROGRAM and worked["observations"] == ["obs_000001"]
    assert [call["name"] for call in worked["calls"]] == ["shots", "observe"] and worked["error"] is None
    assert "no video named 'nope.mp4'" in failed["error"] and "no video named" in failed["calls"][0]["error"]


@pytest.mark.parametrize(
    ("program", "told"),
    [
        ("cuts('nope.mp4')", "no video named 'nope.mp4'. Available: three_shots.mp4, bframes.mp4"),
        ("x = 1\ny = cuts('three_shots.mp4', 5, 2)", "line 2"),
        ("cuts()", "missing"),
        ("def broken(:\n    pass", "SyntaxError"),
        ("class Mine(dict):\n    pass", "does not yet support class inheritance"),
        ("open('/etc/passwd').read()", "Permission denied"),
        ("import socket", "No module named 'socket'"),
        ("while True:\n    pass", "time limit exceeded"),
        ("[observe('bframes.mp4', t) for t in (1, 2, 3)]", "a program can look at most 2 times"),
        ("[info('bframes.mp4') for _ in range(30)]", "more than 20 calls"),
    ],
)
def test_a_program_that_goes_wrong_is_told_how(executor, program, told):
    done = executor.run_sync(program)
    assert done.error and told in done.text and done.text.startswith("The program failed.")


def test_a_program_can_handle_an_error_itself(executor):
    done = executor.run_sync("try:\n    found = cuts('nope.mp4')\nexcept ValueError as error:\n    found = str(error)[:13]\nfound")
    assert done.error is None and done.result == "no video name"


def test_a_large_result_is_cut_and_says_so(executor):
    done = executor.run_sync("[[i, i * 2] for i in range(500)]")
    assert done.error is None and len(done.result) == 500
    assert "[result cut at 200 of" in done.text and "return less" in done.text
