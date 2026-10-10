"""Deterministic scripted demo. Not an LLM or model benchmark."""

import json
import re
from typing import Any

from agentx.llm.contracts import LLMResponse, ToolCall, ToolSpec, Usage


class DemoClient:
    async def complete(
        self,
        messages: list[dict[str, Any]],
        tools: list[ToolSpec],
        *,
        max_tokens: int = 512,
        temperature: float = 0,
    ) -> LLMResponse:
        observations = [
            m["content"]
            for m in messages
            if m["role"] == "tool" and "<untrusted_tool_result>" in str(m["content"])
        ]
        usage = Usage(input_tokens=10, output_tokens=10, estimated=True)
        if observations:
            raw = observations[-1].split("<untrusted_tool_result>\n", 1)[1]
            data = json.loads(raw.split("\n</untrusted_tool_result>", 1)[0])
            if not data["ok"]:
                return LLMResponse(
                    text="The calculator tool failed; I cannot verify the answer.",
                    usage=usage,
                    stop_reason="stop",
                )
            output = json.loads(data["output"])
            answer = json.dumps(
                {"answer": str(output["value"]), "citations": [data["call_id"]]},
                ensure_ascii=False,
            )
            return LLMResponse(text=answer, usage=usage, stop_reason="stop")
        original = str(messages[1]["content"])
        found = re.search(r"(-?\d+(?:\.\d+)?\s*[+*/-]\s*-?\d+(?:\.\d+)?)", original)
        if not found:
            return LLMResponse(
                text="Demo supports a simple arithmetic expression, e.g. calculate 2 + 2.",
                usage=usage,
                stop_reason="stop",
            )
        return LLMResponse(
            tool_calls=[
                ToolCall(id="demo-call-1", name="calculator", arguments={"expression": found[1]})
            ],
            usage=usage,
            stop_reason="tool_calls",
        )
