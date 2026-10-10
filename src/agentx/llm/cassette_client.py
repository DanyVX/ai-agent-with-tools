"""LLMClient-compliant, offline-only adapter."""

from typing import Any

from agentx.llm.cassette import CassetteStore
from agentx.llm.contracts import LLMResponse, ToolSpec


class CassetteClient:
    def __init__(self, store: CassetteStore) -> None:
        self.store = store

    async def complete(
        self,
        messages: list[dict[str, Any]],
        tools: list[ToolSpec],
        *,
        max_tokens: int = 512,
        temperature: float = 0,
    ) -> LLMResponse:
        request = {
            "messages": messages,
            "tools": [t.model_dump(mode="json") for t in tools],
            "max_tokens": max_tokens,
            "temperature": temperature,
        }
        return LLMResponse.model_validate(self.store.replay(request))
