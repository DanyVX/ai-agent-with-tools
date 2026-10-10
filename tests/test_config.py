"""Default spend is denied until explicitly configured."""

from decimal import Decimal

import pytest
from pydantic import ValidationError

from agentx.config import Provider, Settings


def test_safe_defaults(monkeypatch: pytest.MonkeyPatch) -> None:
    for name in ("PROVIDER", "MAX_RUN_USD", "MAX_DAY_USD"):
        monkeypatch.delenv(f"AGENTX_{name}", raising=False)
    settings = Settings(_env_file=None)
    assert settings.provider == Provider.CASSETTE
    assert settings.max_run_usd == Decimal("0")
    assert settings.max_day_usd == Decimal("0")


@pytest.mark.parametrize("provider", ["anthropic", "openai_compat"])
def test_live_provider_requires_explicit_positive_caps(provider: str) -> None:
    with pytest.raises(ValidationError, match="requires explicit"):
        Settings(_env_file=None, provider=provider)


def test_live_provider_remains_disabled_in_m0() -> None:
    settings = Settings(
        _env_file=None,
        provider="anthropic",
        max_run_usd=Decimal("0.50"),
        max_day_usd=Decimal("2"),
    )
    with pytest.raises(RuntimeError, match="AGENTX_ALLOW_LIVE"):
        settings.assert_provider_implemented()


@pytest.mark.parametrize("bad", ["-1", "NaN", "Infinity", "a lot"])
def test_invalid_spend_config_rejected(bad: str) -> None:
    with pytest.raises(ValidationError):
        Settings(_env_file=None, max_run_usd=bad)


def test_secret_never_in_repr() -> None:
    settings = Settings(_env_file=None, anthropic_api_key="dont-print-this")
    assert "dont-print-this" not in repr(settings)
