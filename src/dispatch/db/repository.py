"""Database repository helpers."""
from __future__ import annotations

import logging
from typing import Iterable, List, Optional

from sqlalchemy import select
from sqlalchemy.orm import Session

from ..scraping.base import Product
from .models import ProductRecord

logger = logging.getLogger("dispatch.repository")


def _product_to_dict(product: Product) -> dict:
    return {
        "provider": product.provider,
        "name": product.name,
        "url": product.url,
        "price": product.price,
        "currency": product.currency,
        "images": product.images,
        "description": product.description,
        "brand": product.brand,
        "categories": product.categories,
        "attributes": product.metadata,
        "last_seen": product.last_seen,
    }


def upsert_products(session: Session, products: Iterable[Product]) -> int:
    """Insert or update a batch of products."""

    count = 0
    for product in products:
        payload = _product_to_dict(product)
        existing = session.execute(
            select(ProductRecord).where(
                ProductRecord.provider == product.provider, ProductRecord.url == product.url
            )
        ).scalar_one_or_none()
        if existing:
            existing.update_from_dict(payload)
        else:
            session.add(ProductRecord(**payload))
        count += 1
    return count


def fetch_products(
    session: Session,
    *,
    provider: Optional[str] = None,
    limit: Optional[int] = None,
) -> List[ProductRecord]:
    """Retrieve stored products optionally filtered by provider."""

    stmt = select(ProductRecord).order_by(ProductRecord.last_seen.desc())
    if provider:
        stmt = stmt.where(ProductRecord.provider == provider)
    if limit:
        stmt = stmt.limit(limit)
    return list(session.execute(stmt).scalars().all())
