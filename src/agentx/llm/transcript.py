"""Translate internal tool-call conversations to provider-specific messages.

Tool observations remain untrusted data and cannot alter the system policy.
Malformed internal messages fail before any network request.
"""

import json
from typing import Any


class TranscriptError(ValueError):
    """A malformed conversation cannot be sent to a provider."""


def _content(message: dict[str, Any]) -> str:
    text = message.get("content", "")
    if not isinstance(text, str):
        raise TranscriptError("message content must be a string")
    return text


def _calls(message: dict[str, Any]) -> list[dict[str, Any]]:
    calls = message.get("tool_calls", [])
    if not isinstance(calls, list):
        raise TranscriptError("assistant tool_calls must be a list")
    result: list[dict[str, Any]] = []
    seen: set[str] = set()
    for call in calls:
        if not isinstance(call, dict):
            raise TranscriptError("tool call must be an object")
        call_id, name, arguments = call.get("id"), call.get("name"), call.get("arguments")
        if (
            not isinstance(call_id, str)
            or not call_id
            or call_id in seen
            or not isinstance(name, str)
            or not name
            or not isinstance(arguments, dict)
        ):
            raise TranscriptError("tool call requires distinct id, name and object arguments")
        seen.add(call_id)
        result.append({"id": call_id, "name": name, "arguments": arguments})
    return result


def _tool(message: dict[str, Any]) -> tuple[str, str, bool]:
    call_id = message.get("tool_call_id")
    if not isinstance(call_id, str) or not call_id:
        raise TranscriptError("tool result requires a nonempty tool_call_id")
    is_error = message.get("is_error", False)
    if not isinstance(is_error, bool):
        raise TranscriptError("is_error must be boolean")
    return call_id, _content(message), is_error


def openai_messages(messages: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """Produce Chat Completions assistant.tool_calls / tool response messages."""
    output: list[dict[str, Any]] = []
    for message in messages:
        role = message.get("role")
        if role in {"system", "developer", "user"}:
            output.append({"role": role, "content": _content(message)})
        elif role == "assistant":
            text = _content(message)
            calls = _calls(message)
            item: dict[str, Any] = {"role": "assistant", "content": text or None}
            if calls:
                item["tool_calls"] = [
                    {
                        "id": call["id"],
                        "type": "function",
                        "function": {
                            "name": call["name"],
                            "arguments": json.dumps(
                                call["arguments"], ensure_ascii=False, separators=(",", ":")
                            ),
                        },
                    }
                    for call in calls
                ]
            output.append(item)
        elif role == "tool":
            call_id, text, _ = _tool(message)
            output.append({"role": "tool", "tool_call_id": call_id, "content": text})
        else:
            raise TranscriptError("unsupported internal message role")
    return output


def anthropic_messages(
    messages: list[dict[str, Any]],
) -> tuple[str, list[dict[str, Any]]]:
    """Produce Messages API tool_use/tool_result blocks and top-level system text."""
    system: list[str] = []
    output: list[dict[str, Any]] = []
    for message in messages:
        role = message.get("role")
        if role in {"system", "developer"}:
            if output:
                raise TranscriptError("system/developer instructions must precede dialogue")
            system.append(_content(message))
        elif role == "user":
            output.append({"role": "user", "content": _content(message)})
        elif role == "assistant":
            blocks: list[dict[str, Any]] = []
            text = _content(message)
            if text:
                blocks.append({"type": "text", "text": text})
            for call in _calls(message):
                blocks.append(
                    {
                        "type": "tool_use",
                        "id": call["id"],
                        "name": call["name"],
                        "input": call["arguments"],
                    }
                )
            if not blocks:
                raise TranscriptError("empty assistant message")
            output.append({"role": "assistant", "content": blocks})
        elif role == "tool":
            call_id, content, is_error = _tool(message)
            block = {
                "type": "tool_result",
                "tool_use_id": call_id,
                "content": content,
                "is_error": is_error,
            }
            # Consecutive parallel results belong in the same user turn.
            if output and output[-1]["role"] == "user" and isinstance(
                output[-1]["content"], list
            ):
                output[-1]["content"].append(block)
            else:
                output.append({"role": "user", "content": [block]})
        else:
            raise TranscriptError("unsupported internal message role")
    return "\n".join(system), output
