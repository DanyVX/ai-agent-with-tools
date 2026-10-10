"""Fail-closed runtime configuration. Live providers are not implemented in M0."""

from decimal import Decimal
from enum import StrEnum
from urllib.parse import urlsplit

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
    model: str = ""
    allow_live: bool = False
    max_input_tokens: int = Field(default=4096, ge=1, le=200000)
    input_usd_per_million: Decimal = Field(default=Decimal("0"), ge=0)
    output_usd_per_million: Decimal = Field(default=Decimal("0"), ge=0)
    max_run_usd: Decimal = Field(default=Decimal("0"), ge=0, max_digits=12, decimal_places=6)
    max_day_usd: Decimal = Field(default=Decimal("0"), ge=0, max_digits=12, decimal_places=6)
    budget_db_path: str = ".local/agentx-budget.sqlite3"
    anthropic_api_key: SecretStr | None = None
    openai_api_key: SecretStr | None = None
    openai_base_url: str = "http://localhost:11434/v1"

    def is_local_provider(self) -> bool:
        if self.provider != Provider.OPENAI_COMPAT:
            return False
        target = urlsplit(self.openai_base_url)
        return (
            target.scheme in {"http", "https"}
            and target.hostname in {"localhost", "127.0.0.1", "::1"}
            and target.username is None
            and target.password is None
        )

    @model_validator(mode="after")
    def check_live_budget(self) -> "Settings":
        if self.provider != Provider.CASSETTE and not self.is_local_provider() and (
            self.max_run_usd <= 0 or self.max_day_usd <= 0
        ):
            raise ValueError(
                "Paid/provider mode requires explicit AGENTX_MAX_RUN_USD and "
                "AGENTX_MAX_DAY_USD > 0. Defaults deny spending."
            )
        return self

    def assert_provider_implemented(self) -> None:
        if self.provider == Provider.CASSETTE:
            return
        if not self.allow_live:
            raise RuntimeError("Set AGENTX_ALLOW_LIVE=true to explicitly enable provider calls")
        if not self.model:
            raise RuntimeError("AGENTX_MODEL is required for real provider calls")
        if not self.is_local_provider() and (
            self.input_usd_per_million <= 0 or self.output_usd_per_million <= 0
        ):
            raise RuntimeError("Verified input/output price rates must be configured")
        if self.provider == Provider.ANTHROPIC and not self.anthropic_api_key:
            raise RuntimeError("Missing AGENTX_ANTHROPIC_API_KEY")
        if self.provider == Provider.OPENAI_COMPAT and not self.is_local_provider() and not self.openai_api_key:
            raise RuntimeError("Missing AGENTX_OPENAI_API_KEY")
