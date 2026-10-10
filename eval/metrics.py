"""Measured rates and Wilson uncertainty intervals."""

import math


def wilson(success: int, total: int, z: float = 1.96) -> tuple[float, float]:
    if total <= 0 or success < 0 or success > total:
        raise ValueError("invalid success/total count")
    p = success / total
    denominator = 1 + z * z / total
    center = (p + z * z / (2 * total)) / denominator
    half = z * math.sqrt((p * (1 - p) + z * z / (4 * total)) / total) / denominator
    return max(0.0, center - half), min(1.0, center + half)


def rate(success: int, total: int) -> dict[str, float | int | list[float]]:
    lower, upper = wilson(success, total)
    return {
        "successes": success,
        "samples": total,
        "rate": success / total,
        "wilson_95": [lower, upper],
    }
