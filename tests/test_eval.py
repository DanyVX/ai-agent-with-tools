"""Evaluation cardinality and non-fabrication checks."""

from pathlib import Path

import pytest

from eval.adversarial.generate import make_attack_cases
from eval.harness import evaluate
from eval.metrics import rate, wilson
from eval.tasks.generate import make_benign_cases


def test_eval_case_counts_and_uniqueness() -> None:
    benign = make_benign_cases()
    attacks = make_attack_cases()
    assert len(benign) >= 40 and len(attacks) >= 30
    assert len({c.case_id for c in benign}) == len(benign)
    assert len({c.case_id for c in attacks}) == len(attacks)


def test_wilson_interval_bounds() -> None:
    lo, hi = wilson(4, 10)
    assert 0 <= lo <= 0.4 <= hi <= 1
    with pytest.raises(ValueError):
        wilson(1, 0)
    assert rate(2, 4)["samples"] == 4


@pytest.mark.asyncio
async def test_scripted_eval_harness(tmp_path: Path) -> None:
    path = tmp_path / "report.json"
    data = await evaluate(path, repeats=1)
    assert path.exists()
    assert data["method"] == "scripted_offline_runtime_fixture"
    assert data["benign_cases"] >= 40
    assert data["adversarial_cases"] >= 30
    assert data["NOT_real_model_reliability"]
