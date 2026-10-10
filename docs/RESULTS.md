# Experimental results

| Real-model metric | Result |
| --- | --- |
| Benign task success / uncertainty | TBD (not yet measured) |
| Prompt injection attack success / uncertainty | TBD (not yet measured) |
| Benign false-refusal rate | TBD (not yet measured) |
| Step and tool-error recovery rate | TBD (not yet measured) |
| Cost / tokens / latency | TBD (not yet measured) |
| Two-model comparison | TBD (not yet measured) |
| Guard/repair ablation | TBD (not yet measured) |

`eval/harness.py` contains **40 benign and 30 adversarial synthetic fixtures** with executable checks. Run `agentx eval` to record a real execution of those scripted checks. Such a file uses `method=scripted_offline_runtime_fixture` and deliberately includes the fields `NOT_real_model_reliability` and `NOT_prompt_injection_attack_success_rate`. Do not relabel it.

`bench/smoke.py` executes a true CPU microbenchmark of cassette fingerprints, not an agent-quality test. JSON includes OS, Python, package versions, timestamp and source commit. The code is the source of truth: any future README table must be rendered from a committed machine-generated JSON with these metadata fields.

## Reproducible offline measurements (GitHub Actions)

The automated run produced [a machine-readable fixture result](../results/scripted-eval.json),
[a generated Markdown report](../results/scripted-report.md), and
[a CPU smoke measurement](../results/m0-smoke.json). These were recorded by CI
on the parent commit identified in the JSON, including the Python runtime,
platform, package versions, and number of repetitions. Run the same scripts to
reproduce measurements on your own hardware. Only the report generator renders
these numeric results; do not describe them as real-model reliability or prompt-
injection robustness.
