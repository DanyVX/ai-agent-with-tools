"""Contract tests run through an offline injected HTTP transport."""

import json
from pathlib import Path
from typing import Any

import httpx
import pytest

from agentx.llm.adapters import (
    AnthropicAdapter,
    OpenAICompatibleAdapter,
    ProviderProtocolError,
    ProviderUnavailable,
)
from agentx.llm.cassette import CassetteStore, request_fingerprint
from agentx.llm.cassette_client import CassetteClient
from agentx.llm.contracts import ToolSpec


@pytest.mark.asyncio
@pytest.mark.parametrize("adapter_name", ["openai", "anthropic"])
async def test_provider_contract(adapter_name: str) -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        assert json.loads(request.content)["model"] == "test"
        if adapter_name == "openai":
            return httpx.Response(
                200,
                json={
                    "choices": [
                        {
                            "message": {
                                "content": "done",
                                "tool_calls": [
                                    {
                                        "id": "call-1",
                                        "function": {"name": "calculator", "arguments": '{"x":2}'},
                                    }
                                ],
                            },
                            "finish_reason": "tool_calls",
                        }
                    ],
                    "usage": {"prompt_tokens": 3, "completion_tokens": 5},
                },
            )
        return httpx.Response(
            200,
            json={
                "content": [
                    {"type": "text", "text": "done"},
                    {"type": "tool_use", "id": "call-1", "name": "calculator", "input": {"x": 2}},
                ],
                "usage": {"input_tokens": 3, "output_tokens": 5},
                "stop_reason": "tool_use",
            },
        )

    async with httpx.AsyncClient(transport=httpx.MockTransport(handler)) as client:
        typ = OpenAICompatibleAdapter if adapter_name == "openai" else AnthropicAdapter
        adapter = typ(client, endpoint="https://provider.invalid/test", model="test")
        tool = ToolSpec(name="calculator", description="compute", parameters={"type": "object"})
        result = await adapter.complete([{"role": "user", "content": "2"}], [tool])
    assert result.text == "done"
    assert result.tool_calls[0].arguments == {"x": 2}
    assert result.usage.input_tokens == 3
    assert not result.usage.estimated


@pytest.mark.asyncio
async def test_malformed_args_are_typed_error() -> None:
    response = {
        "choices": [
            {
                "message": {
                    "tool_calls": [
                        {"id": "c", "function": {"name": "calculator", "arguments": "{bad"}}
                    ]
                },
                "finish_reason": "tool_calls",
            }
        ]
    }

    def handler(_request: httpx.Request) -> httpx.Response:
        return httpx.Response(200, json=response)

    async with httpx.AsyncClient(transport=httpx.MockTransport(handler)) as client:
        adapter = OpenAICompatibleAdapter(client, endpoint="https://provider.invalid", model="test")
        with pytest.raises(ProviderProtocolError, match="invalid"):
            await adapter.complete([], [])


@pytest.mark.asyncio
async def test_no_retries_on_400() -> None:
    calls = 0

    def handler(_request: httpx.Request) -> httpx.Response:
        nonlocal calls
        calls += 1
        return httpx.Response(400, json={})

    async with httpx.AsyncClient(transport=httpx.MockTransport(handler)) as client:
        adapter = OpenAICompatibleAdapter(client, endpoint="https://provider.invalid", model="test")
        with pytest.raises(ProviderUnavailable, match="model ID"):
            await adapter.complete([], [])
    assert calls == 1


@pytest.mark.asyncio
async def test_retry_429_and_missing_usage(monkeypatch: pytest.MonkeyPatch) -> None:
    calls = 0

    async def no_delay(_seconds: float) -> None:
        return None

    monkeypatch.setattr("agentx.llm.adapters.asyncio.sleep", no_delay)

    def handler(_request: httpx.Request) -> httpx.Response:
        nonlocal calls
        calls += 1
        if calls == 1:
            return httpx.Response(429, headers={"retry-after": "0"})
        return httpx.Response(
            200, json={"choices": [{"message": {"content": "✅"}, "finish_reason": "stop"}]}
        )

    async with httpx.AsyncClient(transport=httpx.MockTransport(handler)) as client:
        adapter = OpenAICompatibleAdapter(client, endpoint="https://provider.invalid", model="test")
        response = await adapter.complete([{"role": "user", "content": "hello"}], [])
    assert calls == 2
    assert response.usage.estimated


@pytest.mark.asyncio
async def test_cassette_contract_without_network(tmp_path: Path) -> None:
    messages: list[dict[str, Any]] = [{"role": "user", "content": "hello"}]
    request = {"messages": messages, "tools": [], "max_tokens": 512, "temperature": 0}
    digest = request_fingerprint(request)
    fixture = {
        "request_hash": digest,
        "response": {
            "text": "world",
            "usage": {"input_tokens": 1, "output_tokens": 1},
            "tool_calls": [],
            "stop_reason": "stop",
        },
    }
    (tmp_path / f"{digest}.json").write_text(json.dumps(fixture), encoding="utf-8")
    response = await CassetteClient(CassetteStore(tmp_path)).complete(messages, [])
    assert response.text == "world"
