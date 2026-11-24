"""The host harness carries the picture to the model inside the tool result.

No model is called. A scripted model stands in for the agent, and for each provider the request that
would go over the network is captured and inspected.
"""

from __future__ import annotations

import base64
import json
import os

import pytest

os.environ["PYDANTIC_AI_NO_BANNER"] = "1"
pytest.importorskip("pydantic_ai")

import httpx2 as httpx  # noqa: E402
from pydantic_ai import Agent, BinaryContent  # noqa: E402
from pydantic_ai.messages import ModelResponse, TextPart, ToolCallPart, ToolReturnPart  # noqa: E402
from pydantic_ai.models.function import FunctionModel  # noqa: E402

from uberseek import Project  # noqa: E402
from uberseek.host.pydantic_ai import toolset  # noqa: E402


def test_a_scripted_agent_receives_the_picture_it_asked_for(clips, tmp_path):
    project = Project(tmp_path)
    received = []

    def model(messages, info):
        returns = [part for part in messages[-1].parts if isinstance(part, ToolReturnPart)]
        if not returns:
            assert {tool.name for tool in info.function_tools} == {
                "find",
                "observe",
                "sheet",
                "execute",
                "show_again",
                "guide",
                "mark",
                "selections",
                "clip",
                "verify",
                "note",
                "brief",
                "status",
                "videos",
            }
            call = {"video": str(clips["bframes"]), "start": 1, "end": 4, "purpose": "is the bar moving?"}
            return ModelResponse(parts=[ToolCallPart("observe", call)])
        received.extend(returns[0].content)
        return ModelResponse(parts=[TextPart("seen")])

    result = Agent(FunctionModel(model), toolsets=[toolset(project)]).run_sync("Look at the clip.")

    text, picture = received
    assert result.output == "seen"
    assert text.startswith("obs_000001") and "16 frames" in text
    assert isinstance(picture, BinaryContent) and picture.media_type == "image/png"
    (logged,) = project.log.observations()
    assert picture.data == project.log.artifact(logged["artifact"]["sha256"], ".png")
    assert logged["request"]["purpose"] == "is the bar moving?"


def test_a_bad_request_goes_back_to_the_model_as_something_to_fix(clips, tmp_path):
    said = []

    def model(messages, info):
        last = messages[-1].parts[-1]
        if last.part_kind == "user-prompt":
            return ModelResponse(parts=[ToolCallPart("observe", {"video": "missing.mp4", "start": 1})])
        said.append(str(last.content))
        return ModelResponse(parts=[TextPart("gave up")])

    Agent(FunctionModel(model), toolsets=[toolset(Project(tmp_path))]).run_sync("Look.")
    assert "missing.mp4" in said[0]


def test_a_program_run_by_the_agent_returns_its_result_and_its_pictures(clips, tmp_path):
    pytest.importorskip("pydantic_monty")
    project, received = Project(tmp_path), []
    program = "\n".join(
        [
            'shots = cuts("three_shots.mp4")',
            'seen = observe("three_shots.mp4", shots[0] - 1, shots[0] + 1)',
            '{"cuts": shots, "looked": seen["id"]}',
        ]
    )

    def model(messages, info):
        returns = [part for part in messages[-1].parts if isinstance(part, ToolReturnPart)]
        if not returns:
            assert (info.instructions or "").endswith("The videos you can use: three_shots.mp4.")
            return ModelResponse(parts=[ToolCallPart("execute", {"program": program})])
        received.extend(returns[0].content)
        return ModelResponse(parts=[TextPart("done")])

    Agent(FunctionModel(model), toolsets=[toolset(project, [clips["three_shots"]])]).run_sync("Where are the cuts?")

    text, picture = received
    assert text.startswith('{"cuts": [2.5, 4.5], "looked": "obs_000001"}') and "obs_000001: three_shots.mp4" in text
    assert isinstance(picture, BinaryContent) and picture.data.startswith(b"\x89PNG")
    (run,) = project.log.executions()
    assert run["observations"] == ["obs_000001"] and [call["name"] for call in run["calls"]] == ["cuts", "observe"]


def test_the_plain_surface_offers_one_operation_at_a_time(clips, tmp_path):
    asked = []

    def model(messages, info):
        returns = [part for part in messages[-1].parts if isinstance(part, ToolReturnPart)]
        if not returns:
            asked.extend(sorted(tool.name for tool in info.function_tools))
            return ModelResponse(parts=[ToolCallPart("cuts", {"video": "three_shots.mp4"})])
        return ModelResponse(parts=[TextPart(str(returns[0].content))])

    result = Agent(FunctionModel(model), toolsets=[toolset(Project(tmp_path), [clips["three_shots"]], surface="tools")]).run_sync("Cuts?")
    plain = ["coverage", "cuts", "find", "guide", "observe", "pauses", "sheet", "show_again", "words"]
    assert asked == sorted([*plain, "mark", "selections", "clip", "verify", "note", "brief", "status", "videos"])
    assert result.output == "[2.5, 4.5]"


@pytest.mark.parametrize("surface", ["code", "tools"])
def test_a_sheet_comes_back_as_one_picture_on_either_surface(clips, tmp_path, surface):
    received = []

    def model(messages, info):
        returns = [part for part in messages[-1].parts if isinstance(part, ToolReturnPart)]
        if not returns:
            call = {"video": "three_shots.mp4", "times": [1, 3.5, 5], "labels": ["one", "two", "three"]}
            return ModelResponse(parts=[ToolCallPart("sheet", call)])
        received.extend(returns[0].content)
        return ModelResponse(parts=[TextPart("ok")])

    Agent(FunctionModel(model), toolsets=[toolset(Project(tmp_path), [clips["three_shots"]], surface)]).run_sync("Compare the shots.")
    text, picture = received
    assert "a sheet of 3 frames" in text and "(two)" in text
    assert isinstance(picture, BinaryContent) and picture.data.startswith(b"\x89PNG")


def test_an_agent_builds_and_checks_a_clip_through_the_host(clips, tmp_path):
    project, steps, told = (
        Project(tmp_path),
        iter(
            [
                ("observe", {"video": "bframes.mp4", "start": 1, "focus": "boundary"}),
                ("mark", {"video": "bframes.mp4", "start": 1, "end": 2, "reason": "the tone before the silence"}),
                ("clip", {"selections": ["sel_000001"], "name": "tone"}),
                ("verify", {"clip": "tone"}),
                ("observe", {"video": "tone.mp4", "start": 0, "end": 1}),
            ]
        ),
        [],
    )

    def model(messages, info):
        told.extend(part.content for part in messages[-1].parts if isinstance(part, ToolReturnPart))
        step = next(steps, None)
        return ModelResponse(parts=[ToolCallPart(*step)] if step else [TextPart("done")])

    Agent(FunctionModel(model), toolsets=[toolset(project, [clips["bframes"]])]).run_sync("Make a one-second clip of the tone.")
    _, marked, made, checked, look = told
    assert marked["edges_not_seen"] == ["out"] and marked["rests_on"] == ["obs_000001"]
    assert made["clip"] == "tone.mp4" and checked["ok"] and "without a look" in checked["warnings"][0]
    assert look[0].startswith("obs_000002: tone.mp4") and isinstance(look[1], BinaryContent)
    assert [clip["name"] for clip in project.log.clips()] == ["tone"]


def _pictures(messages) -> list[int]:
    """How many pictures each request in a history carries."""
    counts = []
    for message in messages:
        if message.kind == "request":
            returned = [part.content for part in message.parts if isinstance(part, ToolReturnPart) and isinstance(part.content, list)]
            counts.append(sum(isinstance(item, BinaryContent) for content in returned for item in content))
    return counts


@pytest.mark.parametrize("forget", [True, False])
def test_a_picture_stays_for_one_step_and_its_note_stays_for_good(clips, tmp_path, forget):
    from uberseek.host.pydantic_ai import harness

    project, seen_by_model = Project(tmp_path), []
    steps = iter(
        [
            ("observe", {"video": "bframes.mp4", "start": 1, "end": 2}),
            ("note", {"observation": "obs_000001", "text": "the bar sweeps right; nothing else moves"}),
            ("observe", {"video": "bframes.mp4", "start": 3, "end": 4}),
            ("observe", {"video": "bframes.mp4", "start": 4, "end": 5}),
        ]
    )

    def model(messages, info):
        seen_by_model.append((_pictures(messages), str([part.content for m in messages if m.kind == "request" for part in m.parts])))
        step = next(steps, None)
        return ModelResponse(parts=[ToolCallPart(*step)] if step else [TextPart("done")])

    agent = Agent(FunctionModel(model), capabilities=harness(project, [clips["bframes"]], forget=forget))
    result = agent.run_sync("Look at three parts of the clip.")
    counts = [pictures for pictures, _ in seen_by_model]
    if not forget:
        assert counts[-1] == [0, 1, 0, 1, 1]  # every picture is sent again on every later request
        return
    # Each picture is sent once, in the request right after its look, and is gone from every later one.
    assert counts == [[0], [0, 1], [0, 0, 0], [0, 0, 0, 1], [0, 0, 0, 0, 1]]
    last = seen_by_model[-1][1]
    assert "obs_000001: note: the bar sweeps right; nothing else moves" in last
    assert "obs_000002: no note was written" in last and "show_again(id) shows one again" in last
    assert "This picture leaves your context after your next step" in seen_by_model[1][1]
    assert _pictures(result.all_messages()) == [0, 0, 0, 0, 1]  # and the history kept for later is the short one


def test_a_plain_tool_cannot_flood_the_context_either(clips, tmp_path):
    from uberseek.exec import Limits

    told = []

    def model(messages, info):
        returns = [part for part in messages[-1].parts if isinstance(part, ToolReturnPart)]
        if not returns:
            return ModelResponse(parts=[ToolCallPart("cuts", {"video": "ten_shots.mp4"})])
        told.append(returns[0].content)
        return ModelResponse(parts=[TextPart("ok")])

    tools = toolset(Project(tmp_path), [clips["ten_shots"]], surface="tools", limits=Limits(result=30))
    Agent(FunctionModel(model), toolsets=[tools]).run_sync("Cuts?")
    assert told[0].startswith("[8.0, 16.0, 24.0, 32.0, 40.0,") and "[result cut at 30 of" in told[0] and "ask for less" in told[0]


# What each provider's API is sent. A fake server answers twice: first with a call to `observe`, then with text.


def _capture(replies: list) -> tuple[httpx.AsyncClient, list[dict]]:
    sent: list[dict] = []

    def handler(request: httpx.Request) -> httpx.Response:
        sent.append(json.loads(request.content))
        reply = replies[len(sent) - 1]
        if isinstance(reply, dict):
            return httpx.Response(200, json=reply)
        return httpx.Response(200, text=reply, headers={"content-type": "text/event-stream"})

    return httpx.AsyncClient(transport=httpx.MockTransport(handler)), sent


def _call(clips) -> dict:
    return {"video": str(clips["bframes"]), "start": 1, "end": 4}


def test_anthropic_gets_the_picture_inside_the_tool_result(clips, tmp_path):
    pytest.importorskip("anthropic")
    from pydantic_ai.models.anthropic import AnthropicModel
    from pydantic_ai.providers.anthropic import AnthropicProvider

    def stream(block: dict, delta: dict, stop: str) -> str:
        """One reply as the server-sent events the adapter reads."""
        usage = {"input_tokens": 1, "output_tokens": 1}
        message = {"id": "m", "type": "message", "role": "assistant", "model": "m", "content": [], "stop_reason": None, "usage": usage}
        events = [
            {"type": "message_start", "message": message},
            {"type": "content_block_start", "index": 0, "content_block": block},
            {"type": "content_block_delta", "index": 0, "delta": delta},
            {"type": "content_block_stop", "index": 0},
            {"type": "message_delta", "delta": {"stop_reason": stop}, "usage": {"output_tokens": 1}},
            {"type": "message_stop"},
        ]
        return "".join(f"event: {e['type']}\ndata: {json.dumps(e)}\n\n" for e in events)

    client, sent = _capture(
        [
            stream(
                {"type": "tool_use", "id": "call_1", "name": "observe", "input": {}},
                {"type": "input_json_delta", "partial_json": json.dumps(_call(clips))},
                "tool_use",
            ),
            stream({"type": "text", "text": ""}, {"type": "text_delta", "text": "seen"}, "end_turn"),
        ]
    )
    model = AnthropicModel("claude-sonnet-5-5", provider=AnthropicProvider(api_key="none", http_client=client))
    Agent(model, toolsets=[toolset(Project(tmp_path))]).run_sync("Look at the clip.")

    (result,) = [block for block in sent[1]["messages"][-1]["content"] if block["type"] == "tool_result"]
    kinds = [block["type"] for block in result["content"]]
    assert result["tool_use_id"] == "call_1" and kinds == ["text", "image"]
    image = result["content"][1]["source"]
    assert image["media_type"] == "image/png" and base64.b64decode(image["data"]).startswith(b"\x89PNG")


def test_openai_responses_gets_the_picture_inside_the_tool_output(clips, tmp_path):
    pytest.importorskip("openai")
    from pydantic_ai.models.openai import OpenAIResponsesModel
    from pydantic_ai.providers.openai import OpenAIProvider

    def reply(output):
        return {"id": "r", "object": "response", "created_at": 0, "model": "m", "status": "completed", "output": output,
                "parallel_tool_calls": True, "tool_choice": "auto", "tools": [],
                "usage": {"input_tokens": 1, "output_tokens": 1, "total_tokens": 2,
                          "input_tokens_details": {"cached_tokens": 0}, "output_tokens_details": {"reasoning_tokens": 0}}}  # fmt: skip

    call = {
        "type": "function_call",
        "id": "fc_1",
        "call_id": "call_1",
        "name": "observe",
        "arguments": json.dumps(_call(clips)),
        "status": "completed",
    }
    text = {"type": "message", "id": "msg_1", "role": "assistant", "status": "completed",
            "content": [{"type": "output_text", "text": "seen", "annotations": []}]}  # fmt: skip
    client, sent = _capture([reply([call]), reply([text])])
    model = OpenAIResponsesModel("gpt-5", provider=OpenAIProvider(api_key="none", http_client=client))
    Agent(model, toolsets=[toolset(Project(tmp_path))]).run_sync("Look at the clip.")

    (output,) = [item for item in sent[1]["input"] if item.get("type") == "function_call_output"]
    kinds = [part["type"] for part in output["output"]]
    assert kinds == ["input_text", "input_image"]
    assert output["output"][1]["image_url"].startswith("data:image/png;base64,")
