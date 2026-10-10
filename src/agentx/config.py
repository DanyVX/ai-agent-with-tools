"""Fail-closed runtime configuration. Live providers are not implemented in M0."""

from decimal import Decimal
from enum import StrEnum

from pydantic import Field, SecretStr, model_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


class Provider(StrEnum):
    CASSETTE = "cassette"
    ANTHROPIC = "anthropic"
    OPENAI_COMPAT = "openai_compat"


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_prefix="AGENTX_",
        env_file=".env",
        extra="forbid",
        case_sensitive=False,
    )

    provider: Provider = Provider.CASSETTE
    max_run_usd: Decimal = Field(default=Decimal("0"), ge=0, max_digits=12, decimal_places=6)
    max_day_usd: Decimal = Field(default=Decimal("0"), ge=0, max_digits=12, decimal_places=6)
    budget_db_path: str = ".local/agentx-budget.sqlite3"
    anthropic_api_key: SecretStr | None = None
    openai_api_key: SecretStr | None = None
    openai_base_url: str = "http://localhost:11434/v1"

    @model_validator(mode="after")
    def check_live_budget(self) -> "Settings":
        if self.provider != Provider.CASSETTE and (self.max_run_usd <= 0 or self.max_day_usd <= 0):
            raise ValueError(
                "Paid/provider mode requires explicit AGENTX_MAX_RUN_USD and "
                "AGENTX_MAX_DAY_USD > 0. Defaults deny spending."
            )
        return self

    def assert_provider_implemented(self) -> None:
        if self.provider != Provider.CASSETTE:
            raise RuntimeError(
                "Live providers are not implemented in M0. "
                "Selecting a provider does not authorize a network request."
            )
