"""Opt-in synthetic-only record and replay at exact LLM request boundaries."""

from typing import Any

from agentx.llm.contracts import LLMClient, LLMResponse, ToolSpec
from agentx.runs.store import RunStore


def _request(
    messages: list[dict[str, Any]],
    tools: list[ToolSpec],
    max_tokens: int,
    temperature: float,
) -> dict[str, Any]:
    return {
        "messages": messages,
        "tools": [tool.model_dump(mode="json") for tool in tools],
        "max_tokens": max_tokens,
        "temperature": temperature,
    }


class RecordingClient:
    def __init__(self, client: LLMClient, store: RunStore, run_id: str) -> None:
        if not store.allow_synthetic_replay:
            raise PermissionError("recording must be explicitly opted in for synthetic data")
        self.client = client
        self.store = store
        self.run_id = run_id
        self.index = 0

    async def complete(
        self,
        messages: list[dict[str, Any]],
        tools: list[ToolSpec],
        *,
        max_tokens: int = 512,
        temperature: float = 0,
    ) -> LLMResponse:
        result = await self.client.complete(
            messages, tools, max_tokens=max_tokens, temperature=temperature
        )
        self.store.record_synthetic(
            self.run_id, self.index,
            _request(messages, tools, max_tokens, temperature),
            result.model_dump(mode="json"),
        )
        self.index += 1
        return result


class ReplayClient:
    def __init__(self, store: RunStore, run_id: str) -> None:
        if not store.allow_synthetic_replay:
            raise PermissionError("replay must be explicitly opted in for synthetic data")
        self.store = store
        self.run_id = run_id
        self.index = 0

    async def complete(
        self,
        messages: list[dict[str, Any]],
        tools: list[ToolSpec],
        *,
        max_tokens: int = 512,
        temperature: float = 0,
    ) -> LLMResponse:
        data = self.store.replay_synthetic(
            self.run_id, self.index,
            _request(messages, tools, max_tokens, temperature),
        )
        self.index += 1
        return LLMResponse.model_validate(data)
