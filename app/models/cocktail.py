from __future__ import annotations

from datetime import datetime, timezone
from decimal import Decimal
from typing import List, Optional

from sqlalchemy import Boolean, DateTime, Integer, Numeric, SmallInteger, String, Text
from sqlalchemy.dialects.postgresql import ARRAY
from sqlalchemy.orm import Mapped, mapped_column

from ..extensions import db


class Cocktail(db.Model):
    __tablename__ = "cocktails"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    external_id: Mapped[str] = mapped_column(String(64), unique=True, nullable=False)
    name: Mapped[str] = mapped_column(String(200), nullable=False)
    name_alternate: Mapped[Optional[str]] = mapped_column(String(200))
    name_zh: Mapped[Optional[str]] = mapped_column(String(200))
    category: Mapped[Optional[str]] = mapped_column(String(100))
    iba_category: Mapped[Optional[str]] = mapped_column(String(100))
    is_alcoholic: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)
    glass_type: Mapped[Optional[str]] = mapped_column(String(100))
    tags: Mapped[Optional[List[str]]] = mapped_column(ARRAY(Text))
    instructions_en: Mapped[Optional[str]] = mapped_column(Text)
    instructions_zh: Mapped[Optional[str]] = mapped_column(Text)
    image_url: Mapped[Optional[str]] = mapped_column(Text)
    image_source: Mapped[Optional[str]] = mapped_column(Text)
    image_attribution: Mapped[Optional[str]] = mapped_column(Text)
    video_url: Mapped[Optional[str]] = mapped_column(Text)

    # Recommendation fields (added via migration)
    base_spirit_ids: Mapped[Optional[List[int]]] = mapped_column(ARRAY(Integer))
    non_available_ingredient_count: Mapped[int] = mapped_column(Integer, default=0)
    mood_tags: Mapped[Optional[List[str]]] = mapped_column(ARRAY(Text), default=list)
    flavor_tags: Mapped[Optional[List[str]]] = mapped_column(ARRAY(Text), default=list)
    abv_level: Mapped[Optional[str]] = mapped_column(String(10), default="medium")
    difficulty: Mapped[Optional[int]] = mapped_column(SmallInteger, default=2)

    date_modified: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True))
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=lambda: datetime.now(timezone.utc)
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=lambda: datetime.now(timezone.utc),
        onupdate=lambda: datetime.now(timezone.utc),
    )

    def to_summary(self):
        return {
            "id": self.id,
            "name": self.name,
            "name_zh": self.name_zh or self.name,
            "abv_level": self.abv_level,
            "difficulty": self.difficulty,
            "image_url": self.image_url,
            "mood_tags": self.mood_tags or [],
            "flavor_tags": self.flavor_tags or [],
            "glass_type": self.glass_type,
        }

    def to_dict(self):
        return {
            **self.to_summary(),
            "category": self.category,
            "iba_category": self.iba_category,
            "is_alcoholic": self.is_alcoholic,
            "instructions_zh": self.instructions_zh,
            "instructions_en": self.instructions_en,
            "tags": self.tags or [],
        }


class CocktailIngredient(db.Model):
    __tablename__ = "cocktail_ingredients"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    cocktail_id: Mapped[int] = mapped_column(
        Integer, db.ForeignKey("cocktails.id", ondelete="CASCADE"), nullable=False
    )
    ingredient_id: Mapped[int] = mapped_column(
        Integer, db.ForeignKey("ingredients.id"), nullable=False
    )
    measure_raw: Mapped[Optional[str]] = mapped_column(String(100))
    measure_ml: Mapped[Optional[Decimal]] = mapped_column(Numeric(7, 2))
    sort_order: Mapped[int] = mapped_column(SmallInteger, nullable=False, default=0)
