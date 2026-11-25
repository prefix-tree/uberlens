"""The skill describes what UberSeek can do. These tests keep it true: what it names exists, what it shows runs."""

from __future__ import annotations

import os
import re

import pytest

from uberseek import Project, guide
from uberseek.api import Library
from uberseek.cli import main
from uberseek.exec import Executor, Limits
from uberseek.observe.plan import FOCUSES, LADDER

os.environ.setdefault("HF_HUB_DISABLE_XET", "1")
os.environ.setdefault("PYDANTIC_AI_NO_BANNER", "1")

EVERYTHING = "\n".join(path.read_text() for path in sorted(guide.SKILL.rglob("*.md")))


def test_it_is_a_valid_skill_with_a_short_core():
    described = guide.description()
    assert described["name"] == "uberseek" and len(described["description"]) > 200
    assert len((guide.SKILL / "SKILL.md").read_text().splitlines()) < 300
    assert all((guide.SKILL / "references" / f"{topic}.md").exists() for topic in guide.TOPICS)


def test_the_generated_references_are_up_to_date():
    for name, make in guide.GENERATED.items():
        assert guide.topic(name) == make(), f"run `python -m uberseek.guide` to regenerate {name}.md"


def test_every_function_the_skill_calls_exists():
    code = "\n".join(re.findall(r"```python\n(.*?)```", EVERYTHING, re.S))
    called = set(re.findall(r"(?<![\w.])([a-z_]+)\(", code))
    python = {"len", "sorted", "range", "open", "min", "max", "sum", "round", "abs", "int", "str", "print", "any", "list", "gen"}
    assert called - set(Library.OPERATIONS) - python == set()
    assert set(Library.OPERATIONS) <= called  # and every operation is shown in use somewhere


def test_what_it_says_about_looking_matches_the_code():
    looking = guide.topic("looking")
    assert all(f"`{focus}`" in looking and f"`{focus}`" in guide.core("harness") for focus in FOCUSES)
    assert f"Up to {LADDER['moment'][0]} seconds | Moment | Up to {LADDER['moment'][1]} frames" in looking
    assert f"Up to {LADDER['passage'][0]} seconds | Passage | Up to {LADDER['passage'][1]} frames" in looking
    assert f"Up to {LADDER['section'][0] // 60} minutes | Section" in looking and f"Map | {LADDER['map'][1]} equal slices" in looking


def test_the_limits_it_states_are_the_real_ones():
    programs, limits = guide.topic("programs"), Limits()
    assert f"| Running time | {limits.seconds:.0f} seconds" in programs and f"| Memory | {limits.memory // 2**20} MB" in programs
    assert f"| Library calls | {limits.calls} per program" in programs and f"| Looks | {limits.looks} per program" in programs
    assert f"| Result size | {limits.result:,} characters" in programs and f"| Printed text | {limits.printed:,} characters" in programs
    assert f"at most {'four' if limits.looks == 4 else limits.looks}" in guide.core("harness").replace("\n", " ")


@pytest.fixture(scope="module")
def spoken(tmp_path_factory, speech):
    """A project with the synthetic speech clip transcribed, for programs that search words."""
    pytest.importorskip("faster_whisper")
    pytest.importorskip("pydantic_monty")
    project = Project(tmp_path_factory.mktemp("skill"), transcript_model="tiny")
    try:
        project.transcribe(speech)
    except Exception as error:
        pytest.skip(f"the Whisper model could not be loaded: {error}")
    return project, speech


def _with(program: str, **values) -> str:
    """Set the lines at the top of a recipe, as its header tells the reader to."""
    for name, value in values.items():
        program, count = re.subn(rf"^{name} = .*$", f"{name} = {value!r}", program, count=1, flags=re.M)
        assert count == 1, f"the recipe has no line `{name} = ...`"
    return program


RECIPES = {
    "find_spoken": {"query": "money left"},
    "rank_candidates": {"queries": ["money left", "nobody believed"]},
    "cut_point": {"near": 4.0},
    "coverage_check": {},
    "find_picture": {"looking_for": "a test pattern"},
    "build_clip": {"query": "money left", "name": "recipe-clip"},
}


@pytest.mark.parametrize("name", sorted(RECIPES))
def test_every_recipe_runs_as_written(spoken, name):
    project, speech = spoken
    program = _with((guide.SKILL / "recipes" / f"{name}.py").read_text(), video="speech.mp4", **RECIPES[name])
    done = Executor(project, [speech]).run_sync(program)
    assert done.error is None, done.text
    assert done.looks, "a recipe looks at something"
    assert len(done.text.split("\n\n")[0]) < 2000  # and returns something small


def test_no_recipe_is_left_out():
    assert {path.stem for path in (guide.SKILL / "recipes").glob("*.py")} == set(RECIPES)


def test_the_example_of_every_operation_runs(spoken):
    project, speech = spoken
    for name in Library.OPERATIONS:
        done = Executor(project, [speech]).run_sync(guide.EXAMPLES[name].format(video="speech.mp4"))
        assert done.error is None, f"{name}: {done.text}"


def test_the_programs_shown_in_the_guide_run(spoken):
    project, speech = spoken
    blocks = re.findall(r"```python\n(.*?)```", guide.core("harness") + guide.topic("programs"), re.S)
    whole = [b for b in blocks if re.search(r'"(interview|reel)\.mp4"', b)]
    assert len(whole) == 11  # eight ways to combine steps, building a clip and keeping track in the core, and one in the guide to programs
    for program in whole:
        done = Executor(project, [speech]).run_sync(re.sub(r"(interview|reel)\.mp4", "speech.mp4", program))
        assert done.error is None, done.text
    spans = next(b for b in blocks if b.startswith("span = expand"))
    for line in spans.strip().splitlines():
        call, _, says = line.partition("#")
        value = Executor(project, [speech]).run_sync(call.split("= ", 1)[-1].strip()).result
        assert str(value) == says.split(":")[0].strip(), line


@pytest.mark.parametrize(
    ("program", "told"),
    [
        ("class Clip(dict):\n    pass", "class inheritance"),
        ("def gen():\n    yield 1\nlist(gen())", "yield"),
        ("import numpy", "No module named 'numpy'"),
        ('open("notes.txt")', "notes.txt"),
        ("import socket", "No module named 'socket'"),
        ('cuts("speech.mp4", 5, 2)', "the span ends (2) before it starts (5)"),
    ],
)
def test_what_the_guide_says_fails_does_fail(spoken, program, told):
    project, speech = spoken
    done = Executor(project, [speech]).run_sync(program)
    assert done.error and told in done.text


def test_the_harness_gives_the_core_and_serves_the_rest_on_request(clips, tmp_path):
    pytest.importorskip("pydantic_ai")
    from pydantic_ai import Agent
    from pydantic_ai.messages import ModelResponse, TextPart, ToolCallPart, ToolReturnPart
    from pydantic_ai.models.function import FunctionModel

    from uberseek.host.pydantic_ai import toolset

    seen = {}

    def model(messages, info):
        returns = [part for part in messages[-1].parts if isinstance(part, ToolReturnPart)]
        if not returns:
            seen["instructions"], seen["tools"] = info.instructions, {tool.name for tool in info.function_tools}
            return ModelResponse(parts=[ToolCallPart("guide", {"topic": "recipes"})])
        seen["guide"] = returns[0].content
        return ModelResponse(parts=[TextPart("ok")])

    Agent(FunctionModel(model), toolsets=[toolset(Project(tmp_path), [clips["bframes"]])]).run_sync("hi")
    assert "A number on a picture means that picture" in seen["instructions"] and "Using it from a shell" not in seen["instructions"]
    assert seen["instructions"].endswith("The videos you can use: bframes.mp4.")
    assert "guide" in seen["tools"] and seen["guide"] == guide.topic("recipes")

    def plain(messages, info):
        seen["plain"] = (info.instructions, {tool.name for tool in info.function_tools})
        return ModelResponse(parts=[TextPart("ok")])

    Agent(FunctionModel(plain), toolsets=[toolset(Project(tmp_path), [clips["bframes"]], skill=False)]).run_sync("hi")
    tools = {
        "find",
        "observe",
        "sheet",
        "execute",
        "show_again",
        "mark",
        "selections",
        "clip",
        "verify",
        "note",
        "brief",
        "status",
        "videos",
    }
    assert seen["plain"] == ("The videos you can use: bframes.mp4.", tools)


def test_the_command_line_serves_the_skill_and_runs_programs(clips, tmp_path, capsys):
    assert main(["guide"]) == 0 and "Using it from a shell" in capsys.readouterr().out
    assert main(["guide", "limits"]) == 0 and "It cannot hear" in capsys.readouterr().out
    assert main(["skill", "install", str(tmp_path / "skills")]) == 0
    assert (tmp_path / "skills" / "uberseek" / "SKILL.md").exists() and (
        tmp_path / "skills" / "uberseek" / "recipes" / "cut_point.py"
    ).exists()
    capsys.readouterr()

    program = tmp_path / "program.py"
    program.write_text('seen = observe("three_shots.mp4", 2, 3)\n{"cuts": cuts("three_shots.mp4")}')
    assert main(["--project", str(tmp_path), "run", str(program), "--video", str(clips["three_shots"])]) == 0
    out = capsys.readouterr().out
    assert out.startswith('{"cuts": [2.5, 4.5]}') and re.search(r"Picture: .*\.png", out)
    program.write_text('cuts("other.mp4")')
    assert main(["--project", str(tmp_path), "run", str(program), "--video", str(clips["three_shots"])]) == 1


def test_every_operation_is_a_command(clips, tmp_path, monkeypatch, capsys):
    """An agent in a shell reads the skill's operations as commands, so each one has to be one."""
    from uberseek.cli import COMMANDS, PLAIN

    assert set(Library.OPERATIONS) <= {*COMMANDS, *PLAIN}
    monkeypatch.chdir(clips["three_shots"].parent)
    run = ["--project", str(tmp_path)]
    assert main([*run, "cuts", "three_shots.mp4"]) == 0 and capsys.readouterr().out.strip() == "[2.5, 4.5]"
    assert main([*run, "pauses", "three_shots.mp4", "0", "0:03"]) == 0
    assert main([*run, "minus", "[0, 10]", "[[2, 3]]"]) == 0 and capsys.readouterr().out.strip().endswith("[[0, 2], [3, 10]]")
    assert main([*run, "sheet", "three_shots.mp4", "[1, 3, 5]", "purpose=one frame per shot"]) == 0
    assert "Picture: /" in capsys.readouterr().out
    assert main([*run, "videos"]) == 0 and "three_shots.mp4" in capsys.readouterr().out
    assert main([*run, "cuts", "three_shots.mp4", "5", "2"]) == 2  # a refused call says why, and fails


def test_the_card_names_only_commands_that_exist():
    from uberseek.cli import COMMANDS, PLAIN

    card = guide.topic("card")
    named = set(re.findall(r"`uberseek ([a-z_]+)", card))
    assert named and named <= {*COMMANDS, *PLAIN}
    assert len(card) < 4500  # it is loaded into every run, so it stays short
