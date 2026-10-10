# Design and decision log

**Scope:** Small audited core with narrow tool contracts, not general autonomy, browser control, or multi-agent delegation.

## Decision log

| Date | Options | Choice | Reason |
| --- | --- | --- | --- |
| 2026-10-10 | Pass internal messages unchanged to providers; normalize per-provider tool messages | Normalized assistant tool calls and untrusted tool results through a separate transcript adapter | OpenAI-compatible chat completions require tool role + call IDs; Anthropic requires tool_use/tool_result blocks. Exact correlation is essential for real multi-turn runs and offline replay. |
| 2026-10-10 | Agent framework vs explicit loop | Explicit asyncio runtime | All tool calls, approvals and budgets remain inspectable |
| 2026-10-10 | Single provider vs protocol | Provider-normalized `LLMClient` | Offline cassettes, Anthropic and OpenAI-compatible tests share a contract |
| 2026-10-10 | Raw model outputs vs typed contract | Pydantic normalized `LLMResponse` | Malformed JSON cannot silently call a tool |
| 2026-10-10 | Floating cost vs integer ledger | Decimal input, SQLite micro-USD reservations | Avoid floating error, serialize concurrent reservations |
| 2026-10-10 | Unreviewed web requests vs offline fixture | Offline `http_get` only | A naive allowlist does not prevent DNS rebinding; fail safely |
| 2026-10-10 | Automatic side effects vs user approval | Exact-argument explicit approval | Model-generated requests are not authorization |
| 2026-10-10 | Raw trace vs protected previews | Redacted SHA + bounded preview | Minimize private-data retention and log sizes |
| 2026-10-10 | Large general eval claims vs synthetic programmatic tests | 40+30 scripted fixtures | Verify mechanics without inventing LLM success rates |
| 2026-10-10 | Embedded framework tracing vs JSONL | JSONL spans + SQLite outcomes | Inspectable, portable debugging; OTel exporter postponed |
| 2026-10-10 | Silent cassette re-recording vs strict matching | SHA256 request hash + fail on drift | No accidental external requests or changed fixture behavior |

## Contracts

`LLMClient.complete(messages, tools, max_tokens, temperature)` returns text, typed tool calls, usage (estimated flagged), and stop reason. Invalid provider payloads raise typed errors; tool validators reject unknown arguments.

`ToolRegistry` decides valid tool names and schemas. `GuardedExecutor` restricts capabilities through code policy, checks outbound synthetic canaries and consults an external approval callback for side-effect tools. `AgentRunner` never promotes tool observations into policy instructions.

## Cost-bound details

A paid provider is unavailable until all of the following are explicitly configured: an opt-in flag, model ID, credentials, auditable per-token pricing, and positive run/day dollar caps. `BudgetedClient` reserves based on configured **maximum** input tokens and allowed output tokens. Reservations are atomic; actual usage is settled afterward. If actual billing exceeds the reservation, overspend is recorded and future requests blocked, but past provider charges cannot be undone. Missing usage is estimated and marked as uncertain.

## Replay

An exact cassette hash includes messages, selected tool schemas, temperature and max tokens. Missing hashes fail, never re-record automatically. Synthetic run recording needs an explicit flag and original task is needed for replay. Real user prompts are never recorded this way by default.

## Not claimed

Real-model benchmark quality, verified injection immunity, true OpenTelemetry interoperability, unrestricted safe web browsing, performance on production biometric data, model-license commercial clearance or a hardened multi-tenant deployment.
