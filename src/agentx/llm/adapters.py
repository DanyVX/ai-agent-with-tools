"""Small async Anthropic and OpenAI-compatible JSON adapters.

Transport only. Network execution must be called through the budgeted
runtime, not directly from untrusted model/tool content.
"""

import asyncio
import email.utils
import secrets
from datetime import UTC, datetime
from typing import Any

import httpx
from pydantic import ValidationError

from agentx.llm.transcript import TranscriptError, anthropic_messages, openai_messages

from agentx.llm.contracts import (
    LLMResponse,
    ToolCall,
    ToolSpec,
    Usage,
    estimated_usage,
)


class ProviderError(RuntimeError):
    """Typed failure that contains no API key or raw response body."""


class ProviderProtocolError(ProviderError):
    """A provider returned an unusable result."""


class ProviderUnavailable(ProviderError):
    """An API rejected or failed a request."""


def _retry_after(value: str | None) -> float | None:
    if not value:
        return None
    try:
        return max(0.0, float(value))
    except ValueError:
        try:
            date = email.utils.parsedate_to_datetime(value)
            return max(0.0, (date.astimezone(UTC) - datetime.now(UTC)).total_seconds())
        except (TypeError, ValueError, OverflowError):
            return None


class JSONAdapter:
    def __init__(
        self,
        client: httpx.AsyncClient,
        *,
        endpoint: str,
        model: str,
        headers: dict[str, str] | None = None,
        max_attempts: int = 3,
    ) -> None:
        if not (1 <= max_attempts <= 5):
            raise ValueError("max_attempts must be between 1 and 5")
        if not model:
            raise ValueError("explicit model ID required")
        self.client = client
        self.endpoint = endpoint
        self.model = model
        self.headers = headers or {}
        self.max_attempts = max_attempts

    async def _post(self, payload: dict[str, Any]) -> dict[str, Any]:
        for attempt in range(self.max_attempts):
            try:
                response = await self.client.post(self.endpoint, headers=self.headers, json=payload)
            except (httpx.TimeoutException, httpx.TransportError) as exc:
                if attempt + 1 == self.max_attempts:
                    raise ProviderUnavailable("provider network timeout/transport failure") from exc
                await asyncio.sleep(min(4.0, 0.2 * (2**attempt) + secrets.randbelow(100) / 1000))
                continue
            if response.status_code == 429 or response.status_code >= 500:
                if attempt + 1 == self.max_attempts:
                    raise ProviderUnavailable(
                        f"retry budget exhausted: HTTP {response.status_code}"
                    )
                delay = _retry_after(response.headers.get("retry-after"))
                await asyncio.sleep(min(5.0, delay if delay is not None else 0.2 * (2**attempt)))
                continue
            if response.status_code >= 400:
                if response.status_code in (400, 404, 410, 422):
                    raise ProviderUnavailable(
                        f"HTTP {response.status_code}: verify model ID and availability"
                    )
                raise ProviderUnavailable(f"non-retryable provider HTTP {response.status_code}")
            try:
                data = response.json()
            except ValueError as exc:
                raise ProviderProtocolError("provider returned non-JSON body") from exc
            if not isinstance(data, dict):
                raise ProviderProtocolError("provider response must be an object")
            return data
        raise ProviderUnavailable("retry budget exhausted")


class OpenAICompatibleAdapter(JSONAdapter):
    async def complete(
        self,
        messages: list[dict[str, Any]],
        tools: list[ToolSpec],
        *,
        max_tokens: int = 512,
        temperature: float = 0,
    ) -> LLMResponse:
        try:
            normalized_messages = openai_messages(messages)
        except TranscriptError as exc:
            raise ProviderProtocolError("invalid internal conversation") from exc
        payload: dict[str, Any] = {
            "model": self.model,
            "messages": normalized_messages,
            "temperature": temperature,
            "max_tokens": max_tokens,
            "stream": False,
        }
        if tools:
            payload["tools"] = [
                {
                    "type": "function",
                    "function": {
                        "name": t.name,
                        "description": t.description,
                        "parameters": t.parameters,
                    },
                }
                for t in tools
            ]
        data = await self._post(payload)
        try:
            choice = data["choices"][0]
            message = choice["message"]
            text = message.get("content") or ""
            if not isinstance(text, str):
                raise ValueError("assistant content is not text")
            calls = [
                ToolCall(
                    id=t.get("id") or f"missing-{i}",
                    name=t["function"]["name"],
                    arguments=t["function"]["arguments"],
                )
                for i, t in enumerate(message.get("tool_calls") or [])
            ]
            tokens = data.get("usage") or {}
            usage = (
                Usage(
                    input_tokens=tokens["prompt_tokens"],
                    output_tokens=tokens["completion_tokens"],
                )
                if "prompt_tokens" in tokens and "completion_tokens" in tokens
                else estimated_usage(messages, text)
            )
            return LLMResponse(
                text=text,
                tool_calls=calls,
                usage=usage,
                stop_reason=choice.get("finish_reason") or "unknown",
            )
        except (KeyError, IndexError, TypeError, ValueError, ValidationError) as exc:
            raise ProviderProtocolError(
                "invalid OpenAI-compatible response/tool arguments"
            ) from exc


class AnthropicAdapter(JSONAdapter):
    async def complete(
        self,
        messages: list[dict[str, Any]],
        tools: list[ToolSpec],
        *,
        max_tokens: int = 512,
        temperature: float = 0,
    ) -> LLMResponse:
        try:
            system_text, non_system = anthropic_messages(messages)
        except TranscriptError as exc:
            raise ProviderProtocolError("invalid internal conversation") from exc
        payload: dict[str, Any] = {
            "model": self.model,
            "messages": non_system,
            "max_tokens": max_tokens,
            "temperature": temperature,
        }
        if system_text:
            payload["system"] = system_text
        if tools:
            payload["tools"] = [
                {"name": t.name, "description": t.description, "input_schema": t.parameters}
                for t in tools
            ]
        data = await self._post(payload)
        try:
            blocks = data["content"]
            text = "\n".join(block["text"] for block in blocks if block.get("type") == "text")
            calls = [
                ToolCall(
                    id=block.get("id") or f"missing-{i}",
                    name=block["name"],
                    arguments=block["input"],
                )
                for i, block in enumerate(blocks)
                if block.get("type") == "tool_use"
            ]
            tokens = data.get("usage") or {}
            usage = (
                Usage(input_tokens=tokens["input_tokens"], output_tokens=tokens["output_tokens"])
                if "input_tokens" in tokens and "output_tokens" in tokens
                else estimated_usage(messages, text)
            )
            return LLMResponse(
                text=text,
                tool_calls=calls,
                usage=usage,
                stop_reason=data.get("stop_reason") or "unknown",
            )
        except (KeyError, IndexError, TypeError, ValueError, ValidationError) as exc:
            raise ProviderProtocolError("invalid Anthropic response/tool arguments") from exc
