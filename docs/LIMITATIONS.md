# Limitations and negative results

- No runnable agent, tool registry, provider adapters, approval, guardrails, tracing
  or evaluation harness exist in M0. None of the M1-M7 acceptance tests are met.
- No real-model experiment, cost result, security success rate or confidence
  interval has been measured. Placeholder results are not evidence.
- A source lockfile (`uv.lock`) cannot yet be generated/verified without PyPI
  access; transitive dependency pinning and fresh-clone reproducibility remain open.
- Local developer environment was a hosted Linux CPU-only runner (Python 3.13.5),
  not the owner's Windows setup. M0 CI targets Python 3.11/3.12 but hasn't been
  confirmed green at the time this file was written.
- A token-price estimate is not a billing guarantee. If the provider bills more
  than reserved, the actual spend can exceed a cap; the ledger records and flags
  this failure, but cannot reverse billed charges.
- The cassette replay checks request fingerprints, not fixture confidentiality
  or authenticity. Only reviewed synthetic/sanitized fixtures may be committed.
- Confinement defenses, injection protection and redaction are not implemented.
  They will be tested and documented at M4/M5, not advertised now.
