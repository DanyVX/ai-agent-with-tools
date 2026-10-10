"""Policy is a code-owned capability set, not a model-generated instruction."""

import json
import re
from dataclasses import dataclass, field
from typing import Any

from agentx.approval.gate import ApprovalGate, ApprovalRequest
from agentx.tools.core import ToolRegistry, ToolResult

_EMAIL = re.compile(r"(?i)\b[\w.+'-]+@[\w.-]+\.[a-z]{2,}\b")
_PHONE = re.compile(r"(?<!\w)(?:\+?\d[ -]?){9,15}(?!\w)")
_SECRET = re.compile(r"(?i)\b(?:sk-[a-zA-Z0-9_-]{12,}|(?:api[_-]?key|token)\s*[:=]\s*[^\s,}]+)")


def redact(value: str) -> str:
    """Best-effort PII/secret redaction, not a substitute for data minimization."""
    return _SECRET.sub(
        "[REDACTED_SECRET]", _PHONE.sub("[REDACTED_PHONE]", _EMAIL.sub("[REDACTED_EMAIL]", value))
    )


@dataclass
class ToolPolicy:
    permitted: set[str]
    canaries: set[str] = field(default_factory=set)
    # Actual external HTTP is deliberately absent; only reviewed fixtures are allowed.
    outward: set[str] = field(default_factory=lambda: {"send_email_mock", "http_get"})


class GuardedExecutor:
    """Approval gate and canary checks before any tool handler executes."""

    def __init__(self, registry: ToolRegistry, policy: ToolPolicy, gate: ApprovalGate) -> None:
        self.registry = registry
        self.policy = policy
        self.gate = gate

    async def execute_many(
        self,
        calls: list[tuple[str, dict[str, Any], str]],
        *,
        allowed: set[str],
        max_concurrency: int = 3,
        provenance: list[str] | None = None,
    ) -> list[ToolResult]:
        permitted = allowed & self.policy.permitted
        effects = [
            name
            for name, _, _ in calls
            if (tool := self.registry.get(name)) is not None and tool.side_effect
        ]
        if len(effects) > 1:
            return [
                ToolResult(name, call_id, False, error="conflicting effects", code="conflict")
                for name, _, call_id in calls
            ]
        results: list[ToolResult | None] = [None] * len(calls)
        safe: list[tuple[str, dict[str, Any], str, int]] = []
        for idx, (name, args, call_id) in enumerate(calls):
            if name not in permitted:
                results[idx] = ToolResult(
                    name, call_id, False, error="not permitted by code policy", code="denied"
                )
                continue
            if name in self.policy.outward:
                serialized = json.dumps(args, ensure_ascii=False, sort_keys=True)
                if any(token and token in serialized for token in self.policy.canaries):
                    results[idx] = ToolResult(
                        name, call_id, False, error="outbound canary detected", code="data_leak"
                    )
                    continue
            tool = self.registry.get(name)
            if tool is not None and tool.side_effect:
                request = ApprovalRequest(
                    tool=name,
                    arguments=args.copy(),
                    call_id=call_id,
                    provenance=provenance or [],
                )
                decision = await self.gate.decide(request)
                if not decision.approved:
                    results[idx] = ToolResult(
                        name,
                        call_id,
                        False,
                        error="approval denied/expired",
                        code="approval_denied",
                    )
                    continue
                arguments = (
                    decision.edited_arguments if decision.edited_arguments is not None else args
                )
                if not isinstance(arguments, dict):
                    results[idx] = ToolResult(
                        name,
                        call_id,
                        False,
                        error="invalid edited arguments",
                        code="invalid_arguments",
                    )
                    continue
                if name in self.policy.outward:
                    edited = json.dumps(arguments, ensure_ascii=False, sort_keys=True)
                    if any(token and token in edited for token in self.policy.canaries):
                        results[idx] = ToolResult(
                            name,
                            call_id,
                            False,
                            error="outbound canary detected after approval edits",
                            code="data_leak",
                        )
                        continue
                # Re-validate edits in ToolRegistry.execute; never use pre-approved raw data.
                results[idx] = await self.registry.execute(
                    name, arguments, call_id=call_id, approved=True
                )
            else:
                safe.append((name, args, call_id, idx))
        if safe:
            reads = await self.registry.execute_many(
                [(name, args, call_id) for name, args, call_id, _ in safe],
                allowed=permitted,
                max_concurrency=max_concurrency,
            )
            for (_name, _args, _call_id, idx), output in zip(safe, reads, strict=True):
                results[idx] = output
        return [r for r in results if r is not None]
