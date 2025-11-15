"""HTTP utilities for Dispatch scrapers."""
from __future__ import annotations

from contextlib import asynccontextmanager

import httpx

from .config import get_settings


@asynccontextmanager
async def get_async_client() -> httpx.AsyncClient:
    settings = get_settings()
    limits = httpx.Limits(max_connections=settings.max_connections, max_keepalive_connections=settings.max_connections)
    headers = {"User-Agent": settings.user_agent}
    async with httpx.AsyncClient(timeout=settings.default_timeout_seconds, limits=limits, headers=headers) as client:
        yield client
