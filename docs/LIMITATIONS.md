# Known limitations and negative results

1. **No verified real LLM scores.** Anthropic and OpenAI-compatible integrations have mocked contract coverage but no paid/model benchmark run. Real-model task success, attack success and false refusal are all unmeasured.
2. **No generic live web fetching.** `http_get` deliberately uses reviewed HTTPS fixture mappings. Domain checking plus preflight DNS alone cannot prevent DNS rebinding; enabling real network without an address-pinned connection/redirect check is unsafe.
3. **Prompt injection is not solved.** Tool outputs are explicitly untrusted and side effects require approval, but models may still be steered to bad non-side-effect answers. Scripted canary checks do not measure that probability.
4. **Approval UI is local.** Interactive CLI approval is default deny, but is not a remote/multi-user approval service. The synchronous prompt is not a strong wall-clock guarantee.
5. **Synthetic replay is opt-in.** Arbitrary provider calls are not transparently replayable because real prompts might contain private data. Exact request hashing deliberately refuses drift.
6. **Streaming not implemented.** Providers use non-streaming JSON responses. Interruptions in a streaming transfer are therefore not exercised.
7. **Token budget estimation.** Some providers omit usage. An explicitly estimated count is an approximation, not exact billing. External charges can exceed a reserved estimate.
8. **Sandbox is a path guard, not an OS container.** It rejects traversal/encoded names/symlink escapes at validation but does not defend against a hostile local process racing symlink replacement. Do not use with untrusted shared writable directories.
9. **SQLite read-only queries are constrained.** Only single SELECT statements, row caps and query-only database connection. Resource-heavy SQL and unusual SQLite functions warrant additional limits.
10. **Redaction is best-effort.** API-key/PII patterns are incomplete, and SHA previews leak length/timing. Do not log raw biometrics or use real credentials in synthetic fixtures.
11. **Missing deployment extras.** No Docker image, GIF/video demo, verified `uv.lock`, commercial-license sweep or v0.1.0 tagged release has yet been delivered.
12. **Evaluation gaps.** The generated task classes meet basic cardinality, but truly difficult long-context, real-model ablation, replay after crash and live provider deprecation handling remain partial.

These are blockers to calling this production-ready, not items to conceal.

- Live multi-turn tool-call formatting now has offline provider contract coverage for Anthropic and OpenAI-compatible APIs, but real credentialed model requests are still not verified.
