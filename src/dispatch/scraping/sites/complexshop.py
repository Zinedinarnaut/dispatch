"""Scraper for Complex Shop."""
from __future__ import annotations

from decimal import Decimal
from typing import Iterable, List, Optional
from urllib.parse import urlencode, urljoin

from bs4 import BeautifulSoup

from ...core.http import get_async_client
from ...telemetry.events import TelemetryEvent, telemetry_client
from ..base import BaseScraper, Product


class ComplexShopScraper(BaseScraper):
    provider = "complexshop"
    base_url = "https://shop.complex.com"

    async def fetch_products(self, *, query: Optional[str] = None, limit: Optional[int] = None) -> Iterable[Product]:
        params = {"sort_by": "best-selling"}
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
        for card in soup.select("div.grid-product__content"):
            title_elem = card.select_one("div.grid-product__title")
            if not title_elem:
                continue
            name = title_elem.get_text(strip=True)
            url_path = card.find("a", class_="grid-product__link")
            url = urljoin(self.base_url, url_path.get("href")) if url_path else self.base_url
            price_elem = card.select_one("span.grid-product__price--current")
            price, currency = self._parse_price(price_elem)
            image_elem = card.find("img")
            image_url = urljoin(self.base_url, image_elem.get("data-src")) if image_elem else None
            items.append(
                Product(
                    provider=self.provider,
                    name=name,
                    url=url,
                    price=price,
                    currency=currency,
                    images=[image_url] if image_url else [],
                    metadata={"raw_price": price_elem.get_text(strip=True) if price_elem else None},
                )
            )
        return items

    def _parse_price(self, price_elem) -> tuple[Optional[float], Optional[str]]:
        if not price_elem:
            return None, None
        raw = price_elem.get_text(strip=True).replace(",", "")
        currency = None
        digits = ""
        for char in raw:
            if char.isdigit() or char == ".":
                digits += char
            elif not currency and char.isalpha():
                currency = "USD"
        price = float(Decimal(digits)) if digits else None
        return price, currency
