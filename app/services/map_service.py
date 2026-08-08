from __future__ import annotations

"""
星图探索 - 服务层

核心逻辑：
  - 查询主题列表，附带用户进度
  - 查询主题节点图（含节点状态：locked / available / completed）
  - 完成节点
  - 获取节点需要的基酒明细（用于引导购买）
  - 批量更新节点 pos_x / pos_y（编辑器用）

数据库说明：
  - map_nodes 不再含 display_name_zh / complexity / base_spirits，
    改从 cocktails 表获取 name_zh / complexity_score / gateway_spirit / base_spirit_ids
  - map_edges 有效类型：prerequisite / progression / association / archetype_bridge / variant
    其中 prerequisite 和 progression 均用于计算「前置完成」解锁条件
  - user_cabinet 通过 family_id 关联 ingredient_family（无 slug 字段）
"""

import json
from datetime import datetime, timezone

from sqlalchemy import text

from ..extensions import db, get_redis

# ── Redis key helpers ────────────────────────────────────────────────────────

def _cache_key_theme_graph(theme_id: int, user_id: str) -> str:
    return f"map:graph:{theme_id}:{user_id}"

def _cache_key_themes(user_id: str) -> str:
    return f"map:themes:{user_id}"

CACHE_TTL = 300  # 5 minutes


# ── 节点状态计算 SQL ─────────────────────────────────────────────────────────
#
# 节点状态规则：
#   completed  → 用户已完成
#   available  → 入口节点 OR 所有 prerequisite/progression 前置节点均已完成
#                OR (支线节点 && unlock_by 对应的鸡尾酒已被用户完成)
#   locked     → 前置未满足
#
# 节点展示字段（来自 cocktails）：
#   display_name_zh  → cocktails.name_zh
#   complexity       → cocktails.complexity_score
#   gateway_spirit   → cocktails.gateway_spirit（单个基酒类别，如 'gin'）
#   image_url        → cocktails.image_url
#   path_role        → 'main' 或 'side'（主线或支线）
#   unlock_by        → 支线节点解锁所需的鸡尾酒ID

_NODE_STATUS_SQL = """
WITH
-- 用户已完成的鸡尾酒（跨主题共享：任意主题完成同款鸡尾酒均计入）
completed_cocktails AS (
    SELECT DISTINCT mn.cocktail_id
    FROM user_map_progress ump
    JOIN map_nodes mn ON mn.id = ump.node_id
    WHERE ump.user_id = :user_id AND ump.completed_at IS NOT NULL
),
-- 主题节点（含关联 cocktail 数据）
theme_nodes AS (
    SELECT
        mn.id,
        mn.cocktail_id,
        mn.node_key,
        mn.is_entry_node,
        mn.is_boss,
        mn.reward_xp,
        mn.sort_order,
        mn.pos_x,
        mn.pos_y,
        mn.path_role,
        mn.unlock_by,
        c.name_zh          AS display_name_zh,
        c.complexity_score AS complexity,
        c.gateway_spirit,
        c.image_url
    FROM map_nodes mn
    JOIN cocktails c ON c.id = mn.cocktail_id
    WHERE mn.theme_id = :theme_id
),
-- 前置节点是否全部完成（基于 cocktail_id 跨主题共享）
prereqs_met AS (
    SELECT
        e.to_node_id,
        BOOL_AND(
            mn_from.cocktail_id IN (SELECT cocktail_id FROM completed_cocktails)
        ) AS all_done
    FROM map_edges e
    JOIN map_nodes dst     ON dst.id    = e.to_node_id   AND dst.theme_id = :theme_id
    JOIN map_nodes mn_from ON mn_from.id = e.from_node_id
    WHERE e.edge_type IN ('prerequisite', 'progression')
    GROUP BY e.to_node_id
),
-- 节点完成后可解锁的子主题（跨主题前置出边）
unlocks_theme AS (
    SELECT DISTINCT ON (e.from_node_id)
        e.from_node_id,
        t.id            AS theme_id,
        t.name_zh       AS theme_name_zh,
        t.slug          AS theme_slug,
        t.color_primary AS theme_color_primary
    FROM map_edges e
    JOIN map_nodes src ON src.id = e.from_node_id AND src.theme_id = :theme_id
    JOIN map_nodes dst ON dst.id = e.to_node_id   AND dst.theme_id != :theme_id
    JOIN map_themes t  ON t.id = dst.theme_id
    WHERE e.edge_type IN ('prerequisite', 'progression')
    ORDER BY e.from_node_id, t.id
)
SELECT
    tn.id,
    tn.node_key,
    tn.display_name_zh,
    tn.cocktail_id,
    tn.is_entry_node,
    tn.is_boss,
    tn.complexity,
    tn.gateway_spirit,
    tn.image_url,
    tn.reward_xp,
    tn.sort_order,
    tn.pos_x,
    tn.pos_y,
    tn.path_role,
    tn.unlock_by,
    CASE
        WHEN tn.cocktail_id IN (SELECT cocktail_id FROM completed_cocktails) THEN 'completed'
        WHEN tn.is_entry_node OR COALESCE(pm.all_done, FALSE)                THEN 'available'
        WHEN tn.path_role = 'side' AND tn.unlock_by IS NOT NULL 
             AND tn.unlock_by IN (SELECT cocktail_id FROM completed_cocktails) THEN 'available'
        ELSE 'locked'
    END AS status,
    ut.theme_id            AS unlocks_theme_id,
    ut.theme_name_zh       AS unlocks_theme_name_zh,
    ut.theme_slug          AS unlocks_theme_slug,
    ut.theme_color_primary AS unlocks_theme_color
FROM theme_nodes tn
LEFT JOIN prereqs_met  pm ON pm.to_node_id  = tn.id
LEFT JOIN unlocks_theme ut ON ut.from_node_id = tn.id
ORDER BY tn.sort_order, tn.id
"""

# 查询某节点对应鸡尾酒需要但用户尚未拥有的基酒（ingredient_family）
# 使用 cocktails.base_spirit_ids（integer[] → ingredient_family.id）
_MISSING_SPIRITS_SQL = """
WITH node_cocktail AS (
    SELECT c.base_spirit_ids
    FROM map_nodes mn
    JOIN cocktails c ON c.id = mn.cocktail_id
    WHERE mn.id = :node_id
),
required_families AS (
    SELECT unnest(base_spirit_ids) AS family_id
    FROM node_cocktail
    WHERE base_spirit_ids IS NOT NULL
),
user_families AS (
    SELECT family_id
    FROM user_cabinet
    WHERE user_id = :user_id
)
SELECT
    igf.id,
    igf.name,
    igf.name_zh,
    igf.category,
    igf.base_spirit_family,
    igf.abv_approx
FROM required_families rf
JOIN ingredient_family igf ON igf.id = rf.family_id
WHERE rf.family_id NOT IN (SELECT family_id FROM user_families)
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

        theme_row = db.session.execute(
            text("""
                SELECT id, slug, name_zh, color_primary, color_secondary, portal_cocktail_id, cover_url
                FROM map_themes WHERE id = :tid
            """),
            {"tid": theme_id},
        ).fetchone()
        if not theme_row:
            return {}

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
                "gateway_spirit": row.gateway_spirit,
                "image_url": row.image_url,
                "reward_xp": row.reward_xp,
                "sort_order": row.sort_order,
                "pos_x": float(row.pos_x) if row.pos_x is not None else None,
                "pos_y": float(row.pos_y) if row.pos_y is not None else None,
                "status": row.status,
                "path_role": row.path_role,
                "unlock_by": row.unlock_by,
                "unlocks_theme": {
                    "id": row.unlocks_theme_id,
                    "name_zh": row.unlocks_theme_name_zh,
                    "slug": row.unlocks_theme_slug,
                    "color_primary": row.unlocks_theme_color,
                } if row.unlocks_theme_id else None,
            }
            for row in node_rows
        ]

        # 构建节点状态映射，用于计算边的解锁状态
        node_status_map = {row.id: row.status for row in node_rows}

        edge_rows = db.session.execute(
            text("""
                SELECT e.from_node_id, e.to_node_id, e.edge_type, e.edge_label, e.path_role
                FROM map_edges e
                JOIN map_nodes a ON a.id = e.from_node_id AND a.theme_id = :tid
                JOIN map_nodes b ON b.id = e.to_node_id   AND b.theme_id = :tid
                ORDER BY e.edge_type, e.from_node_id
            """),
            {"tid": theme_id},
        ).fetchall()

        # 将 prerequisite 与 progression 统一归为前置边，其余按类型分组
        # 同时为每条边添加解锁状态：根据 from 节点的状态判断
        prereq_edges   = []
        assoc_edges    = []
        variant_edges  = []
        bridge_edges   = []

        for r in edge_rows:
            # 计算边的解锁状态：from节点是available或completed时，边为unlocked
            from_status = node_status_map.get(r.from_node_id, 'locked')
            edge_status = 'unlocked' if from_status in ('available', 'completed') else 'locked'
            
            if r.edge_type in ("prerequisite", "progression"):
                prereq_edges.append({
                    "from": r.from_node_id, 
                    "to": r.to_node_id,
                    "path_role": r.path_role,
                    "status": edge_status,
                })
            elif r.edge_type == "association":
                assoc_edges.append({
                    "from": r.from_node_id, 
                    "to": r.to_node_id, 
                    "label": r.edge_label,
                    "path_role": r.path_role,
                    "status": edge_status,
                })
            elif r.edge_type == "variant":
                variant_edges.append({
                    "from": r.from_node_id, 
                    "to": r.to_node_id,
                    "path_role": r.path_role,
                    "status": edge_status,
                })
            elif r.edge_type == "archetype_bridge":
                bridge_edges.append({
                    "from": r.from_node_id, 
                    "to": r.to_node_id, 
                    "label": r.edge_label,
                    "path_role": r.path_role,
                    "status": edge_status,
                })

        result = {
            "theme": {
                "id": theme_row.id,
                "slug": theme_row.slug,
                "name_zh": theme_row.name_zh,
                "color_primary": theme_row.color_primary,
                "color_secondary": theme_row.color_secondary,
                "portal_cocktail_id": theme_row.portal_cocktail_id,
                "background_url": theme_row.cover_url,
            },
            "nodes": nodes,
            "progression_edges": prereq_edges,
            "association_edges": assoc_edges,
            "variant_edges": variant_edges,
            "archetype_bridge_edges": bridge_edges,
        }

        try:
            r = get_redis()
            r.setex(cache_key, CACHE_TTL, json.dumps(result))
        except Exception:
            pass

        return result

    # ── 节点详情 ─────────────────────────────────────────────────────────────

    def get_node_detail(self, node_id: int, user_id: str) -> dict:
        row = db.session.execute(
            text("""
                SELECT
                    mn.id, mn.theme_id, mn.cocktail_id, mn.node_key,
                    mn.is_entry_node, mn.is_boss, mn.reward_xp, mn.sort_order,
                    c.name, c.name_zh,
                    c.story_zh, c.story_hook_zh,
                    c.instructions_zh, c.preparation_steps,
                    c.image_url, c.video_url,
                    c.difficulty, c.abv_level, c.glass_type,
                    c.mood_tags, c.flavor_tags, c.cultural_icon,
                    c.cocktail_archetype, c.technique_primary,
                    c.occasion_vibe, c.gateway_spirit,
                    c.parent_cocktail_slug,
                    c.complexity_score, c.prep_time_minutes,
                    c.calories, c.carbs_g
                FROM map_nodes mn
                JOIN cocktails c ON c.id = mn.cocktail_id
                WHERE mn.id = :nid
            """),
            {"nid": node_id},
        ).fetchone()
        if not row:
            return {}

        # 配方食材（含用户是否拥有）
        ingredients = db.session.execute(
            text("""
                SELECT
                    ci.sort_order,
                    ci.measure_raw,
                    ci.measure_ml,
                    ci.measure_normalized,
                    ci.measure_value,
                    ci.measure_unit,
                    ci.measure_type,
                    i.name        AS ingredient_name,
                    i.name_zh     AS ingredient_name_zh,
                    igf.id        AS family_id,
                    igf.name_zh   AS family_name_zh,
                    igf.is_base_spirit,
                    CASE WHEN uc.family_id IS NOT NULL THEN true ELSE false END AS in_cabinet
                FROM cocktail_ingredients ci
                JOIN ingredients i ON i.id = ci.ingredient_id
                LEFT JOIN ingredient_family igf ON igf.id = ci.ingredient_family_id
                LEFT JOIN user_cabinet uc
                    ON uc.family_id = ci.ingredient_family_id
                    AND uc.user_id = :uid
                WHERE ci.cocktail_id = :cid
                ORDER BY ci.sort_order
            """),
            {"cid": row.cocktail_id, "uid": user_id},
        ).fetchall()

        # 用户缺少的材料（is_easily_available=false 且酒柜中没有，用于购买引导）
        missing_ing_rows = db.session.execute(
            text("""
                SELECT DISTINCT ON (igf.id)
                    igf.id        AS family_id,
                    igf.name,
                    COALESCE(igf.name_zh, igf.name) AS family_name_zh,
                    igf.category,
                    igf.base_spirit_family,
                    igf.is_base_spirit,
                    i.name        AS ingredient_name,
                    COALESCE(i.name_zh, i.name) AS ingredient_name_zh,
                    ci.measure_raw
                FROM cocktail_ingredients ci
                JOIN ingredients i       ON i.id  = ci.ingredient_id
                JOIN ingredient_family igf ON igf.id = ci.ingredient_family_id
                WHERE ci.cocktail_id = :cid
                  AND igf.is_easily_available = false
                  AND igf.id NOT IN (
                      SELECT family_id FROM user_cabinet WHERE user_id = :uid
                  )
                ORDER BY igf.id, igf.is_base_spirit DESC, ci.sort_order
            """),
            {"cid": row.cocktail_id, "uid": user_id},
        ).fetchall()
        missing_ingredients = [
            {
                "family_id": r.family_id,
                "name": r.ingredient_name,
                "name_zh": r.ingredient_name_zh,
                "family_name_zh": r.family_name_zh,
                "category": r.category,
                "base_spirit_family": r.base_spirit_family,
                "is_base_spirit": r.is_base_spirit or False,
                "measure_raw": r.measure_raw,
            }
            for r in missing_ing_rows
        ]

        # 检查用户是否拥有鸡尾酒所需的所有基酒（从 cocktail_ingredients 取 is_base_spirit=true 的品类）
        spirit_rows = db.session.execute(
            text("""
                SELECT DISTINCT ON (igf.id)
                    igf.id, igf.name, igf.name_zh, igf.base_spirit_family,
                    CASE WHEN uc.family_id IS NOT NULL THEN true ELSE false END AS in_cabinet
                FROM cocktail_ingredients ci
                JOIN ingredient_family igf ON igf.id = ci.ingredient_family_id
                LEFT JOIN user_cabinet uc
                    ON uc.family_id = igf.id AND uc.user_id = :uid
                WHERE ci.cocktail_id = :cid AND igf.is_base_spirit = true
                ORDER BY igf.id
            """),
            {"cid": row.cocktail_id, "uid": user_id},
        ).fetchall()
        required_spirits = [
            {
                "id": s.id,
                "name": s.name,
                "name_zh": s.name_zh,
                "base_spirit_family": s.base_spirit_family,
                "in_cabinet": s.in_cabinet,
            }
            for s in spirit_rows
        ]
        can_complete = all(s.in_cabinet for s in spirit_rows) if spirit_rows else True

        return {
            "node": {
                "id": row.id,
                "theme_id": row.theme_id,
                "cocktail_id": row.cocktail_id,
                "node_key": row.node_key,
                "is_entry_node": row.is_entry_node,
                "is_boss": row.is_boss,
                "reward_xp": row.reward_xp,
            },
            "cocktail": {
                "id": row.cocktail_id,
                "name": row.name,
                "name_zh": row.name_zh,
                # 故事与氛围
                "story_zh": row.story_zh,
                "story_hook_zh": row.story_hook_zh,
                "cultural_icon": row.cultural_icon or [],
                "occasion_vibe": row.occasion_vibe,
                # 制作
                "instructions_zh": row.instructions_zh,
                "preparation_steps": row.preparation_steps or [],
                "technique_primary": row.technique_primary,
                "cocktail_archetype": row.cocktail_archetype,
                # 展示
                "image_url": row.image_url,
                "video_url": row.video_url,
                "glass_type": row.glass_type,
                # 口味 & 难度
                "difficulty": row.difficulty,
                "abv_level": row.abv_level,
                "complexity": row.complexity_score,
                "mood_tags": row.mood_tags or [],
                "flavor_tags": row.flavor_tags or [],
                # 基酒 & 关联
                "gateway_spirit": row.gateway_spirit,
                "parent_cocktail_slug": row.parent_cocktail_slug,
                # 营养 & 时间
                "prep_time_minutes": row.prep_time_minutes,
                "calories": row.calories,
                "carbs_g": float(row.carbs_g) if row.carbs_g is not None else None,
            },
            "ingredients": [
                {
                    "sort_order": ing.sort_order,
                    "name": ing.ingredient_name,
                    "name_zh": ing.ingredient_name_zh,
                    "measure_raw": ing.measure_raw,
                    "measure_ml": float(ing.measure_ml) if ing.measure_ml else None,
                    "measure": ing.measure_normalized or ing.measure_raw or "适量",  # 优先使用规范化用量
                    "measure_value": float(ing.measure_value) if ing.measure_value else None,
                    "measure_unit": ing.measure_unit,
                    "measure_type": ing.measure_type,
                    "family_id": ing.family_id,
                    "family_name_zh": ing.family_name_zh,
                    "is_base_spirit": ing.is_base_spirit or False,
                    "in_cabinet": ing.in_cabinet,
                }
                for ing in ingredients
            ],
            "required_spirits": required_spirits,
            "can_complete": can_complete,
            "missing_ingredients": missing_ingredients,
        }

    # ── 完成节点 ─────────────────────────────────────────────────────────────

    def complete_node(self, node_id: int, user_id: str) -> dict:
        from ..models.map import MapNode

        node = db.session.get(MapNode, node_id)
        if not node:
            raise ValueError(f"节点 {node_id} 不存在")

        # 检查用户是否拥有该鸡尾酒所需的所有基酒（is_base_spirit=true 的品类）
        missing_spirits = db.session.execute(
            text("""
                SELECT DISTINCT igf.id, igf.name_zh
                FROM map_nodes mn
                JOIN cocktail_ingredients ci ON ci.cocktail_id = mn.cocktail_id
                JOIN ingredient_family igf ON igf.id = ci.ingredient_family_id
                WHERE mn.id = :nid
                  AND igf.is_base_spirit = true
                  AND igf.id NOT IN (
                      SELECT family_id FROM user_cabinet WHERE user_id = :uid
                  )
            """),
            {"nid": node_id, "uid": user_id},
        ).fetchall()
        if missing_spirits:
            names = "、".join(r.name_zh or str(r.id) for r in missing_spirits)
            raise PermissionError(f"缺少必需基酒：{names}")

        now = datetime.now(timezone.utc)

        progress = db.session.execute(
            text("SELECT id FROM user_map_progress WHERE user_id=:uid AND node_id=:nid"),
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

        try:
            r = get_redis()
            r.delete(_cache_key_theme_graph(node.theme_id, user_id))
            r.delete(_cache_key_themes(user_id))
        except Exception:
            pass

        return {"node_id": node_id, "reward_xp": node.reward_xp}

    # ── 完成节点并生成卡片 ───────────────────────────────────────────────────

    def complete_node_with_card(
        self,
        node_id: int,
        user_id: str,
        card_image: bytes,
        card_ext: str,
        card_params: dict,
    ) -> dict:
        """
        完成节点并生成分享卡片。
        
        Args:
            node_id: 节点ID
            user_id: 用户ID
            card_image: 卡片图片二进制数据（前端渲染后的PNG/JPEG）
            card_ext: 图片格式扩展名（png 或 jpg）
            card_params: 卡片参数字典，包含：
                - template_id (可选): 模板ID
                - text_overrides (可选): 文字层位置覆盖
                - user_photo_url (可选): 用户照片URL
                - mood_caption (可选): 心情描述
                
        Returns:
            包含节点完成信息和卡片信息的字典
        """
        import uuid as uuid_lib
        from ..models.map import MapNode
        from ..models.cocktail import Cocktail
        from ..models.share_card import ShareCard

        # 1. 获取节点信息
        node = db.session.get(MapNode, node_id)
        if not node:
            raise ValueError(f"节点 {node_id} 不存在")

        # 2. 检查用户是否拥有所需基酒（与 complete_node 相同的逻辑）
        missing_spirits = db.session.execute(
            text("""
                SELECT DISTINCT igf.id, igf.name_zh
                FROM map_nodes mn
                JOIN cocktail_ingredients ci ON ci.cocktail_id = mn.cocktail_id
                JOIN ingredient_family igf ON igf.id = ci.ingredient_family_id
                WHERE mn.id = :nid
                  AND igf.is_base_spirit = true
                  AND igf.id NOT IN (
                      SELECT family_id FROM user_cabinet WHERE user_id = :uid
                  )
            """),
            {"nid": node_id, "uid": user_id},
        ).fetchall()
        if missing_spirits:
            names = "、".join(r.name_zh or str(r.id) for r in missing_spirits)
            raise PermissionError(f"缺少必需基酒：{names}")

        # 3. 获取鸡尾酒信息
        cocktail = db.session.get(Cocktail, node.cocktail_id)
        if not cocktail:
            raise ValueError(f"鸡尾酒 {node.cocktail_id} 不存在")

        # 4. 上传卡片图片到存储
        card_id = uuid_lib.uuid4()
        image_url = self._upload_card_image(str(card_id), card_image, card_ext)

        # 5. 创建卡片记录
        card = ShareCard(
            id=card_id,
            user_id=uuid_lib.UUID(user_id),
            cocktail_id=node.cocktail_id,
            layout="portrait",
            template_id=card_params.get("template_id"),
            text_overrides=card_params.get("text_overrides") or {},
            user_photo_url=card_params.get("user_photo_url"),
            mood_caption=card_params.get("mood_caption", ""),
            image_url=image_url,
            status="done",
        )
        db.session.add(card)

        # 6. 完成节点
        now = datetime.now(timezone.utc)
        progress = db.session.execute(
            text("SELECT id FROM user_map_progress WHERE user_id=:uid AND node_id=:nid"),
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

        # 7. 清除缓存
        try:
            r = get_redis()
            r.delete(_cache_key_theme_graph(node.theme_id, user_id))
            r.delete(_cache_key_themes(user_id))
        except Exception:
            pass

        # 8. 返回结果
        return {
            "node_id": node_id,
            "reward_xp": node.reward_xp,
            "card": {
                "card_id": str(card_id),
                "image_url": image_url,
                "status": "done",
            },
        }

    def _upload_card_image(self, card_id: str, data: bytes, ext: str) -> str:
        """上传卡片图片到存储并返回公开URL"""
        from flask import current_app
        import os

        supabase_url = current_app.config.get("SUPABASE_URL", "")
        service_key = current_app.config.get("SUPABASE_SERVICE_KEY", "")
        bucket = current_app.config.get("SUPABASE_STORAGE_BUCKET", "vibemix")

        # 本地存储模式
        if not supabase_url or not service_key:
            static_dir = os.path.join(current_app.root_path, "static", "cards")
            os.makedirs(static_dir, exist_ok=True)
            filepath = os.path.join(static_dir, f"{card_id}.{ext}")
            with open(filepath, "wb") as f:
                f.write(data)
            base_url = current_app.config.get("BASE_URL", "").rstrip("/")
            return f"{base_url}/static/cards/{card_id}.{ext}"

        # Supabase 存储模式
        from supabase import create_client

        client = create_client(supabase_url, service_key)
        path = f"cards/{card_id}.{ext}"
        client.storage.from_(bucket).upload(
            path,
            data,
            {"content-type": f"image/{ext}", "upsert": "true"},
        )
        return client.storage.from_(bucket).get_public_url(path)

    # ── 缺少的基酒 ───────────────────────────────────────────────────────────

    def get_missing_spirits(self, node_id: int, user_id: str) -> list[dict]:
        rows = db.session.execute(
            text(_MISSING_SPIRITS_SQL),
            {"node_id": node_id, "user_id": user_id},
        ).fetchall()
        return [
            {
                "id": r.id,
                "name": r.name,
                "name_zh": r.name_zh,
                "category": r.category,
                "base_spirit_family": r.base_spirit_family,
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
                WITH
                -- 用户已完成的鸡尾酒（跨主题共享）
                completed_cocktails AS (
                    SELECT DISTINCT mn.cocktail_id
                    FROM user_map_progress ump
                    JOIN map_nodes mn ON mn.id = ump.node_id
                    WHERE ump.user_id = :uid AND ump.completed_at IS NOT NULL
                ),
                -- 主题是否已解锁：
                --   1. 无跨主题前置边 → 始终解锁（如经典基石）
                --   2. 有跨主题前置边 → 所有源头鸡尾酒均已完成则解锁
                theme_unlocked AS (
                    SELECT t.id AS theme_id,
                        CASE
                            WHEN NOT EXISTS (
                                SELECT 1 FROM map_edges e
                                JOIN map_nodes dst ON dst.id = e.to_node_id AND dst.theme_id = t.id
                                JOIN map_nodes src ON src.id = e.from_node_id AND src.theme_id != t.id
                                WHERE e.edge_type IN ('prerequisite', 'progression')
                            ) THEN true
                            WHEN NOT EXISTS (
                                SELECT 1 FROM map_edges e
                                JOIN map_nodes dst ON dst.id = e.to_node_id AND dst.theme_id = t.id
                                JOIN map_nodes src ON src.id = e.from_node_id AND src.theme_id != t.id
                                WHERE e.edge_type IN ('prerequisite', 'progression')
                                  AND src.cocktail_id NOT IN (
                                      SELECT cocktail_id FROM completed_cocktails
                                  )
                            ) THEN true
                            ELSE false
                        END AS is_unlocked
                    FROM map_themes t
                    WHERE t.is_active
                )
                SELECT
                    t.id AS theme_id,
                    t.name_zh,
                    t.cover_url,
                    COUNT(mn.id) AS total,
                    COUNT(mn.id) FILTER (
                        WHERE mn.cocktail_id IN (SELECT cocktail_id FROM completed_cocktails)
                    ) AS completed,
                    COALESCE(tu.is_unlocked, false) AS is_unlocked
                FROM map_themes t
                JOIN map_nodes mn ON mn.theme_id = t.id
                LEFT JOIN theme_unlocked tu ON tu.theme_id = t.id
                WHERE t.is_active
                GROUP BY t.id, t.name_zh, t.cover_url, t.sort_order, tu.is_unlocked
                ORDER BY t.sort_order
            """),
            {"uid": user_id},
        ).fetchall()

        themes = [
            {
                "theme_id": r.theme_id,
                "name_zh": r.name_zh,
                "background_url": r.cover_url,
                "total": r.total,
                "completed": r.completed,
                "is_unlocked": r.is_unlocked,
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
