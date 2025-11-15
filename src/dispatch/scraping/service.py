"""Scraping service orchestrating provider-specific scrapers."""
from __future__ import annotations

import logging
from typing import Dict, Iterable, List, Optional

from .base import BaseScraper, Product, ScraperError
from .sites.complexshop import ComplexShopScraper
from .sites.goat import GoatScraper
from .sites.universalstore import UniversalStoreScraper

logger = logging.getLogger("dispatch.scraping")


class ScraperRegistry:
    """Registry for site scrapers."""

    def __init__(self, scrapers: Iterable[BaseScraper]):
        self._scrapers: Dict[str, BaseScraper] = {scraper.provider: scraper for scraper in scrapers}

    @property
    def providers(self) -> List[str]:
        return sorted(self._scrapers.keys())

    def get(self, provider: str) -> BaseScraper:
        try:
            return self._scrapers[provider]
        except KeyError as exc:
            raise ScraperError(f"Unknown provider '{provider}'") from exc


async def collect_from_scraper(scraper: BaseScraper, *, query: Optional[str], limit: Optional[int]) -> List[Product]:
    logger.debug("Collecting products from %s", scraper.provider)
    products = await scraper.fetch_products(query=query, limit=limit)
    items = list(products)
    logger.debug("Collected %s products from %s", len(items), scraper.provider)
    return items


def create_registry(*, timeout: float, user_agent: str) -> ScraperRegistry:
    scrapers: List[BaseScraper] = [
        ComplexShopScraper(timeout=timeout, user_agent=user_agent),
        UniversalStoreScraper(timeout=timeout, user_agent=user_agent),
        GoatScraper(timeout=timeout, user_agent=user_agent),
    ]
    return ScraperRegistry(scrapers)
