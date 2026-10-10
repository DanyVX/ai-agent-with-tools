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
        Settings(
            _env_file=None,
            provider=provider,
            openai_base_url="https://api.example.org/v1",
        )


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

def test_local_model_requires_opt_in_but_no_money_or_api_key() -> None:
    from agentx.config import Provider

    local = Settings(
        _env_file=None,
        provider=Provider.OPENAI_COMPAT,
        model="local-fixture-id",
        allow_live=True,
        openai_base_url="http://127.0.0.1:11434/v1",
    )
    assert local.is_local_provider()
    local.assert_provider_implemented()


def test_remote_openai_compat_keeps_spend_caps() -> None:
    with pytest.raises(ValidationError, match="requires explicit"):
        Settings(
            _env_file=None,
            provider="openai_compat",
            openai_base_url="https://api.example.org/v1",
            allow_live=True,
            model="example",
        )
