import json
import sys
from pathlib import Path

import pytest
from mcp import ClientSession, StdioServerParameters
from mcp.client.stdio import stdio_client
from slimconfig import plain_output
from test_verifier import make_report

from contract import QuestionId, SelectionInput, StudentId

ROOT = Path(__file__).resolve().parents[1]


@pytest.fixture
def anyio_backend():
    return "asyncio"


@pytest.mark.anyio
async def test_mcp_round_trip():
    command = StdioServerParameters(command=sys.executable, args=["-m", "plugin"], cwd=ROOT)
    async with stdio_client(command) as (read, write), ClientSession(read, write) as client:
        await client.initialize()
        tools = await client.list_tools()
        assert {tool.name for tool in tools.tools} == {
            "list_exam",
            "get_submission",
            "evaluate_expression",
            "pin_minimum",
        }
        catalog = await client.call_tool("list_exam", {})
        assert not catalog.isError
        assert len(catalog.structuredContent["questions"]) == len(catalog.structuredContent["student_ids"]) == 5
        selection = {"question_id": "garden-watering", "student_id": "synthetic-04"}
        given = await client.call_tool("get_submission", selection)
        assert not given.isError
        assert given.structuredContent["original_expression"] == "F AND R"
        evaluated = await client.call_tool(
            "evaluate_expression", {"question_id": selection["question_id"], "expression": "F AND D AND NOT R"}
        )
        assert not evaluated.isError
        assert evaluated.structuredContent["outputs"] == given.structuredContent["reference_outputs"]
        reference = await client.call_tool("pin_minimum", selection)
        assert not reference.isError and reference.structuredContent["minimum_edits"] == 2
        invalid = await client.call_tool("get_submission", {**selection, "student_id": "unknown"})
        assert invalid.isError


@pytest.mark.anyio
async def test_nanoagent_pins_then_grades(tmp_path, monkeypatch):
    pytest.importorskip("nanoagent", reason="The NanoAgent host is optional for plugin development.")
    from nanoagent.core.agent import Agent, Reply, ToolCall
    from nanoagent.plugin import runtime
    from nanoagent.plugin.manifest import load_manifest
    from nanoagent.plugin.tasks import run_task

    plugin_env = runtime.plugin_env
    monkeypatch.setattr(
        runtime,
        "plugin_env",
        lambda manifest, workspace: {
            **plugin_env(manifest, workspace),
            "UV_NO_SYNC": "1",
            "UV_OFFLINE": "1",
            "UV_NO_CACHE": "1",
        },
    )
    manifest = load_manifest(ROOT)
    selection = SelectionInput(QuestionId.GARDEN_WATERING, StudentId.STUDENT_04)
    arguments = plain_output(selection)
    report = plain_output(make_report(selection))
    steps = iter(
        [
            ("get_submission", arguments),
            (
                "evaluate_expression",
                {"question_id": arguments["question_id"], "expression": report["original_expression"]},
            ),
            (
                "evaluate_expression",
                {"question_id": arguments["question_id"], "expression": report["corrected_expression"]},
            ),
            ("submit", report),
        ]
    )
    events = []

    class ScriptedModel:
        async def query(self, messages, tools, **kwargs):
            assert {tool["function"]["name"] for tool in tools} == {"get_submission", "evaluate_expression", "submit"}
            assert any(kind == "task.reference" for kind, _ in events)
            step = next(steps, None)
            if step is None:
                return Reply(content="Done.")
            name, payload = step
            return Reply(content=None, tool_calls=[ToolCall(f"call-{name}-{len(events)}", name, json.dumps(payload))])

    outcome = await run_task(
        manifest,
        manifest.task("grade-answer"),
        arguments,
        tmp_path,
        make_agent=lambda system: Agent(ScriptedModel(), [], system_prompt=system, max_steps=6),
        make_decider=None,
        timeout=15,
        on_event=lambda kind, data: events.append((kind, data)),
        stage=lambda folder: None,
    )
    assert outcome.reference["minimum_edits"] == 2
    assert outcome.output == report
    assert outcome.verdict.valid, outcome.verdict.message
    tool_events = [data for kind, data in events if kind == "task.tool"]
    assert [event["name"] for event in tool_events] == [
        "get_submission",
        "evaluate_expression",
        "evaluate_expression",
        "submit",
    ]
    assert not any(event["isError"] for event in tool_events)
