"""Scraper for Universal Store."""
from __future__ import annotations

from decimal import Decimal
from typing import Iterable, List, Optional
from urllib.parse import urlencode, urljoin

from bs4 import BeautifulSoup

from ...core.http import get_async_client
from ...telemetry.events import TelemetryEvent, telemetry_client
from ..base import BaseScraper, Product


class UniversalStoreScraper(BaseScraper):
    provider = "universalstore"
    base_url = "https://www.universalstore.com"

    async def fetch_products(self, *, query: Optional[str] = None, limit: Optional[int] = None) -> Iterable[Product]:
        params = {"sz": 48}
        path = "/collections/all"
        if query:
            path = "/search"
            params["q"] = query
        url = f"{self.base_url}{path}?{urlencode(params)}"
        async with get_async_client() as client:
            response = await client.get(url)
            response.raise_for_status()
        soup = BeautifulSoup(response.text, "html.parser")
        products = self._parse_products(soup)
        await telemetry_client.record(
            TelemetryEvent(
                name="scraper.fetch",
                attributes={"provider": self.provider, "count": len(products), "query": query or ""},
            )
        )
        return await self._limit(products, limit)

    def _parse_products(self, soup: BeautifulSoup) -> List[Product]:
        items: List[Product] = []
        for card in soup.select("article.product-grid-item"):
            title_elem = card.select_one("h3.product-grid-item__title")
            if not title_elem:
                continue
            name = title_elem.get_text(strip=True)
            anchor = card.find("a", class_="product-grid-item__link")
            url = urljoin(self.base_url, anchor.get("href")) if anchor else self.base_url
            price_elem = card.select_one("span.price")
            price, currency = self._parse_price(price_elem)
            image_elem = card.find("img")
            image_url = urljoin(self.base_url, image_elem.get("data-src")) if image_elem else None
            brand_elem = card.select_one("p.product-grid-item__brand")
            brand = brand_elem.get_text(strip=True) if brand_elem else None
            items.append(
                Product(
                    provider=self.provider,
                    name=name,
                    url=url,
                    price=price,
                    currency=currency,
                    images=[image_url] if image_url else [],
                    brand=brand,
                    metadata={"raw_price": price_elem.get_text(strip=True) if price_elem else None},
                )
            )
        return items

    def _parse_price(self, price_elem) -> tuple[Optional[float], Optional[str]]:
        if not price_elem:
            return None, None
        raw = price_elem.get_text(strip=True).replace(",", "")
        currency = "AUD" if "A$" in raw or "$" in raw else None
        digits = ""
        for char in raw:
            if char.isdigit() or char == ".":
                digits += char
        price = float(Decimal(digits)) if digits else None
        return price, currency
