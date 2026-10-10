"""Durable atomic USD reservation ledger for future provider requests.

Amounts are integer micro-USD; each reservation is transactional and idempotent.
Actual usage settles a reservation. This module never makes provider calls.
"""

import sqlite3
from datetime import datetime, timezone
from decimal import Decimal, ROUND_UP
from pathlib import Path

_MICRO = Decimal("1000000")


class BudgetExceeded(RuntimeError):
    """A request would exceed a configured cap or spend was under-reserved."""


class BudgetConflict(RuntimeError):
    """A request id was reused with different parameters or was already closed."""


def to_micros(amount: Decimal) -> int:
    if not amount.is_finite() or amount < 0:
        raise ValueError("USD amount must be finite and nonnegative")
    return int((amount * _MICRO).to_integral_value(rounding=ROUND_UP))


class SpendLedger:
    """Cross-process safe reservations using SQLite BEGIN IMMEDIATE.

    Call reserve *before* a live request and settle after receiving actual usage.
    Reserve a conservative maximum, not an expected cost. A crashed request
    stays reserved until manually investigated; it is never silently refunded.
    """

    def __init__(self, path: Path, *, per_run_usd: Decimal, per_day_usd: Decimal):
        self.path = path
        self.run_limit = to_micros(per_run_usd)
        self.day_limit = to_micros(per_day_usd)
        path.parent.mkdir(parents=True, exist_ok=True)
        with self._connect() as conn:
            conn.execute(
                """CREATE TABLE IF NOT EXISTS spending (
                    request_id TEXT PRIMARY KEY,
                    run_id TEXT NOT NULL,
                    day_utc TEXT NOT NULL,
                    reserved_micros INTEGER NOT NULL,
                    actual_micros INTEGER,
                    state TEXT NOT NULL CHECK (state IN ('reserved','settled'))
                )"""
            )

    def _connect(self) -> sqlite3.Connection:
        conn = sqlite3.connect(self.path, timeout=10)
        conn.execute("PRAGMA busy_timeout=10000")
        return conn

    @staticmethod
    def _day(at: datetime | None) -> str:
        date = at or datetime.now(timezone.utc)
        if date.tzinfo is None or date.utcoffset() is None:
            raise ValueError("Time must be timezone aware")
        return date.astimezone(timezone.utc).date().isoformat()

    def reserve(
        self, *, request_id: str, run_id: str, maximum_usd: Decimal, at: datetime | None = None
    ) -> None:
        cost = to_micros(maximum_usd)
        if not request_id or not run_id or cost <= 0:
            raise ValueError("request_id, run_id and positive maximum_usd are required")
        day = self._day(at)
        with self._connect() as conn:
            conn.execute("BEGIN IMMEDIATE")
            prior = conn.execute(
                "SELECT run_id, day_utc, reserved_micros, state FROM spending WHERE request_id=?",
                (request_id,),
            ).fetchone()
            if prior is not None:
                if prior == (run_id, day, cost, "reserved"):
                    return
                raise BudgetConflict("Request ID already exists with other values or state")
            run_spend = conn.execute(
                """SELECT COALESCE(SUM(COALESCE(actual_micros,reserved_micros)),0)
                   FROM spending WHERE run_id=?""",
                (run_id,),
            ).fetchone()[0]
            day_spend = conn.execute(
                """SELECT COALESCE(SUM(COALESCE(actual_micros,reserved_micros)),0)
                   FROM spending WHERE day_utc=?""",
                (day,),
            ).fetchone()[0]
            if run_spend + cost > self.run_limit or day_spend + cost > self.day_limit:
                raise BudgetExceeded("Run or UTC-day USD limit exceeded; request was not sent")
            conn.execute(
                """INSERT INTO spending
                   (request_id,run_id,day_utc,reserved_micros,actual_micros,state)
                   VALUES (?,?,?,?,NULL,'reserved')""",
                (request_id, run_id, day, cost),
            )

    def settle(self, *, request_id: str, actual_usd: Decimal) -> None:
        actual = to_micros(actual_usd)
        with self._connect() as conn:
            conn.execute("BEGIN IMMEDIATE")
            prior = conn.execute(
                "SELECT reserved_micros, actual_micros, state FROM spending WHERE request_id=?",
                (request_id,),
            ).fetchone()
            if prior is None:
                raise BudgetConflict("Cannot settle an unknown request")
            maximum, previous, state = prior
            if state == "settled":
                if previous == actual:
                    return
                raise BudgetConflict("Cannot change already-settled usage")
            conn.execute(
                "UPDATE spending SET actual_micros=?,state='settled' WHERE request_id=?",
                (actual, request_id),
            )
        if actual > maximum:
            raise BudgetExceeded(
                "Actual spend exceeded reservation; true usage was recorded, "
                "and later requests must be re-evaluated"
            )

    def totals(self, *, run_id: str, at: datetime | None = None) -> tuple[int, int]:
        """Return current run/day charges in integer micro-USD."""
        day = self._day(at)
        with self._connect() as conn:
            run_total = conn.execute(
                "SELECT COALESCE(SUM(COALESCE(actual_micros,reserved_micros)),0) "
                "FROM spending WHERE run_id=?",
                (run_id,),
            ).fetchone()[0]
            day_total = conn.execute(
                "SELECT COALESCE(SUM(COALESCE(actual_micros,reserved_micros)),0) "
                "FROM spending WHERE day_utc=?",
                (day,),
            ).fetchone()[0]
        return int(run_total), int(day_total)
