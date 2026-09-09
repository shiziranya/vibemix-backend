from __future__ import annotations

import uuid
from datetime import datetime, timezone
from typing import Dict, List, Optional

from sqlalchemy import DateTime, Integer, String, Text
from sqlalchemy.dialects.postgresql import ARRAY, JSONB, UUID
from sqlalchemy.orm import Mapped, mapped_column

from ..extensions import db


class RecommendationHistory(db.Model):
    __tablename__ = "recommendation_history"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    user_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        db.ForeignKey("users.id", ondelete="CASCADE"),
        nullable=False,
    )
    session_id: Mapped[str] = mapped_column(String(64), nullable=False)
    cocktail_id: Mapped[Optional[int]] = mapped_column(
        Integer, db.ForeignKey("cocktails.id")
    )
    mood_tags: Mapped[Optional[List[str]]] = mapped_column(ARRAY(Text))
    abv_pref: Mapped[Optional[str]] = mapped_column(String(10))
    flavor_tags: Mapped[Optional[List[str]]] = mapped_column(ARRAY(Text))
    recipe_type: Mapped[Optional[str]] = mapped_column(String(20))
    category: Mapped[Optional[str]] = mapped_column(String(20))
    free_text: Mapped[Optional[str]] = mapped_column(Text)
    cocktail_name: Mapped[Optional[str]] = mapped_column(String(200))
    cocktail_name_zh: Mapped[Optional[str]] = mapped_column(String(200))
    prototype_name: Mapped[Optional[str]] = mapped_column(String(200))
    prototype_name_zh: Mapped[Optional[str]] = mapped_column(String(200))
    ai_reason: Mapped[Optional[str]] = mapped_column(Text)
    ai_poetic: Mapped[Optional[str]] = mapped_column(Text)
    ai_mood_caption: Mapped[Optional[str]] = mapped_column(Text)
    ai_tweaks: Mapped[Optional[Dict]] = mapped_column(JSONB)
    ai_ingredients: Mapped[Optional[List[Dict]]] = mapped_column(JSONB)
    ai_steps: Mapped[Optional[List[Dict]]] = mapped_column(JSONB)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=lambda: datetime.now(timezone.utc)
    )

    def to_dict(self):
        return {
            "id": self.id,
            "session_id": self.session_id,
            "cocktail_id": self.cocktail_id,
            "mood_tags": self.mood_tags or [],
            "abv_pref": self.abv_pref,
            "flavor_tags": self.flavor_tags or [],
            "recipe_type": self.recipe_type,
            "category": self.category,
            "free_text": self.free_text,
            "cocktail_name": self.cocktail_name,
            "cocktail_name_zh": self.cocktail_name_zh,
            "prototype_name": self.prototype_name,
            "prototype_name_zh": self.prototype_name_zh,
            "ai_reason": self.ai_reason,
            "ai_poetic": self.ai_poetic,
            "ai_mood_caption": self.ai_mood_caption,
            "ai_tweaks": self.ai_tweaks,
            "ai_ingredients": self.ai_ingredients or [],
            "ai_steps": self.ai_steps or [],
            "created_at": self.created_at.isoformat() if self.created_at else None,
        }
