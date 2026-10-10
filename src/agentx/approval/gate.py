"""Default-deny approvals with exact arguments and optional edits."""

import asyncio
from collections.abc import Awaitable, Callable
from typing import Any

from pydantic import BaseModel, ConfigDict, Field


class ApprovalRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    tool: str
    arguments: dict[str, Any]
    call_id: str
    provenance: list[str] = Field(default_factory=list)


class ApprovalDecision(BaseModel):
    approved: bool = False
    edited_arguments: dict[str, Any] | None = None


Approver = Callable[[ApprovalRequest], Awaitable[ApprovalDecision]]


class ApprovalGate:
    """No callback means deny. Timeout, exceptions or fatigue mean deny."""

    def __init__(
        self, approver: Approver | None = None, *, timeout_s: float = 30, max_requests: int = 3
    ) -> None:
        if timeout_s <= 0 or max_requests < 1:
            raise ValueError("invalid approval timeout or request cap")
        self.approver = approver
        self.timeout_s = timeout_s
        self.max_requests = max_requests
        self._requests = 0

    async def decide(self, request: ApprovalRequest) -> ApprovalDecision:
        self._requests += 1
        if self.approver is None or self._requests > self.max_requests:
            return ApprovalDecision()
        try:
            return await asyncio.wait_for(self.approver(request), timeout=self.timeout_s)
        except (TimeoutError, Exception):
            return ApprovalDecision()
