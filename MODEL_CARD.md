# Model card / provider choices

**No trained or pretrained model weights are included or redistributed.**
Model IDs are provided by the operator at runtime. The deterministic scripted
demo is not an LLM and must never be compared to model quality.

## Intended usage
Compare tool-use reliability and refusal/security behavior of explicitly selected
LLMs in a sandbox with budgets and written provider approval.

## Model license and provenance
No exact provider model has been selected or validated. Before any real-model
benchmark, record: provider, exact model revision, official model card and license,
effective rate/pricing date, context size, allowed use terms, and verified request
parameters. Do not assume Ollama packaging makes every underlying model commercial.

## Limitations
Demographic fairness, multilingual injection success, model deprecation, hallucination
rates and long-context reliability are **not evaluated**. Any future biometric/KYC
extension must add fairness/lighting/camera and consent analysis separately.

## Metrics
Benign success, attack success and false refusal: TBD (not yet measured).
