"""Application configuration for Dispatch services."""
from __future__ import annotations

from functools import lru_cache
from typing import List

from pydantic import AnyUrl, BaseSettings, Field, validator


class Settings(BaseSettings):
    """Runtime configuration loaded from environment variables."""

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
    telemetry_endpoint: AnyUrl | None = Field(
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

    class Config:
        env_file = ".env"
        env_file_encoding = "utf-8"

    @validator("api_keys", pre=True)
    def _split_api_keys(cls, value: str | list[str]) -> list[str]:
        if isinstance(value, str):
            return [item.strip() for item in value.split(",") if item.strip()]
        return value


@lru_cache()
def get_settings() -> Settings:
    """Return cached application settings."""

    return Settings()
