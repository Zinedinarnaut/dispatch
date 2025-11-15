"""Scraper for GOAT."""
from __future__ import annotations

from typing import Iterable, List, Optional

from ...core.http import get_async_client
from ...telemetry.events import TelemetryEvent, telemetry_client
from ..base import BaseScraper, Product


class GoatScraper(BaseScraper):
    provider = "goat"
    base_url = "https://www.goat.com"
    search_endpoint = "https://www.goat.com/web-api/v2/search"

    async def fetch_products(self, *, query: Optional[str] = None, limit: Optional[int] = None) -> Iterable[Product]:
        params = {
            "query": query or "",
            "productType": "sneakers",
            "perPage": 80,
        }
        async with get_async_client() as client:
            response = await client.get(self.search_endpoint, params=params, headers={"Accept": "application/json"})
            response.raise_for_status()
            payload = response.json()
        products = self._parse_products(payload)
        await telemetry_client.record(
            TelemetryEvent(
                name="scraper.fetch",
                attributes={"provider": self.provider, "count": len(products), "query": query or ""},
            )
        )
        return await self._limit(products, limit)

    def _parse_products(self, payload: dict) -> List[Product]:
        items: List[Product] = []
        hits = payload.get("hits", [])
        for hit in hits:
            product = hit.get("_source", {})
            name = product.get("name") or product.get("slug", "")
            url = f"{self.base_url}/sneakers/{product.get('slug')}" if product.get("slug") else self.base_url
            price_cents = product.get("lowest_price_cents")
            price = price_cents / 100 if price_cents else None
            images = []
            if product.get("grid_default_image"):
                images.append(product["grid_default_image"])
            categories = product.get("category_traits") or []
            brand = product.get("brand_name")
            items.append(
                Product(
                    provider=self.provider,
                    name=name,
                    url=url,
                    price=price,
                    currency="USD",
                    images=images,
                    brand=brand,
                    categories=categories,
                    metadata={
                        "color": product.get("color"),
                        "silhouette": product.get("silhouette"),
                        "release_date": product.get("release_date"),
                    },
                )
            )
        return items
