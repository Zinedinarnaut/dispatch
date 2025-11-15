"""Telemetry event collection for Dispatch."""
from __future__ import annotations

import asyncio
import contextlib
import json
import time
from dataclasses import asdict, dataclass, field
from typing import Any, Dict, Optional

import httpx

from ..core.config import get_settings


@dataclass(slots=True)
class TelemetryEvent:
    """Represents a single telemetry data point."""

    name: str
    attributes: Dict[str, Any] = field(default_factory=dict)
    timestamp: float = field(default_factory=lambda: time.time())


class TelemetryClient:
    """In-memory telemetry buffer with optional forwarding."""

    def __init__(self) -> None:
        self._events: asyncio.Queue[TelemetryEvent] = asyncio.Queue()
        self._settings = get_settings()
        self._sender_task: Optional[asyncio.Task[None]] = None

    async def start(self) -> None:
        if self._settings.telemetry_endpoint and self._sender_task is None:
            self._sender_task = asyncio.create_task(self._forward_events())

    async def stop(self) -> None:
        if self._sender_task:
            self._sender_task.cancel()
            with contextlib.suppress(asyncio.CancelledError):
                await self._sender_task

    async def record(self, event: TelemetryEvent) -> None:
        await self._events.put(event)

    async def _forward_events(self) -> None:
        assert self._settings.telemetry_endpoint is not None
        async with httpx.AsyncClient() as client:
            while True:
                event = await self._events.get()
                payload = json.dumps(asdict(event))
                try:
                    await client.post(str(self._settings.telemetry_endpoint), content=payload)
                except httpx.HTTPError:
                    # Swallow telemetry errors to avoid cascading failures
                    pass


telemetry_client = TelemetryClient()
