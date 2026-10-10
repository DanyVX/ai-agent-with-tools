# Changelog

This file follows [Keep a Changelog](https://keepachangelog.com/en/1.1.0/).

## [Unreleased]

### Added
- M0 baseline: fail-closed provider settings, atomic SQLite spend ledger, offline cassette storage, CI and repository hygiene.
- M1 normalized provider protocol, Anthropic and OpenAI-compatible non-streaming adapters, typed errors, retry/backoff with Retry-After.
- M2 Pydantic tool registry, sandbox math/files/SQLite tools, offline-only reviewed HTTP fixtures and idempotent mock side effects.
- M3 bounded agent runtime, context reduction, loop detection and structured terminal outcomes.
- M4 code-owned capability policy, explicit human approvals, redaction and synthetic canary exfil checks.
- M5 redacted JSONL traces, SQLite outcomes and opt-in synthetic recording/replay.
- M6 generator for 40 benign and 30 adversarial offline scripted cases, report renderer and Wilson confidence intervals.
- M7 CLI with demo, run, evaluation, trace and replay commands, and reserve-before-send paid provider wrapper.

### Security
- Updated audited vulnerable direct dependencies detected by CI.

No release has been tagged; real-model evaluation and hardened production deployment remain unverified.
