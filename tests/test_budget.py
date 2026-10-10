"""Durable, atomic and conservative spend reservations."""

from concurrent.futures import ThreadPoolExecutor
from datetime import datetime, timedelta, timezone
from decimal import Decimal
from pathlib import Path

import pytest

from agentx.budget import BudgetConflict, BudgetExceeded, SpendLedger, to_micros


def ledger(path: Path, cap: str = "1") -> SpendLedger:
    return SpendLedger(path, per_run_usd=Decimal(cap), per_day_usd=Decimal(cap))


def test_no_spend_by_default(tmp_path: Path) -> None:
    store = ledger(tmp_path / "budget.sqlite", "0")
    with pytest.raises(BudgetExceeded):
        store.reserve(request_id="r1", run_id="run1", maximum_usd=Decimal("0.000001"))


def test_reserve_settle_and_idempotency(tmp_path: Path) -> None:
    store = ledger(tmp_path / "budget.sqlite")
    store.reserve(request_id="a", run_id="run1", maximum_usd=Decimal("0.25"))
    store.reserve(request_id="a", run_id="run1", maximum_usd=Decimal("0.25"))
    assert store.totals(run_id="run1") == (250000, 250000)
    store.settle(request_id="a", actual_usd=Decimal("0.10"))
    store.settle(request_id="a", actual_usd=Decimal("0.10"))
    assert store.totals(run_id="run1") == (100000, 100000)
    with pytest.raises(BudgetConflict):
        store.settle(request_id="a", actual_usd=Decimal("0.20"))


def test_conflicting_request_id_rejected(tmp_path: Path) -> None:
    store = ledger(tmp_path / "budget.sqlite")
    store.reserve(request_id="a", run_id="run1", maximum_usd=Decimal("0.1"))
    with pytest.raises(BudgetConflict):
        store.reserve(request_id="a", run_id="run2", maximum_usd=Decimal("0.1"))


def test_run_and_day_limits(tmp_path: Path) -> None:
    store = ledger(tmp_path / "budget.sqlite", "0.40")
    store.reserve(request_id="a", run_id="run1", maximum_usd=Decimal("0.30"))
    with pytest.raises(BudgetExceeded):
        store.reserve(request_id="b", run_id="run1", maximum_usd=Decimal("0.20"))
    with pytest.raises(BudgetExceeded):
        store.reserve(request_id="b", run_id="run2", maximum_usd=Decimal("0.20"))
    assert store.totals(run_id="run2") == (0, 300000)


def test_overrun_recorded_not_hidden(tmp_path: Path) -> None:
    store = ledger(tmp_path / "budget.sqlite")
    store.reserve(request_id="a", run_id="r1", maximum_usd=Decimal("0.5"))
    with pytest.raises(BudgetExceeded, match="exceeded reservation"):
        store.settle(request_id="a", actual_usd=Decimal("1.1"))
    assert store.totals(run_id="r1") == (1100000, 1100000)
    with pytest.raises(BudgetExceeded):
        store.reserve(request_id="b", run_id="r2", maximum_usd=Decimal("0.01"))


def test_utc_day_partition(tmp_path: Path) -> None:
    store = ledger(tmp_path / "budget.sqlite")
    d1 = datetime(2026, 10, 10, 23, 59, tzinfo=timezone.utc)
    d2 = d1 + timedelta(minutes=2)
    store.reserve(request_id="a", run_id="r1", maximum_usd=Decimal("0.9"), at=d1)
    store.reserve(request_id="b", run_id="r2", maximum_usd=Decimal("0.9"), at=d2)
    assert store.totals(run_id="r2", at=d2) == (900000, 900000)


@pytest.mark.parametrize("bad", ["-1", "NaN", "Infinity"])
def test_bad_decimal(bad: str) -> None:
    with pytest.raises(ValueError):
        to_micros(Decimal(bad))


def test_rounds_up_micro_dollars() -> None:
    assert to_micros(Decimal("0.0000001")) == 1


def test_atomic_reservations_in_threads(tmp_path: Path) -> None:
    path = tmp_path / "budget.sqlite"
    store = ledger(path, "0.000001")

    def attempt(i: int) -> bool:
        try:
            store.reserve(
                request_id=f"request-{i}", run_id=f"run-{i}", maximum_usd=Decimal("0.000001")
            )
            return True
        except BudgetExceeded:
            return False

    with ThreadPoolExecutor(max_workers=5) as executor:
        outcomes = list(executor.map(attempt, range(10)))
    assert sum(outcomes) == 1
    assert store.totals(run_id="run-0")[1] == 1
