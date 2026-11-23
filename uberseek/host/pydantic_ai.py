"""UberSeek's tools for Pydantic AI, the host harness.

UberSeek has no agent loop of its own: Pydantic AI drives the model and calls these tools. `observe`
returns its picture inside the tool result, next to the text that says what the picture shows.
"""

from __future__ import annotations

from typing import Literal

from pydantic_ai import BinaryContent, ModelRetry
from pydantic_ai.toolsets import FunctionToolset

from uberseek import Project
from uberseek.media import MediaError

Focus = Literal["visual", "speech", "motion", "delivery", "boundary"]


def toolset(project: Project) -> FunctionToolset:
    """The tools to give an agent: `Agent(model, toolsets=[toolset(project)])`."""

    def observe(video: str, start: str, end: str | None = None, focus: Focus = "visual", purpose: str = "") -> list:
        """Look at a span of a video. You get one picture: numbered frames in time order and, where it helps, the sound drawn as a strip.

        You choose the span and the focus; how many frames and how large is chosen for you, and the reply
        says exactly what was shown. You cannot hear: sound is only drawn.

        Args:
            video: Path of the video file.
            start: Where the span starts, in seconds or as H:MM:SS.mmm.
            end: Where it ends. Leave out to see the single frame showing at `start`.
            focus: What the look is for. visual: what is in the picture. motion: how something moves, as
                dense frames. speech or delivery: where sound and pauses are, with a few frames. boundary:
                the frames and sound right around one instant, to judge a cut point.
            purpose: The question this look should answer, in a few words. It is kept in the log.
        """
        try:
            seen = project.observe(video, start, end, focus, purpose)
        except (MediaError, ValueError, FileNotFoundError) as error:
            raise ModelRetry(str(error)) from error
        return [seen.text, BinaryContent(data=seen.image, media_type=seen.media_type)]

    def show_again(observation: str) -> list:
        """Show a past observation again by its id (obs_000012), from the stored picture.

        Args:
            observation: The id of the observation.
        """
        try:
            seen = project.show(observation)
        except (KeyError, ValueError) as error:
            raise ModelRetry(str(error)) from error
        return [seen.text, BinaryContent(data=seen.image, media_type=seen.media_type)]

    return FunctionToolset([observe, show_again])
