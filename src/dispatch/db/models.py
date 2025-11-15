"""Database models for Dispatch."""
from __future__ import annotations

from datetime import datetime
from typing import Any

from sqlalchemy import JSON, Column, DateTime, Float, Integer, String, Text, UniqueConstraint

from .session import Base


class ProductRecord(Base):
    """SQLAlchemy representation of a scraped product."""

    __tablename__ = "products"
    __table_args__ = (UniqueConstraint("provider", "url", name="uq_provider_url"),)

    id = Column(Integer, primary_key=True)
    provider = Column(String(50), nullable=False)
    name = Column(String(255), nullable=False)
    url = Column(String(512), nullable=False)
    price = Column(Float, nullable=True)
    currency = Column(String(16), nullable=True)
    images = Column(JSON, nullable=False, default=list)
    description = Column(Text, nullable=True)
    brand = Column(String(255), nullable=True)
    categories = Column(JSON, nullable=False, default=list)
    attributes = Column(JSON, nullable=False, default=dict)
    last_seen = Column(DateTime, default=datetime.utcnow, nullable=False)

    def update_from_dict(self, data: dict[str, Any]) -> None:
        """Update the product record from a plain dictionary."""

        for key, value in data.items():
            setattr(self, key, value)
