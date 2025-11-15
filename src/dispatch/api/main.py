"""FastAPI application entrypoint for Dispatch."""
from __future__ import annotations

import asyncio
from dataclasses import asdict
from typing import List, Optional

from fastapi import Depends, FastAPI, HTTPException, Query, Request, status
from fastapi.middleware.cors import CORSMiddleware

from ..core.config import get_settings
from ..scraping.service import collect_from_scraper, create_registry
from ..security.auth import verify_api_key
from ..security.rate_limiter import RateLimiter
from ..telemetry.events import TelemetryEvent, telemetry_client

settings = get_settings()
app = FastAPI(title=settings.app_name, version="1.0.0")
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.allowed_origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

registry = create_registry(timeout=settings.default_timeout_seconds, user_agent=settings.user_agent)
rate_limiter = RateLimiter(max_requests=settings.request_rate_per_minute)


async def enforce_rate_limit(request: Request) -> None:
    identifier = request.client.host if request.client else "anonymous"
    allowed = await rate_limiter.allow(identifier)
    if not allowed:
        raise HTTPException(status_code=status.HTTP_429_TOO_MANY_REQUESTS, detail="Rate limit exceeded")


@app.on_event("startup")
async def on_startup() -> None:
    await telemetry_client.start()
    await telemetry_client.record(TelemetryEvent(name="app.startup", attributes={"environment": settings.environment}))


@app.on_event("shutdown")
async def on_shutdown() -> None:
    await telemetry_client.record(TelemetryEvent(name="app.shutdown"))
    await telemetry_client.stop()


@app.get("/", dependencies=[Depends(enforce_rate_limit)])
async def root() -> dict:
    return {"service": settings.app_name, "message": "Dispatch API is online."}


@app.get("/health", dependencies=[Depends(enforce_rate_limit)])
async def health() -> dict:
    return {"status": "ok"}


@app.get(f"{settings.api_v1_prefix}/providers", dependencies=[Depends(enforce_rate_limit)])
async def list_providers() -> dict:
    return {"providers": registry.providers}


@app.get(f"{settings.api_v1_prefix}/products", dependencies=[Depends(enforce_rate_limit), Depends(verify_api_key)])
async def get_products(
    request: Request,
    providers: Optional[List[str]] = Query(None, description="Specific providers to query."),
    query: Optional[str] = Query(None, description="Optional search term."),
    limit: Optional[int] = Query(None, ge=1, le=100, description="Limit results per provider."),
) -> dict:
    selected = providers or registry.providers
    results = {}
    tasks = []
    for provider in selected:
        scraper = registry.get(provider)
        tasks.append(collect_from_scraper(scraper, query=query, limit=limit))
    gather_results = await asyncio.gather(*tasks, return_exceptions=True)
    for provider, outcome in zip(selected, gather_results):
        if isinstance(outcome, Exception):
            await telemetry_client.record(
                TelemetryEvent(name="scraper.error", attributes={"provider": provider, "error": str(outcome)})
            )
            continue
        results[provider] = [asdict(product) for product in outcome]
    await telemetry_client.record(
        TelemetryEvent(
            name="api.products",
            attributes={
                "providers": selected,
                "query": query or "",
                "count": sum(len(items) for items in results.values()),
                "client": request.client.host if request.client else "anonymous",
            },
        )
    )
    return {"providers": results}
