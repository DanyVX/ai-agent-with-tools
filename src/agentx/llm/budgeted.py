"""Strict reserve-before-send wrapper for explicitly configured live providers."""

import uuid
from decimal import Decimal
from typing import Any

from agentx.budget import SpendLedger
from agentx.llm.contracts import LLMClient, LLMResponse, ToolSpec


class BudgetedClient:
    """Require configured prices and a maximum input size before paid execution.

    This cannot guarantee an external provider's final bill; overages are
    recorded and signalled, never silently forgiven.
    """

    def __init__(
        self,
        client: LLMClient,
        ledger: SpendLedger,
        *,
        run_id: str,
        max_input_tokens: int,
        input_per_million_usd: Decimal,
        output_per_million_usd: Decimal,
    ) -> None:
        if max_input_tokens <= 0 or min(input_per_million_usd, output_per_million_usd) <= 0:
            raise ValueError("positive input ceiling and audited price rates required")
        self.client = client
        self.ledger = ledger
        self.run_id = run_id
        self.max_input_tokens = max_input_tokens
        self.input_rate = input_per_million_usd
        self.output_rate = output_per_million_usd

    async def complete(
        self,
        messages: list[dict[str, Any]],
        tools: list[ToolSpec],
        *,
        max_tokens: int = 512,
        temperature: float = 0,
    ) -> LLMResponse:
        if not (1 <= max_tokens <= 100_000):
            raise ValueError("invalid output token ceiling")
        ceiling = (
            Decimal(self.max_input_tokens) * self.input_rate
            + Decimal(max_tokens) * self.output_rate
        ) / Decimal("1000000")
        request_id = uuid.uuid4().hex
        self.ledger.reserve(request_id=request_id, run_id=self.run_id, maximum_usd=ceiling)
        # On error, reservation remains held as an ambiguous provider spend.
        result = await self.client.complete(
            messages, tools, max_tokens=max_tokens, temperature=temperature
        )
        actual = (
            Decimal(result.usage.input_tokens) * self.input_rate
            + Decimal(result.usage.output_tokens) * self.output_rate
        ) / Decimal("1000000")
        self.ledger.settle(request_id=request_id, actual_usd=actual)
        return result
