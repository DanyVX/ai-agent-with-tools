"""Strict arguments, structured errors, hard tool deadlines, output caps."""

import asyncio
import json
import sqlite3
from collections.abc import Awaitable, Callable
from dataclasses import dataclass
from typing import Any

from pydantic import BaseModel, ConfigDict, ValidationError

from agentx.llm.contracts import ToolSpec


class StrictArgs(BaseModel):
    model_config = ConfigDict(extra="forbid")


@dataclass(frozen=True)
class Tool:
    name: str
    description: str
    arguments: type[StrictArgs]
    handler: Callable[[StrictArgs], Awaitable[Any]]
    timeout_s: float = 5.0
    max_output_chars: int = 4096
    side_effect: bool = False


@dataclass(frozen=True)
class ToolResult:
    name: str
    call_id: str
    ok: bool
    output: str = ""
    error: str | None = None
    code: str | None = None

    def observation(self) -> dict[str, Any]:
        return {
            "tool": self.name,
            "call_id": self.call_id,
            "ok": self.ok,
            "output": self.output,
            "error": self.error,
            "code": self.code,
            "trust": "untrusted_data",
        }


class ToolRegistry:
    def __init__(self) -> None:
        self._tools: dict[str, Tool] = {}

    def register(self, tool: Tool) -> None:
        if tool.name in self._tools:
            raise ValueError(f"duplicate tool name: {tool.name}")
        if tool.timeout_s <= 0 or tool.max_output_chars < 64:
            raise ValueError("tool timeout and output cap must be positive")
        self._tools[tool.name] = tool

    def get(self, name: str) -> Tool | None:
        return self._tools.get(name)

    def specs(self, *, allowed: set[str] | None = None) -> list[ToolSpec]:
        return [
            ToolSpec(
                name=t.name,
                description=t.description,
                parameters=t.arguments.model_json_schema(),
            )
            for t in self._tools.values()
            if allowed is None or t.name in allowed
        ]

    async def execute(
        self,
        name: str,
        raw_arguments: dict[str, Any],
        *,
        call_id: str,
        approved: bool = False,
    ) -> ToolResult:
        tool = self.get(name)
        if tool is None:
            return ToolResult(name, call_id, False, error="unknown tool", code="unknown_tool")
        if tool.side_effect and not approved:
            return ToolResult(
                name, call_id, False, error="approval required", code="approval_required"
            )
        try:
            validated = tool.arguments.model_validate(raw_arguments)
        except ValidationError as exc:
            details = [
                {"field": ".".join(str(v) for v in e["loc"]), "type": e["type"]}
                for e in exc.errors(include_url=False)
            ]
            return ToolResult(
                name, call_id, False, error=json.dumps(details), code="invalid_arguments"
            )
        try:
            value = await asyncio.wait_for(tool.handler(validated), timeout=tool.timeout_s)
        except TimeoutError:
            return ToolResult(name, call_id, False, error="tool timed out", code="timeout")
        except (ValueError, OSError, sqlite3.Error) as exc:
            return ToolResult(name, call_id, False, error=type(exc).__name__, code="tool_error")
        except Exception:
            return ToolResult(name, call_id, False, error="tool raised an error", code="tool_error")
        try:
            text = json.dumps(value, ensure_ascii=False, allow_nan=False, sort_keys=True)
        except (TypeError, ValueError):
            return ToolResult(
                name, call_id, False, error="non-serializable output", code="serialization_error"
            )
        limit = tool.max_output_chars
        if len(text) > limit:
            lost = len(text) - limit
            text = f"{text[:limit]} [truncated {lost:,} chars]"
        return ToolResult(name, call_id, True, output=text)

    async def execute_many(
        self,
        calls: list[tuple[str, dict[str, Any], str]],
        *,
        allowed: set[str],
        max_concurrency: int = 3,
    ) -> list[ToolResult]:
        if max_concurrency < 1 or max_concurrency > 16:
            raise ValueError("invalid max_concurrency")
        effects = [name for name, _, _ in calls if (tool := self.get(name)) is not None and tool.side_effect]
        if len(effects) > 1:
            return [
                ToolResult(name, call_id, False, error="conflicting side effects", code="conflict")
                for name, _, call_id in calls
            ]
        semaphore = asyncio.Semaphore(max_concurrency)

        async def invoke(name: str, args: dict[str, Any], call_id: str) -> ToolResult:
            if name not in allowed:
                return ToolResult(
                    name, call_id, False, error="tool denied by policy", code="denied"
                )
            async with semaphore:
                return await self.execute(name, args, call_id=call_id)

        return await asyncio.gather(*(invoke(name, args, call_id) for name, args, call_id in calls))
