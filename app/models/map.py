from __future__ import annotations

import uuid
from datetime import datetime, timezone
from decimal import Decimal
from typing import Optional

from sqlalchemy import (
    Boolean, CheckConstraint, DateTime, Integer,
    Numeric, SmallInteger, String, Text, UniqueConstraint,
)
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column

from ..extensions import db


class MapTheme(db.Model):
    __tablename__ = "map_themes"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    slug: Mapped[str] = mapped_column(String(50), unique=True, nullable=False)
    name: Mapped[str] = mapped_column(String(100), nullable=False)
    name_zh: Mapped[str] = mapped_column(String(100), nullable=False)
    description_zh: Mapped[Optional[str]] = mapped_column(Text)
    icon_url: Mapped[Optional[str]] = mapped_column(Text)
    cover_url: Mapped[Optional[str]] = mapped_column(Text)
    color_primary: Mapped[Optional[str]] = mapped_column(String(20))
    color_secondary: Mapped[Optional[str]] = mapped_column(String(20))
    sort_order: Mapped[int] = mapped_column(SmallInteger, nullable=False, default=0)
    is_active: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)
    portal_cocktail_id: Mapped[Optional[int]] = mapped_column(
        Integer, db.ForeignKey("cocktails.id"), nullable=True
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=lambda: datetime.now(timezone.utc)
    )

    def to_dict(self) -> dict:
        return {
            "id": self.id,
            "slug": self.slug,
            "name": self.name,
            "name_zh": self.name_zh,
            "description_zh": self.description_zh,
            "icon_url": self.icon_url,
            "cover_url": self.cover_url,
            "color_primary": self.color_primary,
            "color_secondary": self.color_secondary,
            "sort_order": self.sort_order,
            "portal_cocktail_id": self.portal_cocktail_id,
        }


class MapNode(db.Model):
    __tablename__ = "map_nodes"
    __table_args__ = (
        UniqueConstraint("cocktail_id", "theme_id"),
        CheckConstraint(
            "path_role IN ('main', 'side')",
            name="map_nodes_path_role_check",
        ),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    theme_id: Mapped[Optional[int]] = mapped_column(
        Integer, db.ForeignKey("map_themes.id", ondelete="CASCADE")
    )
    cocktail_id: Mapped[int] = mapped_column(
        Integer, db.ForeignKey("cocktails.id"), nullable=False
    )
    node_key: Mapped[Optional[str]] = mapped_column(String(100))
    is_entry_node: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    is_boss: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    reward_xp: Mapped[int] = mapped_column(SmallInteger, nullable=False, default=10)
    sort_order: Mapped[int] = mapped_column(SmallInteger, nullable=False, default=0)
    pos_x: Mapped[Optional[Decimal]] = mapped_column(Numeric(8, 2))
    pos_y: Mapped[Optional[Decimal]] = mapped_column(Numeric(8, 2))
    path_role: Mapped[str] = mapped_column(String(10), nullable=False, default="main")
    unlock_by: Mapped[Optional[int]] = mapped_column(
        Integer, db.ForeignKey("cocktails.id"), nullable=True
    )

    def to_dict(self) -> dict:
        return {
            "id": self.id,
            "theme_id": self.theme_id,
            "cocktail_id": self.cocktail_id,
            "node_key": self.node_key,
            "is_entry_node": self.is_entry_node,
            "is_boss": self.is_boss,
            "reward_xp": self.reward_xp,
            "sort_order": self.sort_order,
            "pos_x": float(self.pos_x) if self.pos_x is not None else None,
            "pos_y": float(self.pos_y) if self.pos_y is not None else None,
            "path_role": self.path_role,
            "unlock_by": self.unlock_by,
        }


class MapEdge(db.Model):
    __tablename__ = "map_edges"
    __table_args__ = (
        UniqueConstraint("from_node_id", "to_node_id"),
        CheckConstraint("from_node_id <> to_node_id", name="no_self_loop"),
        CheckConstraint(
            "edge_type IN ('progression', 'association', 'prerequisite', 'archetype_bridge', 'variant')",
            name="map_edges_edge_type_check",
        ),
        CheckConstraint(
            "path_role IN ('main', 'side')",
            name="map_edges_path_role_check",
        ),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    from_node_id: Mapped[int] = mapped_column(
        Integer, db.ForeignKey("map_nodes.id", ondelete="CASCADE"), nullable=False
    )
    to_node_id: Mapped[int] = mapped_column(
        Integer, db.ForeignKey("map_nodes.id", ondelete="CASCADE"), nullable=False
    )
    edge_type: Mapped[str] = mapped_column(
        String(20), nullable=False, default="progression"
    )
    edge_label: Mapped[Optional[str]] = mapped_column(String(20))
    path_role: Mapped[str] = mapped_column(String(10), nullable=False, default="main")

    def to_dict(self) -> dict:
        return {
            "from_node_id": self.from_node_id,
            "to_node_id": self.to_node_id,
            "edge_type": self.edge_type,
            "edge_label": self.edge_label,
            "path_role": self.path_role,
        }


class UserMapProgress(db.Model):
    __tablename__ = "user_map_progress"
    __table_args__ = (UniqueConstraint("user_id", "node_id"),)

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    user_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), db.ForeignKey("users.id", ondelete="CASCADE"), nullable=False
    )
    node_id: Mapped[int] = mapped_column(
        Integer, db.ForeignKey("map_nodes.id", ondelete="CASCADE"), nullable=False
    )
    unlocked_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True))
    completed_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True))


class UserThemeProgress(db.Model):
    __tablename__ = "user_theme_progress"

    user_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        db.ForeignKey("users.id", ondelete="CASCADE"),
        primary_key=True,
    )
    theme_id: Mapped[int] = mapped_column(
        Integer, db.ForeignKey("map_themes.id", ondelete="CASCADE"),
        primary_key=True,
    )
    nodes_completed: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    nodes_total: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    last_activity_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True))
