"""Stable provider-independent LLM contract."""

import json
from typing import Any, Protocol

from pydantic import BaseModel, ConfigDict, Field, field_validator


class ToolSpec(BaseModel):
    name: str
    description: str
    parameters: dict[str, Any]


class ToolCall(BaseModel):
    id: str
    name: str
    arguments: dict[str, Any]

    @field_validator("arguments", mode="before")
    @classmethod
    def validate_arguments(cls, value: Any) -> dict[str, Any]:
        if isinstance(value, str):
            try:
                value = json.loads(value)
            except json.JSONDecodeError as exc:
                raise ValueError("malformed tool argument JSON") from exc
        if not isinstance(value, dict):
            raise ValueError("tool arguments must be a JSON object")
        return value


class Usage(BaseModel):
    input_tokens: int = Field(ge=0)
    output_tokens: int = Field(ge=0)
    estimated: bool = False


class LLMResponse(BaseModel):
    model_config = ConfigDict(extra="forbid")

    text: str = ""
    tool_calls: list[ToolCall] = Field(default_factory=list)
    usage: Usage
    stop_reason: str = "unknown"


class LLMClient(Protocol):
    async def complete(
        self,
        messages: list[dict[str, Any]],
        tools: list[ToolSpec],
        *,
        max_tokens: int = 512,
        temperature: float = 0,
    ) -> LLMResponse: ...


def estimated_usage(messages: list[dict[str, Any]], text: str) -> Usage:
    """Transparent fallback; NOT provider-billed tokens or a benchmark."""
    raw = json.dumps(messages, ensure_ascii=False, default=str)
    return Usage(
        input_tokens=max(1, (len(raw) + 3) // 4),
        output_tokens=max(1, (len(text) + 3) // 4),
        estimated=True,
    )
