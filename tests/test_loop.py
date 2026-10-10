"""Bounded loop tests with deterministic synthetic LLM responses."""

from collections import deque
from typing import Any

import pytest

from agentx.llm.contracts import LLMResponse, ToolCall, ToolSpec, Usage
from agentx.loop.runner import AgentRunner, RunLimits, collapse_context
from agentx.tools.builtins import make_registry


class FakeLLM:
    def __init__(self, replies: list[LLMResponse]) -> None:
        self.replies = deque(replies)
        self.messages: list[list[dict[str, Any]]] = []

    async def complete(
        self,
        messages: list[dict[str, Any]],
        tools: list[ToolSpec],
        *,
        max_tokens: int = 512,
        temperature: float = 0,
    ) -> LLMResponse:
        self.messages.append(messages)
        return self.replies.popleft()


def response(text: str = "", calls: list[ToolCall] | None = None) -> LLMResponse:
    return LLMResponse(
        text=text, tool_calls=calls or [],
        usage=Usage(input_tokens=3, output_tokens=2), stop_reason="stop",
    )


@pytest.mark.asyncio
async def test_single_tool_then_final(tmp_path: Any) -> None:
    c = ToolCall(id="id1", name="calculator", arguments={"expression": "2+2"})
    client = FakeLLM([response(calls=[c]), response('{"answer":"4","citations":["id1"]}')])
    run = await AgentRunner(
        client, make_registry(tmp_path), allowed_tools={"calculator"}
    ).run("calculate 2+2")
    assert run.outcome == "completed"
    assert run.answer == "4"
    assert run.citations == ["id1"]


@pytest.mark.asyncio
async def test_denied_tool_and_unverified_citation(tmp_path: Any) -> None:
    client = FakeLLM([response('{"answer":"done","citations":["imaginary"]}')])
    run = await AgentRunner(client, make_registry(tmp_path), allowed_tools=set()).run("task")
    assert run.outcome == "invalid_final"


@pytest.mark.asyncio
async def test_step_cap(tmp_path: Any) -> None:
    c = ToolCall(id="id1", name="calculator", arguments={"expression": "2+2"})
    client = FakeLLM([response(calls=[c])])
    runner = AgentRunner(
        client, make_registry(tmp_path), allowed_tools={"calculator"},
        limits=RunLimits(max_steps=1),
    )
    assert (await runner.run("task")).outcome == "budget_exceeded"


@pytest.mark.asyncio
async def test_token_cap(tmp_path: Any) -> None:
    client = FakeLLM([response("done")])
    runner = AgentRunner(
        client, make_registry(tmp_path), allowed_tools=set(),
        limits=RunLimits(max_tokens=5),
    )
    assert (await runner.run("task")).outcome == "budget_exceeded"


@pytest.mark.asyncio
async def test_model_asks_user(tmp_path: Any) -> None:
    client = FakeLLM([response("Which account?")])
    result = await AgentRunner(client, make_registry(tmp_path), allowed_tools=set()).run("task")
    assert result.outcome == "ask_user"


@pytest.mark.asyncio
async def test_loop_detection(tmp_path: Any) -> None:
    same = ToolCall(id="id1", name="calculator", arguments={"expression": "2+2"})
    client = FakeLLM([response(calls=[same]) for _ in range(5)])
    result = await AgentRunner(
        client, make_registry(tmp_path), allowed_tools={"calculator"}
    ).run("task")
    assert result.outcome == "loop_detected"


def test_context_preserves_system_and_task() -> None:
    messages = [
        {"role": "system", "content": "do not leak"},
        {"role": "user", "content": "original task"},
        {"role": "user", "content": "x" * 800},
        {"role": "assistant", "content": "y" * 800},
        {"role": "user", "content": "last tool"},
    ]
    reduced = collapse_context(messages, max_chars=500)
    assert reduced[0] == messages[0]
    assert reduced[1] == messages[1]
    assert reduced[-1] == messages[-1]
