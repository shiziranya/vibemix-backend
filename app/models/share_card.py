from __future__ import annotations

import uuid
from datetime import datetime, timezone
from typing import Optional

from sqlalchemy import DateTime, Integer, String, Text
from sqlalchemy.dialects.postgresql import JSON, UUID
from sqlalchemy.orm import Mapped, mapped_column

from ..extensions import db


class ShareCard(db.Model):
    __tablename__ = "share_cards"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    user_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        db.ForeignKey("users.id", ondelete="CASCADE"),
        nullable=False,
    )
    cocktail_id: Mapped[Optional[int]] = mapped_column(
        Integer, db.ForeignKey("cocktails.id")
    )
    session_id: Mapped[Optional[str]] = mapped_column(String(64))
    layout: Mapped[str] = mapped_column(String(20), nullable=False)
    # 模板 ID，来自 card_templates.TEMPLATES
    template_id: Mapped[Optional[str]] = mapped_column(String(64))
    # 用户拖拽后的文字层位置覆盖：{layer_id: {x: float, y: float}}
    text_overrides: Mapped[Optional[dict]] = mapped_column(JSON)
    user_photo_url: Mapped[Optional[str]] = mapped_column(Text)
    image_url: Mapped[Optional[str]] = mapped_column(Text)
    mood_caption: Mapped[Optional[str]] = mapped_column(Text)
    status: Mapped[str] = mapped_column(String(20), default="pending")
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=lambda: datetime.now(timezone.utc)
    )

    def to_dict(self):
        return {
            "card_id": str(self.id),
            "cocktail_id": self.cocktail_id,
            "session_id": self.session_id,
            "layout": self.layout,
            "template_id": self.template_id,
            "text_overrides": self.text_overrides or {},
            "user_photo_url": self.user_photo_url,
            "image_url": self.image_url,
            "mood_caption": self.mood_caption,
            "status": self.status,
            "created_at": self.created_at.isoformat() if self.created_at else None,
        }
