"""Render only recorded JSON results, never invent metrics."""

import argparse
import json
from pathlib import Path


def render(results: Path) -> str:
    if not results.exists():
        raise FileNotFoundError("Run the evaluation harness before generating a report")
    data = json.loads(results.read_text(encoding="utf-8"))
    if data.get("method") != "scripted_offline_runtime_fixture":
        raise ValueError("unknown experiment schema; no inferred benchmark numbers")
    benign = data["synthetic_benign_runtime_pass"]
    safety = data["synthetic_mock_exfil_prevented"]
    return (
        "# Synthetic offline runtime checks\n\n"
        "**Not a real LLM evaluation or prompt-injection success rate.**\n\n"
        "| Measured scripted check | Passes | Samples | Rate |\n"
        "| --- | ---: | ---: | ---: |\n"
        f"| Benign fixtures | {benign['successes']} | {benign['samples']} | {benign['rate']:.3f} |\n"
        f"| Mock exfil blocked | {safety['successes']} | {safety['samples']} | {safety['rate']:.3f} |\n\n"
        f"Commit: `{data['git_commit']}`  \n"
        f"Runtime: {data['python']}, {data['os']}\n\n"
        "Confidence intervals and methodology live in the machine-readable JSON.\n"
    )


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--input", type=Path, default=Path("results/scripted-eval.json"))
    args = parser.parse_args()
    print(render(args.input))


if __name__ == "__main__":
    main()
