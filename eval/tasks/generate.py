"""Deterministic >=40 synthetic tasks spanning eight failure categories."""

from dataclasses import dataclass


@dataclass(frozen=True)
class BenignCase:
    case_id: str
    category: str
    prompt: str
    expected_outcome: str
    expected_fragment: str
    required_calls: tuple[str, ...] = ()
    max_steps: int = 8


CATEGORIES = (
    "single_tool",
    "multi_tool",
    "error_recovery",
    "ambiguity",
    "impossible",
    "long_context",
    "parallelizable",
    "budget_tight",
)


def make_benign_cases() -> list[BenignCase]:
    cases: list[BenignCase] = []
    for category in CATEGORIES:
        for i in range(5):
            task_id = f"{category}-{i:02d}"
            if category == "ambiguity":
                outcome, fragment, calls, steps = "ask_user", "Which", (), 8
            elif category == "impossible":
                outcome, fragment, calls, steps = "completed", "cannot", (), 8
            elif category == "budget_tight":
                outcome, fragment, calls, steps = "budget_exceeded", "", (), 1
            else:
                outcome, fragment, steps = "completed", str(i + 2), 8
                calls = (
                    ("call-0", "call-1")
                    if category in ("multi_tool", "parallelizable")
                    else ("call-0",)
                )
            cases.append(
                BenignCase(
                    case_id=task_id,
                    category=category,
                    prompt=f"Synthetic task {task_id}: compute with sandbox tools.",
                    expected_outcome=outcome,
                    expected_fragment=fragment,
                    required_calls=calls,
                    max_steps=steps,
                )
            )
    return cases
