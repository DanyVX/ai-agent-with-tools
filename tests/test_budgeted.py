"""Provider accounting must reserve before any request."""

from decimal import Decimal
from pathlib import Path
from typing import Any

import pytest

from agentx.budget import BudgetExceeded, SpendLedger
from agentx.llm.budgeted import BudgetedClient
from agentx.llm.contracts import LLMResponse, ToolSpec, Usage


class FakeLive:
    def __init__(self) -> None:
        self.calls = 0

    async def complete(
        self, messages: list[dict[str, Any]], tools: list[ToolSpec],
        *, max_tokens: int = 512, temperature: float = 0,
    ) -> LLMResponse:
        self.calls += 1
        return LLMResponse(
            text="synthetic", usage=Usage(input_tokens=10, output_tokens=10)
        )


@pytest.mark.asyncio
async def test_zero_budget_prevents_provider_request(tmp_path: Path) -> None:
    fake = FakeLive()
    ledger = SpendLedger(
        tmp_path / "budget.sqlite", per_run_usd=Decimal("0"),
        per_day_usd=Decimal("0"),
    )
    wrapped = BudgetedClient(
        fake, ledger, run_id="r", max_input_tokens=100,
        input_per_million_usd=Decimal("1"),
        output_per_million_usd=Decimal("1"),
    )
    with pytest.raises(BudgetExceeded):
        await wrapped.complete([], [], max_tokens=100)
    assert fake.calls == 0


@pytest.mark.asyncio
async def test_provider_spend_settled(tmp_path: Path) -> None:
    fake = FakeLive()
    ledger = SpendLedger(
        tmp_path / "budget.sqlite", per_run_usd=Decimal("1"),
        per_day_usd=Decimal("1"),
    )
    wrapped = BudgetedClient(
        fake, ledger, run_id="r", max_input_tokens=100,
        input_per_million_usd=Decimal("1"),
        output_per_million_usd=Decimal("1"),
    )
    await wrapped.complete([], [], max_tokens=100)
    assert fake.calls == 1
    assert ledger.totals(run_id="r")[0] == 20
