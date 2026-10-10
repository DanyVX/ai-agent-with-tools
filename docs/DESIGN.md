# Design and engineering decisions

## Scope
Build a small, inspectable, fail-safe tool-using runtime, not an autonomy
framework, browser agent or multi-agent swarm. This document records decisions
rather than asserting that future components are already implemented.

## Decision log

| Date | Options considered | Decision | Rationale |
| --- | --- | --- | --- |
| 2026-10-10 | Paid API by default; local model by default; offline cassette by default | Offline cassette default | Deterministic tests, zero accidental paid requests; M1 adds separate Anthropic and OpenAI-compatible adapters (including Ollama) |
| 2026-10-10 | Float USD; Decimal; integer micro-USD | Decimal config + integer micro-USD ledger | Avoid float drift; conservative ROUND_UP; atomic reservations in SQLite |
| 2026-10-10 | Auto-record provider output; reviewed fixture-only replay | Reviewed fixture-only replay | No silent real network usage or unreviewed PII/secrets in fixture files |
| 2026-10-10 | Framework agent runtime; custom bounded core | Custom asyncio core in future milestone | Exposes tool state and failure handling to reviewers; avoids hiding budgets behind a framework |
| 2026-10-10 | OpenTelemetry SDK; JSONL spans | Defer tracer choice to M5 | Avoid claiming compatibility before tracing is implemented |

## Spend model
`SpendLedger.reserve()` must be called *before* a paid request with a
conservative **upper bound** on cost and unique request ID. Reservations count
against both run and UTC-day limits; SQLite transactions serialize concurrent
reservations. `settle()` stores actual cost. If an estimate proves too low,
actual overspend is recorded and a `BudgetExceeded` error is raised. The API
cannot undo spending that a provider has already charged. Crashed/incomplete
requests remain reserved until audited, never automatically refunded.

The budget ledger is implemented in M0, but live adapters aren't. M1 must
ensure every live request uses it and explicitly documents per-model price
sources, token ceilings and cost estimation limitations.

## Decisions pending
- User-approved maximum spend **per run** and **per UTC day**.
- Which Anthropic and OpenAI-compatible model IDs and verified prices to use.
- Whether local Ollama is CPU-feasible on the user's Windows laptop.
- Generate and check in `uv.lock` on a networked development machine.
- Choose and document the exact provider fixture format for M1.
