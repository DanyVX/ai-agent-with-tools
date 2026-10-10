# Threat model

## Assets

Private task data, provider credentials and account balance, tool permissions, local sandbox notes and outbox, trace/run-state files, model responses and evaluated security labels.

## Adversaries and boundaries

- A user-facing task can contain a direct attacker request.
- Any file, HTTP fixture, search result, SQLite row or tool return is **untrusted** relative to the system/developer policy.
- A model may propose a tool call but **cannot expand code-owned capability policy** or authorize a side-effect by its own output.
- The terminal human approver can grant exact arguments or edit them; edits must be validated anew.

## Protections implemented

| Threat | Control | Residual risk |
| --- | --- | --- |
| Unsafe math execution | AST allowlist, no eval | CPU-heavy numeric expressions remain limited heuristically |
| File traversal | canonical root, encoded/absolute/backslash rejection | TOCTOU with hostile local filesystem |
| SQL write | SQLite ro mode, query-only, single SELECT | expensive SELECT not yet progress-interrupted |
| SSRF and redirects | No live HTTP transport; fixed reviewed fixtures | Not a general web agent |
| Secret/canary in mock outbound argument | String scanning before tool call | Encoded/fragmented secrets may evade checks |
| Unauthorized mock email/note | Code policy + exact human approval | Human may approve malicious arguments |
| Duplicate effects | Idempotent on-disk keys | Cross-process durability applies to files but no remote atomicity |
| Prompt injection | Untrusted tool result delimiters, fixed policy | Delimiters do not guarantee semantic safety |
| Expense runaway | Atomic run/day SQLite reservations, step/token/time caps | Provider billing reconciliation limitations |
| Log leakage | redacted/truncated previews, no raw default | Pattern misses, hashes and metadata leakage |

## Test coverage and outcomes

`tests/test_tools.py`, `test_guard.py`, `test_budget.py`, and 30 generated synthetic attack cases exercise confinement/approval failure modes. `eval/harness.py` reports those scripted outcomes separately from **unmeasured** real-model attack success and benign false-refusal rates.

## Response

Suspected leaked credentials must be revoked and rotated immediately, even if Git history is later rewritten. Suspected unsafe network behavior must be disabled rather than bypassing a failing guard. Never use actual credentials, ID images, biometric embeddings or contact details as synthetic canaries.
