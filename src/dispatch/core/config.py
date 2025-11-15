"""Application configuration for Dispatch services."""
from __future__ import annotations

from functools import lru_cache
import json
import logging
from pathlib import Path
import secrets
from typing import List

from pydantic import Field, field_validator, model_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


logger = logging.getLogger("dispatch.config")


def _tolerant_json_loads(value: str):
    """Parse JSON for complex env fields but allow blank strings."""

    if value == "":
        return value
    return json.loads(value)


class Settings(BaseSettings):
    """Runtime configuration loaded from environment variables."""

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
        json_loads=_tolerant_json_loads,
    )

    app_name: str = Field(default="Dispatch", description="Human readable application name.")
    environment: str = Field(default="development", description="Environment name for telemetry tagging.")
    api_v1_prefix: str = Field(default="/api/v1", description="Prefix for versioned API routes.")
    default_timeout_seconds: float = Field(default=10.0, description="HTTP timeout used for outbound scraping requests.")
    max_connections: int = Field(default=10, description="Maximum concurrent connections per target host.")
    user_agent: str = Field(
        default=(
            "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
            "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
        ),
        description="User agent string used when scraping remote e-commerce sites.",
    )
    allowed_origins: List[str] = Field(
        default_factory=lambda: ["*"],
        description="List of CORS origins allowed to access the API.",
    )
    telemetry_endpoint: str | None = Field(
        default=None,
        description="Optional external telemetry collector endpoint for forwarding events.",
    )
    api_keys: List[str] = Field(
        default_factory=list,
        description="Optional list of static API keys that can access privileged routes.",
    )
    request_rate_per_minute: int = Field(
        default=60,
        description="Maximum number of API requests allowed per minute for a single client identifier.",
    )
    scrape_interval_seconds: int = Field(
        default=1800,
        ge=60,
        description="Interval between automated scraping passes.",
    )
    database_url: str = Field(
        default="sqlite:///./dispatch.db",
        description="Database connection string used for persisting scraped products.",
    )
    log_level: str = Field(default="INFO", description="Application log level.")
    master_key: str | None = Field(default=None, description="Master API key generated automatically if missing.")

    @field_validator("api_keys", mode="before")
    def _split_api_keys(cls, value: str | list[str]) -> list[str]:
        if isinstance(value, str):
            return [item.strip() for item in value.split(",") if item.strip()]
        return value

    @model_validator(mode="after")
    def _ensure_master_in_keys(self) -> "Settings":
        if self.master_key and self.master_key not in self.api_keys:
            object.__setattr__(self, "api_keys", [*self.api_keys, self.master_key])
        return self


def _persist_master_key(path: Path, key: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    if path.exists():
        content = path.read_text(encoding="utf-8")
        if "MASTER_KEY" in content:
            return
        with path.open("a", encoding="utf-8") as handle:
            handle.write(f"\nMASTER_KEY={key}\n")
            if "API_KEYS" not in content:
                handle.write(f"API_KEYS={key}\n")
    else:
        path.write_text(f"MASTER_KEY={key}\nAPI_KEYS={key}\n", encoding="utf-8")


@lru_cache()
def get_settings() -> Settings:
    """Return cached application settings and ensure runtime defaults are persisted."""

    settings = Settings()
    if not settings.master_key:
        key = secrets.token_urlsafe(32)
        object.__setattr__(settings, "master_key", key)
        object.__setattr__(settings, "api_keys", [*settings.api_keys, key])
        env_file = Path(settings.model_config.get("env_file", ".env"))
        try:
            _persist_master_key(env_file, key)
            logger.warning("Generated new MASTER_KEY and stored it in %s", env_file)
        except OSError as exc:
            logger.error("Failed to persist MASTER_KEY to %s: %s", env_file, exc)
    return settings
