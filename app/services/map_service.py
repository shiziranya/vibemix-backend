from __future__ import annotations

"""
星图探索 - 服务层

核心逻辑：
  - 查询主题列表，附带用户进度
  - 查询主题节点图（含节点状态：locked / available / unlocked / completed）
  - 完成节点
  - 获取节点需要的基酒明细（用于引导购买）
  - 批量更新节点 pos_x / pos_y（编辑器用）
"""

import json
import uuid
from datetime import datetime, timezone
from typing import Any

from sqlalchemy import text

from ..extensions import db, get_redis

# ── Redis key helpers ────────────────────────────────────────────────────────

def _cache_key_theme_graph(theme_id: int, user_id: str) -> str:
    return f"map:graph:{theme_id}:{user_id}"

def _cache_key_themes(user_id: str) -> str:
    return f"map:themes:{user_id}"

CACHE_TTL = 300  # 5 minutes


# ── 节点状态计算 SQL ─────────────────────────────────────────────────────────

_NODE_STATUS_SQL = """
WITH
-- 用户已完成的节点
user_completed AS (
    SELECT node_id
    FROM user_map_progress
    WHERE user_id = :user_id AND completed_at IS NOT NULL
),
-- 用户拥有的基酒（ingredient_family slug）
user_spirits AS (
    SELECT ig.slug
    FROM user_cabinet uc
    JOIN ingredients i ON i.id = uc.ingredient_id
    JOIN ingredient_families ig ON ig.id = i.family_id
    WHERE uc.user_id = :user_id
),
-- 主题节点
theme_nodes AS (
    SELECT mn.id, mn.cocktail_id, mn.is_entry_node, mn.base_spirits
    FROM map_nodes mn
    WHERE mn.theme_id = :theme_id
),
-- 每个节点「主题内 progression 前置节点」是否全部完成
prereqs_met AS (
    SELECT
        e.to_node_id,
        BOOL_AND(uc2.node_id IS NOT NULL) AS all_done
    FROM map_edges e
    JOIN map_nodes src ON src.id = e.from_node_id AND src.theme_id = :theme_id
    JOIN map_nodes dst ON dst.id = e.to_node_id   AND dst.theme_id = :theme_id
    LEFT JOIN user_completed uc2 ON uc2.node_id = e.from_node_id
    WHERE e.edge_type = 'progression'
    GROUP BY e.to_node_id
),
-- 每个节点所需基酒是否全部拥有
spirits_met AS (
    SELECT
        mn.id AS node_id,
        CASE
            WHEN array_length(mn.base_spirits, 1) IS NULL THEN TRUE
            WHEN mn.base_spirits = '{}' THEN TRUE
            ELSE (
                SELECT COUNT(*) = array_length(mn.base_spirits, 1)
                FROM unnest(mn.base_spirits) AS bs
                WHERE bs IN (SELECT slug FROM user_spirits)
            )
        END AS has_all_spirits
    FROM theme_nodes mn
),
-- 汇总：拥有的、缺少的基酒数量
spirits_summary AS (
    SELECT
        mn.id AS node_id,
        (
            SELECT COUNT(*) FROM unnest(mn.base_spirits) AS bs
            WHERE bs IN (SELECT slug FROM user_spirits)
        )::int AS owned_spirit_count,
        (
            SELECT COUNT(*) FROM unnest(mn.base_spirits) AS bs
            WHERE bs NOT IN (SELECT slug FROM user_spirits)
        )::int AS missing_spirit_count
    FROM theme_nodes mn
)
SELECT
    mn.id,
    mn.node_key,
    mn.display_name_zh,
    mn.cocktail_id,
    mn.is_entry_node,
    mn.is_boss,
    mn.complexity,
    mn.base_spirits,
    mn.reward_xp,
    mn.sort_order,
    mn.pos_x,
    mn.pos_y,
    CASE
        WHEN uc.node_id IS NOT NULL THEN 'completed'
        WHEN (mn.is_entry_node OR COALESCE(pm.all_done, FALSE))
             AND sm.has_all_spirits THEN 'available'
        WHEN (mn.is_entry_node OR COALESCE(pm.all_done, FALSE))
             AND NOT sm.has_all_spirits THEN 'available'
        ELSE 'locked'
    END AS status,
    sm.has_all_spirits,
    ss.owned_spirit_count,
    ss.missing_spirit_count
FROM theme_nodes mn
LEFT JOIN user_completed uc ON uc.node_id = mn.id
LEFT JOIN prereqs_met pm ON pm.to_node_id = mn.id
JOIN spirits_met sm ON sm.node_id = mn.id
JOIN spirits_summary ss ON ss.node_id = mn.id
ORDER BY mn.sort_order, mn.id
"""

# 查询某节点需要但用户缺少的基酒详情
_MISSING_SPIRITS_SQL = """
WITH user_spirits AS (
    SELECT ig.slug
    FROM user_cabinet uc
    JOIN ingredients i ON i.id = uc.ingredient_id
    JOIN ingredient_families ig ON ig.id = i.family_id
    WHERE uc.user_id = :user_id
),
node_spirits AS (
    SELECT unnest(base_spirits) AS slug
    FROM map_nodes WHERE id = :node_id
)
SELECT
    ig.id,
    ig.slug,
    ig.name_zh,
    ig.name_en,
    ig.category,
    ig.abv_min,
    ig.abv_max
FROM node_spirits ns
JOIN ingredient_families ig ON ig.slug = ns.slug
WHERE ns.slug NOT IN (SELECT slug FROM user_spirits)
"""


class MapService:
    # ── 主题列表 ─────────────────────────────────────────────────────────────

    def get_themes(self, user_id: str) -> list[dict]:
        cache_key = _cache_key_themes(user_id)
        try:
            r = get_redis()
            cached = r.get(cache_key)
            if cached:
                return json.loads(cached)
        except Exception:
            pass

        rows = db.session.execute(
            text("""
                SELECT
                    t.id, t.slug, t.name_zh, t.sort_order,
                    t.color_primary, t.icon_url, t.portal_cocktail_id,
                    COUNT(mn.id) AS node_total,
                    COUNT(ump.node_id) AS node_completed
                FROM map_themes t
                LEFT JOIN map_nodes mn ON mn.theme_id = t.id
                LEFT JOIN user_map_progress ump
                    ON ump.node_id = mn.id
                    AND ump.user_id = :uid
                    AND ump.completed_at IS NOT NULL
                WHERE t.is_active
                GROUP BY t.id
                ORDER BY t.sort_order
            """),
            {"uid": user_id},
        ).fetchall()

        result = [
            {
                "id": r.id,
                "slug": r.slug,
                "name_zh": r.name_zh,
                "sort_order": r.sort_order,
                "color_primary": r.color_primary,
                "icon_url": r.icon_url,
                "portal_cocktail_id": r.portal_cocktail_id,
                "node_total": r.node_total,
                "node_completed": r.node_completed,
            }
            for r in rows
        ]

        try:
            r = get_redis()
            r.setex(cache_key, CACHE_TTL, json.dumps(result))
        except Exception:
            pass

        return result

    # ── 主题图谱（含状态）────────────────────────────────────────────────────

    def get_theme_graph(self, theme_id: int, user_id: str) -> dict:
        cache_key = _cache_key_theme_graph(theme_id, user_id)
        try:
            r = get_redis()
            cached = r.get(cache_key)
            if cached:
                return json.loads(cached)
        except Exception:
            pass

        # 主题信息
        theme_row = db.session.execute(
            text("SELECT id,slug,name_zh,color_primary,color_secondary,portal_cocktail_id FROM map_themes WHERE id=:tid"),
            {"tid": theme_id},
        ).fetchone()
        if not theme_row:
            return {}

        # 节点（含状态）
        node_rows = db.session.execute(
            text(_NODE_STATUS_SQL),
            {"theme_id": theme_id, "user_id": user_id},
        ).fetchall()

        nodes = [
            {
                "id": row.id,
                "node_key": row.node_key,
                "display_name_zh": row.display_name_zh,
                "cocktail_id": row.cocktail_id,
                "is_entry_node": row.is_entry_node,
                "is_boss": row.is_boss,
                "complexity": row.complexity,
                "base_spirits": row.base_spirits or [],
                "reward_xp": row.reward_xp,
                "sort_order": row.sort_order,
                "pos_x": float(row.pos_x) if row.pos_x is not None else None,
                "pos_y": float(row.pos_y) if row.pos_y is not None else None,
                "status": row.status,
                "has_all_spirits": row.has_all_spirits,
                "owned_spirit_count": row.owned_spirit_count,
                "missing_spirit_count": row.missing_spirit_count,
            }
            for row in node_rows
        ]

        # 边（分类返回）
        edge_rows = db.session.execute(
            text("""
                SELECT e.from_node_id, e.to_node_id, e.edge_type, e.edge_label
                FROM map_edges e
                JOIN map_nodes a ON a.id = e.from_node_id AND a.theme_id = :tid
                JOIN map_nodes b ON b.id = e.to_node_id   AND b.theme_id = :tid
                ORDER BY e.edge_type, e.from_node_id
            """),
            {"tid": theme_id},
        ).fetchall()

        prog_edges  = [{"from": r.from_node_id, "to": r.to_node_id} for r in edge_rows if r.edge_type == "progression"]
        assoc_edges = [{"from": r.from_node_id, "to": r.to_node_id, "label": r.edge_label} for r in edge_rows if r.edge_type == "association"]

        result = {
            "theme": {
                "id": theme_row.id,
                "slug": theme_row.slug,
                "name_zh": theme_row.name_zh,
                "color_primary": theme_row.color_primary,
                "color_secondary": theme_row.color_secondary,
                "portal_cocktail_id": theme_row.portal_cocktail_id,
            },
            "nodes": nodes,
            "progression_edges": prog_edges,
            "association_edges": assoc_edges,
        }

        try:
            r = get_redis()
            r.setex(cache_key, CACHE_TTL, json.dumps(result))
        except Exception:
            pass

        return result

    # ── 完成节点 ─────────────────────────────────────────────────────────────

    def complete_node(self, node_id: int, user_id: str) -> dict:
        from ..models.map import MapNode, UserMapProgress

        node = db.session.get(MapNode, node_id)
        if not node:
            raise ValueError(f"节点 {node_id} 不存在")

        now = datetime.now(timezone.utc)

        progress = db.session.execute(
            text("SELECT id, unlocked_at, completed_at FROM user_map_progress WHERE user_id=:uid AND node_id=:nid"),
            {"uid": user_id, "nid": node_id},
        ).fetchone()

        if progress:
            db.session.execute(
                text("UPDATE user_map_progress SET completed_at=:now WHERE user_id=:uid AND node_id=:nid"),
                {"now": now, "uid": user_id, "nid": node_id},
            )
        else:
            db.session.execute(
                text("INSERT INTO user_map_progress (user_id, node_id, unlocked_at, completed_at) VALUES (:uid,:nid,:now,:now)"),
                {"uid": user_id, "nid": node_id, "now": now},
            )

        db.session.commit()

        # 清缓存
        try:
            r = get_redis()
            r.delete(_cache_key_theme_graph(node.theme_id, user_id))
            r.delete(_cache_key_themes(user_id))
        except Exception:
            pass

        return {"node_id": node_id, "reward_xp": node.reward_xp}

    # ── 缺少的基酒 ───────────────────────────────────────────────────────────

    def get_missing_spirits(self, node_id: int, user_id: str) -> list[dict]:
        rows = db.session.execute(
            text(_MISSING_SPIRITS_SQL),
            {"node_id": node_id, "user_id": user_id},
        ).fetchall()
        return [
            {
                "id": r.id,
                "slug": r.slug,
                "name_zh": r.name_zh,
                "name_en": r.name_en,
                "category": r.category,
            }
            for r in rows
        ]

    # ── 批量更新节点位置（编辑器用）─────────────────────────────────────────

    def batch_update_positions(self, updates: list[dict]) -> int:
        count = 0
        for item in updates:
            node_id = item.get("node_id")
            pos_x   = item.get("pos_x")
            pos_y   = item.get("pos_y")
            if node_id is None:
                continue
            db.session.execute(
                text("UPDATE map_nodes SET pos_x=:x, pos_y=:y WHERE id=:id"),
                {"x": pos_x, "y": pos_y, "id": node_id},
            )
            count += 1
        db.session.commit()

        # 清所有 graph 缓存（管理员操作，直接清除）
        try:
            r = get_redis()
            for key in r.scan_iter("map:graph:*"):
                r.delete(key)
        except Exception:
            pass

        return count

    # ── 用户统计 ─────────────────────────────────────────────────────────────

    def get_user_stats(self, user_id: str) -> dict:
        rows = db.session.execute(
            text("""
                SELECT
                    t.id AS theme_id, t.name_zh,
                    COUNT(mn.id)   AS total,
                    COUNT(ump.node_id) FILTER (WHERE ump.completed_at IS NOT NULL) AS completed,
                    COUNT(ump.node_id) FILTER (WHERE ump.unlocked_at IS NOT NULL AND ump.completed_at IS NULL) AS unlocked
                FROM map_themes t
                JOIN map_nodes mn ON mn.theme_id = t.id
                LEFT JOIN user_map_progress ump
                    ON ump.node_id = mn.id AND ump.user_id = :uid
                WHERE t.is_active
                GROUP BY t.id, t.name_zh
                ORDER BY t.sort_order
            """),
            {"uid": user_id},
        ).fetchall()

        themes = [
            {
                "theme_id": r.theme_id,
                "name_zh": r.name_zh,
                "total": r.total,
                "completed": r.completed,
                "unlocked": r.unlocked,
                "progress_pct": round(r.completed / r.total * 100) if r.total else 0,
            }
            for r in rows
        ]
        total_xp = db.session.execute(
            text("""
                SELECT COALESCE(SUM(mn.reward_xp), 0)
                FROM user_map_progress ump
                JOIN map_nodes mn ON mn.id = ump.node_id
                WHERE ump.user_id = :uid AND ump.completed_at IS NOT NULL
            """),
            {"uid": user_id},
        ).scalar()

        return {"themes": themes, "total_xp": int(total_xp or 0)}


map_service = MapService()
