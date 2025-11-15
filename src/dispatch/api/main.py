"""FastAPI application entrypoint for Dispatch."""
from __future__ import annotations

import asyncio
import logging
from contextlib import suppress
from dataclasses import asdict
from typing import List, Optional

from fastapi import Depends, FastAPI, HTTPException, Query, Request, status
from fastapi.middleware.cors import CORSMiddleware

from ..core.config import get_settings
from ..core.logging import setup_logging
from ..db.repository import fetch_products as fetch_cached_products
from ..db.repository import upsert_products
from ..db.session import configure_engine, init_db, session_scope
from ..scraping.base import Product
from ..scraping.service import collect_from_scraper, create_registry
from ..security.auth import verify_api_key
from ..security.rate_limiter import RateLimiter
from ..telemetry.events import TelemetryEvent, telemetry_client

settings = get_settings()
setup_logging(settings.log_level)
logger = logging.getLogger("dispatch.api")
configure_engine()
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
scraping_task: asyncio.Task | None = None


async def enforce_rate_limit(request: Request) -> None:
    identifier = request.client.host if request.client else "anonymous"
    allowed = await rate_limiter.allow(identifier)
    if not allowed:
        raise HTTPException(status_code=status.HTTP_429_TOO_MANY_REQUESTS, detail="Rate limit exceeded")


async def _persist_results(provider: str, items: List[Product]) -> int:
    def _store() -> int:
        with session_scope() as session:
            return upsert_products(session, items)

    return await asyncio.to_thread(_store)


async def run_scraping_cycle() -> None:
    logger.info("Starting scraping cycle for providers: %s", ", ".join(registry.providers))
    tasks = [collect_from_scraper(registry.get(provider), query=None, limit=None) for provider in registry.providers]
    results = await asyncio.gather(*tasks, return_exceptions=True)
    stored = 0
    for provider, outcome in zip(registry.providers, results):
        if isinstance(outcome, Exception):
            logger.error("Scraper for %s failed: %s", provider, outcome)
            await telemetry_client.record(
                TelemetryEvent(name="scraper.error", attributes={"provider": provider, "error": str(outcome)})
            )
            continue
        stored_count = await _persist_results(provider, outcome)
        stored += stored_count
        logger.info("Stored %s products for provider %s", stored_count, provider)
    await telemetry_client.record(
        TelemetryEvent(
            name="scraper.cycle",
            attributes={
                "providers": registry.providers,
                "stored": stored,
            },
        )
    )


async def background_scraper_loop() -> None:
    while True:
        try:
            await run_scraping_cycle()
        except Exception as exc:  # pragma: no cover - defensive logging
            logger.exception("Automated scraping cycle failed: %s", exc)
            await telemetry_client.record(
                TelemetryEvent(name="scraper.cycle.error", attributes={"error": str(exc)})
            )
        await asyncio.sleep(settings.scrape_interval_seconds)


@app.on_event("startup")
async def on_startup() -> None:
    logger.info("Initialising Dispatch API")
    await asyncio.to_thread(init_db)
    await telemetry_client.start()
    await telemetry_client.record(TelemetryEvent(name="app.startup", attributes={"environment": settings.environment}))
    global scraping_task
    scraping_task = asyncio.create_task(background_scraper_loop())
    logger.info("Background scraper loop started with interval %ss", settings.scrape_interval_seconds)


@app.on_event("shutdown")
async def on_shutdown() -> None:
    logger.info("Shutting down Dispatch API")
    if scraping_task:
        scraping_task.cancel()
        with suppress(asyncio.CancelledError):
            await scraping_task
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


@app.get(
    f"{settings.api_v1_prefix}/products/cache",
    dependencies=[Depends(enforce_rate_limit), Depends(verify_api_key)],
)
async def get_cached_products(
    provider: Optional[str] = Query(None, description="Filter cached results by provider."),
    limit: Optional[int] = Query(None, ge=1, le=500, description="Maximum number of records to return."),
) -> dict:
    def _fetch() -> List[dict]:
        with session_scope() as session:
            records = fetch_cached_products(session, provider=provider, limit=limit)
            return [
                {
                    "provider": record.provider,
                    "name": record.name,
                    "url": record.url,
                    "price": record.price,
                    "currency": record.currency,
                    "images": record.images,
                    "description": record.description,
                    "brand": record.brand,
                    "categories": record.categories,
                    "metadata": record.attributes,
                    "last_seen": record.last_seen.isoformat(),
                }
                for record in records
            ]

    cached = await asyncio.to_thread(_fetch)
    logger.info("Served %s cached products (provider=%s)", len(cached), provider or "all")
    return {"results": cached}
