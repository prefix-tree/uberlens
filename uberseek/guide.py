"""The skill: one description of what UberSeek can do, read by coding agents and by the host harness.

The folder `uberseek/skill/` is a standard Agent Skill. Two of its reference files are generated from
the code, so they cannot drift: the operations, from the library, and the recipes, from the programs in
`recipes/`.
"""

from __future__ import annotations

import inspect
import re
import shutil
from pathlib import Path

from uberseek.api.library import Library, signature

SKILL = Path(__file__).parent / "skill"
TOPICS = ("operations", "looking", "programs", "recipes", "limits")

# One call of each operation, as it would be written in a program.
EXAMPLES = {
    "info": 'info("{video}")',
    "find": 'find("{video}", "company almost failed", after=60, limit=5)',
    "words": 'words("{video}", 1, 4)',
    "pauses": 'pauses("{video}", 0, 5)',
    "loudness": 'loudness("{video}", 0, 2)',
    "cuts": 'cuts("{video}")',
    "shots": 'shots("{video}", 0, 5)',
    "observe": 'observe("{video}", 1, 4, "delivery", "where does the line start?")',
    "observations": 'observations("{video}", focus="delivery")',
    "coverage": 'coverage("{video}", 0, 5)',
    "expand": "expand([10, 14], before=2, after=3)",
    "merge": "merge([[1, 2], [1.5, 3], [5, 6]], gap=0.5)",
    "minus": "minus([0, 10], [[2, 3], [5, 12]])",
}


def description() -> dict[str, str]:
    """The skill's name and description, from the top of SKILL.md."""
    head = (SKILL / "SKILL.md").read_text().split("---")[1]
    return dict(line.split(": ", 1) for line in head.strip().splitlines())


def core(route: str) -> str:
    """The body of SKILL.md for one way of using it: "harness" (tools) or "shell" (the command line)."""
    body = (SKILL / "SKILL.md").read_text().split("---", 2)[2]
    other = "shell" if route == "harness" else "harness"
    body = re.sub(rf"<!-- {other} -->.*?<!-- /{other} -->\n", "", body, flags=re.S)
    return re.sub(r"<!-- /?\w+ -->\n", "", body).strip()


def topic(name: str) -> str:
    """One reference file of the skill."""
    if name not in TOPICS:
        raise ValueError(f"no topic {name!r}. Topics: {', '.join(TOPICS)}")
    return (SKILL / "references" / f"{name}.md").read_text()


def operations() -> str:
    """The operations reference, written from the library itself."""
    out = [
        "# Operations",
        "",
        "Every function of the library, generated from the code. Times are seconds; a span is `[start, end]`.",
        "A `video` is a file's name. A call that cannot be served raises `ValueError` and says what to change.",
        "",
    ]
    for name in Library.OPERATIONS:
        function = getattr(Library, name)
        out += [f"## `{name}`", "", "```python", f"{name}{signature(function)}", "```", "", inspect.getdoc(function), ""]
        out += ["Example:", "", "```python", EXAMPLES[name].format(video="interview.mp4"), "```", ""]
    return "\n".join(out)


def recipes() -> str:
    """The recipes reference, written from the programs in `recipes/`."""
    out = [
        "# Recipes",
        "",
        "Worked programs for common jobs. Each is a file in `recipes/` next to this folder and runs as written:",
        "set the lines at the top, then run it (`execute`, or `uberseek run recipes/<name>.py --video <file>`).",
        "They are starting points: change the measurements and the looks to fit the job.",
        "",
    ]
    for path in sorted((SKILL / "recipes").glob("*.py")):
        text = path.read_text()
        title = text.splitlines()[0].lstrip("# ").rstrip(".")
        out += [f"## {title}", "", f"`recipes/{path.name}`", "", "```python", text.rstrip(), "```", ""]
    return "\n".join(out)


GENERATED = {"operations": operations, "recipes": recipes}


def write_generated() -> None:
    for name, make in GENERATED.items():
        (SKILL / "references" / f"{name}.md").write_text(make())


def install(folder: Path) -> Path:
    """Copy the skill into `folder/uberseek`, where an agent that reads skills will find it."""
    target = Path(folder) / "uberseek"
    shutil.copytree(SKILL, target, dirs_exist_ok=True, ignore=shutil.ignore_patterns("__pycache__"))
    return target


if __name__ == "__main__":
    write_generated()
