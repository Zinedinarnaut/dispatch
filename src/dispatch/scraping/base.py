"""Shared abstractions for Dispatch scraping clients."""
from __future__ import annotations

import abc
from dataclasses import dataclass, field
from datetime import datetime
from typing import Any, Dict, Iterable, List, Optional


@dataclass(slots=True)
class Product:
    """Normalized representation of a product item."""

    provider: str
    name: str
    url: str
    price: Optional[float]
    currency: Optional[str]
    images: List[str] = field(default_factory=list)
    description: Optional[str] = None
    brand: Optional[str] = None
    categories: List[str] = field(default_factory=list)
    metadata: Dict[str, Any] = field(default_factory=dict)
    last_seen: datetime = field(default_factory=datetime.utcnow)


class ScraperError(RuntimeError):
    """Raised when a scraper cannot complete its task."""


class BaseScraper(abc.ABC):
    """Base class for site-specific scrapers."""

    provider: str

    def __init__(self, *, timeout: float, user_agent: str):
        self.timeout = timeout
        self.user_agent = user_agent

    @abc.abstractmethod
    async def fetch_products(self, *, query: Optional[str] = None, limit: Optional[int] = None) -> Iterable[Product]:
        """Collect products matching an optional query string."""

    async def _limit(self, items: Iterable[Product], limit: Optional[int]) -> List[Product]:
        if limit is None:
            return list(items)
        limited: List[Product] = []
        for item in items:
            limited.append(item)
            if len(limited) >= limit:
                break
        return limited
