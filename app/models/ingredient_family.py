from __future__ import annotations

from datetime import datetime, timezone
from decimal import Decimal
from typing import Optional

from sqlalchemy import Boolean, DateTime, Integer, Numeric, String, Text
from sqlalchemy.orm import Mapped, mapped_column

from ..extensions import db


class IngredientFamily(db.Model):
    __tablename__ = "ingredient_family"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    name: Mapped[str] = mapped_column(String(60), nullable=False)
    name_normalized: Mapped[str] = mapped_column(String(80), unique=True, nullable=False)
    name_zh: Mapped[Optional[str]] = mapped_column(String(60))
    category: Mapped[Optional[str]] = mapped_column(String(50))
    description: Mapped[Optional[str]] = mapped_column(Text)
    is_base_spirit: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    is_easily_available: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    abv_approx: Mapped[Optional[Decimal]] = mapped_column(Numeric(5, 2))
    base_spirit_family: Mapped[Optional[str]] = mapped_column(String(40))
    image_url: Mapped[Optional[str]] = mapped_column(String(255))
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=lambda: datetime.now(timezone.utc)
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=lambda: datetime.now(timezone.utc),
        onupdate=lambda: datetime.now(timezone.utc),
    )

    def to_dict(self, in_cabinet: bool = False) -> dict:
        return {
            "id": self.id,
            "name": self.name,
            "name_zh": self.name_zh or self.name,
            "category": self.category,
            "is_base_spirit": self.is_base_spirit,
            "is_easily_available": self.is_easily_available,
            "base_spirit_family": self.base_spirit_family,
            "abv_approx": float(self.abv_approx) if self.abv_approx else None,
            "description": self.description,
            "in_cabinet": in_cabinet,
            "image_url": self.image_url,
        }
