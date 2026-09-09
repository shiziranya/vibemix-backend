from __future__ import annotations

import uuid
from datetime import date, datetime, timezone
from typing import Optional

from sqlalchemy import Boolean, Date, DateTime, Integer, SmallInteger, String, Text, UniqueConstraint
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column

from ..extensions import db


class UserSavedCocktail(db.Model):
    """用户收藏的鸡尾酒（收藏夹 + 今日酒单）"""
    __tablename__ = "user_saved_cocktails"
    __table_args__ = (
        UniqueConstraint("user_id", "cocktail_id", name="uq_user_cocktail"),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    user_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        db.ForeignKey("users.id", ondelete="CASCADE"),
        nullable=False,
    )
    cocktail_id: Mapped[int] = mapped_column(
        Integer,
        db.ForeignKey("cocktails.id", ondelete="CASCADE"),
        nullable=False,
    )
    
    # 关联推荐记录（如果来自LLM推荐）
    recommendation_id: Mapped[Optional[int]] = mapped_column(
        Integer,
        db.ForeignKey("recommendation_history.id", ondelete="SET NULL"),
        nullable=True,
    )

    # 今日酒单标记
    # 如果 is_in_today=True，表示在今日酒单中
    # plan_date 记录是哪天的计划（用于自动清理）
    is_in_today: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    plan_date: Mapped[Optional[date]] = mapped_column(Date, nullable=True)

    # 优先级排序（用于今日酒单排序）
    priority: Mapped[int] = mapped_column(SmallInteger, default=0, nullable=False)

    # 个人笔记
    personal_note: Mapped[Optional[str]] = mapped_column(Text, nullable=True)

    # 时间记录
    added_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=lambda: datetime.now(timezone.utc),
        nullable=False,
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=lambda: datetime.now(timezone.utc),
        onupdate=lambda: datetime.now(timezone.utc),
        nullable=False,
    )

    def to_dict(self):
        return {
            "id": self.id,
            "cocktail_id": self.cocktail_id,
            "recommendation_id": self.recommendation_id,
            "is_in_today": self.is_in_today,
            "plan_date": self.plan_date.isoformat() if self.plan_date else None,
            "priority": self.priority,
            "personal_note": self.personal_note,
            "added_at": self.added_at.isoformat() if self.added_at else None,
            "updated_at": self.updated_at.isoformat() if self.updated_at else None,
        }
