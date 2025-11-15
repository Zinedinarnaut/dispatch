"""Authentication helpers for Dispatch."""
from __future__ import annotations

from fastapi import HTTPException, Security, status
from fastapi.security import APIKeyHeader

from ..core.config import get_settings

api_key_header = APIKeyHeader(name="X-Dispatch-Key", auto_error=False)


def verify_api_key(api_key: str = Security(api_key_header)) -> None:
    settings = get_settings()
    if not settings.api_keys:
        return
    if api_key in settings.api_keys:
        return
    raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid API key")
