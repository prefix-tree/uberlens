"""UberSeek's tools for Pydantic AI, the host harness.

UberSeek has no agent loop of its own: Pydantic AI drives the model and calls these tools. There are two
surfaces over the same library, so they can be compared: `code`, where the model writes programs, and
`tools`, where it calls one operation at a time. Either way a picture comes back inside the tool result.
"""

from __future__ import annotations

import functools
import json
import re
from dataclasses import replace
from pathlib import Path
from typing import Literal

from pydantic_ai import BinaryContent, ModelRetry, Tool
from pydantic_ai.capabilities import ProcessHistory, Toolset
from pydantic_ai.messages import ModelMessage, ModelRequest, ModelResponse, ToolReturnPart
from pydantic_ai.toolsets import FunctionToolset

from uberseek import Project, guide
from uberseek.api import ApiError, Library
from uberseek.exec import Executor, Limits
from uberseek.exec.executor import clip
from uberseek.observe.gateway import Observation

Surface = Literal["code", "tools"]
PLAIN = ("find", "words", "pauses", "cuts", "coverage")  # the operations offered one at a time on the `tools` surface
BUILD = ("mark", "selections", "clip", "verify")  # building a clip: on both surfaces
TRACK = ("note", "brief", "status", "videos")  # keeping track of a task: on both surfaces

KEEP = "This picture leaves your context after your next step. Keep what you conclude from it: note(id, what you concluded)."

EXECUTE = """Run a short Python program against the video library and get back its result.

Use it to search, measure, filter and combine: the working data stays in the program, and only the value
of its last expression comes back, so return something small (a few candidates, a count, a decision).
A program cannot see. Call observe(...) in it to look at up to {looks} spans; their pictures are shown
to you with the result.

The Python is a subset: no imports beyond the standard basics (math, json, re), no class inheritance, no
generators. The functions below are already defined; call them directly, without await. Times are seconds.

{reference}"""


def _picture(seen: Observation) -> BinaryContent:
    return BinaryContent(data=seen.image, media_type=seen.media_type)


def _retrying(function, limit: int | None = None):
    """A request the library refuses goes back to the model as something to fix.

    With a limit, a large result is cut and says so, exactly as a program's result is: what one call may
    put into the model's context is the same on both surfaces.
    """

    @functools.wraps(function)
    def call(*args, **kwargs):
        try:
            result = function(*args, **kwargs)
        except ApiError as error:
            raise ModelRetry(str(error)) from error
        text = json.dumps(result, default=str)
        return result if limit is None or len(text) <= limit else clip(text, limit, "result")

    return call


def toolset(
    project: Project,
    videos: list[Path | str] | None = None,
    surface: Surface = "code",
    limits: Limits | None = None,
    skill: bool = True,
    forget: bool = False,
) -> FunctionToolset:
    """The tools to give an agent: `Agent(model, toolsets=[toolset(project, videos)])`.

    `videos` are the files the agent may use, by name; leave it out to allow any path. With `skill`,
    the agent is also given the UberSeek skill: its core as instructions, and a `guide` tool for the rest.
    With `forget`, each look says that its picture will not stay; use it together with `forget_pictures`,
    or take both at once from `harness`.
    """
    reminder = [KEEP] if forget else []
    library, limits = Library(project, videos), limits or Limits()
    names = ", ".join(library.allowed) if library.allowed else None
    notes = "\n\n".join(
        part for part in (guide.core("harness") if skill else "", f"The videos you can use: {names}." if names else "") if part
    )

    def read_guide(topic: Literal["operations", "looking", "programs", "recipes", "limits"]) -> str:
        """Read one part of the UberSeek guide.

        Args:
            topic: operations (every function, its arguments and what it returns), looking (spans, focus
                and how to read a picture), programs (writing programs, limits, errors), recipes (worked
                programs for common jobs), limits (what UberSeek cannot do).
        """
        return guide.topic(topic)

    extra = [
        *(_retrying(getattr(library, name), limits.result) for name in (*BUILD, *TRACK)),
        *([Tool(read_guide, name="guide")] if skill else []),
    ]

    @functools.wraps(library.observe)
    def observe(*args, **kwargs) -> list:
        text = _retrying(library.observe)(*args, **kwargs)["text"]
        return [text, *reminder, _picture(library.looks.pop())]

    @functools.wraps(library.sheet)
    def sheet(*args, **kwargs) -> list:
        text = _retrying(library.sheet)(*args, **kwargs)["text"]
        return [text, *reminder, _picture(library.looks.pop())]

    def show_again(observation: str) -> list:
        """Show a past observation again by its id (obs_000012), from the stored picture.

        Args:
            observation: The id of the observation.
        """
        try:
            seen = project.show(observation)
        except (KeyError, ValueError) as error:
            raise ModelRetry(str(error)) from error
        return [seen.text, _picture(seen)]

    seen_now = ("after the program ends; a program cannot see it", "in the reply")
    look = Tool(observe, description=library.observe.__doc__.replace(*seen_now))
    plot = Tool(sheet, description=library.sheet.__doc__.replace(*seen_now))
    if surface == "tools":
        return FunctionToolset(
            [look, plot, show_again, *(_retrying(getattr(library, name), limits.result) for name in PLAIN), *extra],
            instructions=notes or None,
        )

    executor = Executor(project, videos, limits)

    async def execute(program: str) -> list:
        """Run a program."""
        done = await executor.run(program)
        return [done.text, *(reminder if done.looks else []), *(_picture(seen) for seen in done.looks)]

    description = EXECUTE.format(looks=executor.limits.looks, reference=executor.reference())
    return FunctionToolset(
        [_retrying(library.find, limits.result), look, plot, Tool(execute, description=description), show_again, *extra],
        instructions=notes or None,
    )


def forget_pictures(project: Project):
    """A history processor: once the model has answered after seeing a picture, the picture is taken out of the history.

    Its id and its text stay, with the note written about it, so nothing that cannot be recovered is lost:
    a picture can be shown again by its id, and a conclusion lives in its note. Without this, every picture
    is sent again on every later request, and the cost of a task grows with each look.
    """

    def process(messages: list[ModelMessage]) -> list[ModelMessage]:
        answered = max((i for i, message in enumerate(messages) if isinstance(message, ModelResponse)), default=-1)
        notes, out = None, []
        for i, message in enumerate(messages):
            if i > answered or not isinstance(message, ModelRequest):
                out.append(message)  # what the model has not answered yet is left as it is
                continue
            parts = []
            for part in message.parts:
                content = part.content if isinstance(part, ToolReturnPart) else None
                if not isinstance(content, list) or not any(isinstance(item, BinaryContent) for item in content):
                    parts.append(part)
                    continue
                notes = project.log.notes() if notes is None else notes
                kept = [item for item in content if not isinstance(item, BinaryContent) and item != KEEP]
                ids = list(dict.fromkeys(re.findall(r"obs_\d+", " ".join(str(item) for item in kept))))
                gone = [f"{id}: note: {notes[id]}" if id in notes else f"{id}: no note was written" for id in ids]
                kept.append("[The pictures are no longer in your context. " + "; ".join(gone) + ". show_again(id) shows one again.]")
                parts.append(replace(part, content=kept))
            out.append(replace(message, parts=parts))
        return out

    return process


def harness(
    project: Project,
    videos: list[Path | str] | None = None,
    surface: Surface = "code",
    limits: Limits | None = None,
    skill: bool = True,
    forget: bool = True,
) -> list:
    """Everything an agent needs, as capabilities: `Agent(model, capabilities=harness(project, videos))`.

    The tools, the skill, and with `forget` the rule that a picture stays in the context for one step only.
    """
    tools = Toolset(toolset(project, videos, surface, limits, skill, forget))
    return [tools, ProcessHistory(forget_pictures(project))] if forget else [tools]
