"""End-to-end offline checks for both provider tool-call formats."""

import json
from pathlib import Path
from typing import Any

import httpx
import pytest

from agentx.llm.adapters import (
    AnthropicAdapter,
    OpenAICompatibleAdapter,
    ProviderProtocolError,
)
from agentx.llm.transcript import TranscriptError, anthropic_messages, openai_messages
from agentx.loop.runner import AgentRunner
from agentx.tools.builtins import make_registry


@pytest.mark.asyncio
@pytest.mark.parametrize("provider", ["openai", "anthropic"])
async def test_two_turn_provider_tool_round_trip(provider: str, tmp_path: Path) -> None:
    """A model's next request must contain the actual tool call and result."""
    requests: list[dict[str, Any]] = []

    def handler(request: httpx.Request) -> httpx.Response:
        payload = json.loads(request.content)
        requests.append(payload)
        if len(requests) == 1:
            if provider == "openai":
                return httpx.Response(
                    200,
                    json={
                        "choices": [{
                            "message": {
                                "content": None,
                                "tool_calls": [{
                                    "id": "call-1",
                                    "type": "function",
                                    "function": {
                                        "name": "calculator",
                                        "arguments": '{"expression":"2+2"}',
                                    },
                                }],
                            },
                            "finish_reason": "tool_calls",
                        }],
                        "usage": {"prompt_tokens": 8, "completion_tokens": 7},
                    },
                )
            return httpx.Response(
                200,
                json={
                    "content": [{
                        "type": "tool_use",
                        "id": "call-1",
                        "name": "calculator",
                        "input": {"expression": "2+2"},
                    }],
                    "usage": {"input_tokens": 8, "output_tokens": 7},
                    "stop_reason": "tool_use",
                },
            )
        if provider == "openai":
            messages = payload["messages"]
            assert messages[2]["role"] == "assistant"
            call = messages[2]["tool_calls"][0]
            assert call["id"] == "call-1"
            assert json.loads(call["function"]["arguments"]) == {"expression": "2+2"}
            assert messages[3]["role"] == "tool"
            assert messages[3]["tool_call_id"] == "call-1"
            result_text = messages[3]["content"]
            response = {
                "choices": [{
                    "message": {"content": '{"answer":"4","citations":["call-1"]}'},
                    "finish_reason": "stop",
                }],
                "usage": {"prompt_tokens": 21, "completion_tokens": 8},
            }
        else:
            assert payload["system"] == "Use tools carefully."
            messages = payload["messages"]
            call = messages[1]["content"][0]
            assert call == {
                "type": "tool_use",
                "id": "call-1",
                "name": "calculator",
                "input": {"expression": "2+2"},
            }
            result = messages[2]["content"][0]
            assert messages[2]["role"] == "user"
            assert result["tool_use_id"] == "call-1"
            assert result["is_error"] is False
            result_text = result["content"]
            response = {
                "content": [{
                    "type": "text",
                    "text": '{"answer":"4","citations":["call-1"]}',
                }],
                "usage": {"input_tokens": 21, "output_tokens": 8},
                "stop_reason": "end_turn",
            }
        observation = json.loads(result_text.split("\n")[1])
        assert observation["trust"] == "untrusted_data"
        assert json.loads(observation["output"]) == {"value": "4"}
        return httpx.Response(200, json=response)

    async with httpx.AsyncClient(transport=httpx.MockTransport(handler)) as client:
        typ = OpenAICompatibleAdapter if provider == "openai" else AnthropicAdapter
        adapter = typ(client, endpoint="https://provider.invalid/messages", model="test")
        result = await AgentRunner(
            adapter, make_registry(tmp_path), allowed_tools={"calculator"}
        ).run("calculate 2+2", system="Use tools carefully.")
    assert result.outcome == "completed", result.error
    assert result.answer == "4"
    assert result.citations == ["call-1"]
    assert len(requests) == 2


def test_parallel_tool_results_grouped_for_anthropic() -> None:
    messages = [
        {"role": "system", "content": "Safety"},
        {"role": "user", "content": "Task"},
        {"role": "assistant", "content": "", "tool_calls": [
            {"id": "a", "name": "calculator", "arguments": {"expression": "1+1"}},
            {"id": "b", "name": "calculator", "arguments": {"expression": "2+2"}},
        ]},
        {"role": "tool", "tool_call_id": "a", "content": "2"},
        {"role": "tool", "tool_call_id": "b", "content": "denied", "is_error": True},
    ]
    system, output = anthropic_messages(messages)
    assert system == "Safety"
    assert len(output) == 3
    blocks = output[2]["content"]
    assert [block["tool_use_id"] for block in blocks] == ["a", "b"]
    assert blocks[1]["is_error"] is True


def test_unicode_arguments_round_trip() -> None:
    messages = [{"role": "assistant", "content": "", "tool_calls": [
        {"id": "unicode", "name": "search_files", "arguments": {"term": "مرحبا 🧪"}}
    ]}]
    encoded = openai_messages(messages)[0]["tool_calls"][0]["function"]["arguments"]
    assert json.loads(encoded) == {"term": "مرحبا 🧪"}


@pytest.mark.parametrize(
    "message",
    [
        {"role": "tool", "content": "missing ID"},
        {"role": "assistant", "content": "", "tool_calls": [
            {"id": "same", "name": "calculator", "arguments": {}},
            {"id": "same", "name": "calculator", "arguments": {}},
        ]},
        {"role": "assistant", "content": "", "tool_calls": [
            {"id": "a", "name": "calculator", "arguments": "not JSON object"}
        ]},
        {"role": "system", "content": ["not", "text"]},
        {"role": "fake_system", "content": "elevate permission"},
    ],
)
def test_malformed_transcripts_fail_closed(message: dict[str, Any]) -> None:
    with pytest.raises(TranscriptError):
        openai_messages([message])
    with pytest.raises(TranscriptError):
        anthropic_messages([message])


@pytest.mark.asyncio
async def test_invalid_transcript_does_not_send_http_request() -> None:
    calls = 0

    def handler(_request: httpx.Request) -> httpx.Response:
        nonlocal calls
        calls += 1
        return httpx.Response(200, json={})

    async with httpx.AsyncClient(transport=httpx.MockTransport(handler)) as client:
        for adapter_type in (OpenAICompatibleAdapter, AnthropicAdapter):
            adapter = adapter_type(client, endpoint="https://provider.invalid", model="test")
            with pytest.raises(ProviderProtocolError, match="invalid internal conversation"):
                await adapter.complete([{"role": "tool", "content": "no call ID"}], [])
    assert calls == 0
