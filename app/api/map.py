from __future__ import annotations

from flask import Blueprint, request
from flask_jwt_extended import get_jwt_identity, jwt_required

from ..services.map_service import map_service
from ..utils.response import error, success

map_bp = Blueprint("map", __name__)


# ── 公开：主题列表（无需登录，供编辑器使用）──────────────────────────────

@map_bp.route("/themes/list", methods=["GET"])
def get_themes_public():
    """返回所有主题基本信息，不含用户进度。"""
    from sqlalchemy import text
    from ..extensions import db
    rows = db.session.execute(
        text("""
            SELECT t.id, t.slug, t.name_zh, t.sort_order, t.color_primary,
                   COUNT(mn.id) AS node_total
            FROM map_themes t
            LEFT JOIN map_nodes mn ON mn.theme_id = t.id
            WHERE t.is_active
            GROUP BY t.id
            ORDER BY t.sort_order
        """)
    ).fetchall()
    return success({
        "themes": [
            {"id": r.id, "slug": r.slug, "name_zh": r.name_zh,
             "color_primary": r.color_primary, "node_total": r.node_total}
            for r in rows
        ]
    })


# ── 主题列表 ─────────────────────────────────────────────────────────────────

@map_bp.route("/themes", methods=["GET"])
@jwt_required()
def get_themes():
    user_id = get_jwt_identity()
    themes = map_service.get_themes(user_id)
    return success({"themes": themes, "total": len(themes)})


# ── 主题图谱 ─────────────────────────────────────────────────────────────────

@map_bp.route("/themes/<int:theme_id>", methods=["GET"])
@jwt_required()
def get_theme_graph(theme_id: int):
    user_id = get_jwt_identity()
    data = map_service.get_theme_graph(theme_id, user_id)
    if not data:
        return error(4401, "主题不存在", 404)
    return success(data)


# ── 完成节点 ─────────────────────────────────────────────────────────────────

@map_bp.route("/nodes/<int:node_id>/complete", methods=["POST"])
@jwt_required()
def complete_node(node_id: int):
    user_id = get_jwt_identity()
    try:
        result = map_service.complete_node(node_id, user_id)
    except ValueError as e:
        return error(4402, str(e), 404)
    return success(result)


# ── 缺少的基酒 ───────────────────────────────────────────────────────────────

@map_bp.route("/nodes/<int:node_id>/missing-spirits", methods=["GET"])
@jwt_required()
def get_missing_spirits(node_id: int):
    user_id = get_jwt_identity()
    items = map_service.get_missing_spirits(node_id, user_id)
    return success({"items": items, "count": len(items)})


# ── 用户统计 ─────────────────────────────────────────────────────────────────

@map_bp.route("/stats", methods=["GET"])
@jwt_required()
def get_stats():
    user_id = get_jwt_identity()
    data = map_service.get_user_stats(user_id)
    return success(data)


# ── 批量更新节点位置（星图编辑器专用）──────────────────────────────────────

@map_bp.route("/nodes/positions", methods=["PATCH"])
@jwt_required()
def update_positions():
    """
    批量保存节点的 pos_x / pos_y。
    Body: { "updates": [{"node_id": 1, "pos_x": 180.0, "pos_y": 450.0}, ...] }
    """
    data = request.get_json(silent=True) or {}
    updates = data.get("updates")
    if not updates or not isinstance(updates, list):
        return error(4100, "updates 为必填数组", 422)

    count = map_service.batch_update_positions(updates)
    return success({"updated": count}, message="位置已保存")


# ── 公开：返回所有主题的节点位置（无需认证，供编辑器初始化）──────────────

@map_bp.route("/themes/<int:theme_id>/layout", methods=["GET"])
def get_theme_layout(theme_id: int):
    """
    返回主题的节点 + 边（不含用户状态）。
    供星图编辑器在无登录状态下加载布局数据。
    """
    from sqlalchemy import text
    from ..extensions import db

    theme_row = db.session.execute(
        text("SELECT id,slug,name_zh,color_primary FROM map_themes WHERE id=:tid"),
        {"tid": theme_id},
    ).fetchone()
    if not theme_row:
        return error(4401, "主题不存在", 404)

    nodes = db.session.execute(
        text("""
            SELECT mn.id, mn.node_key, mn.display_name_zh, mn.cocktail_id,
                   mn.is_entry_node, mn.is_boss, mn.complexity,
                   mn.base_spirits, mn.sort_order, mn.pos_x, mn.pos_y
            FROM map_nodes mn
            WHERE mn.theme_id = :tid
            ORDER BY mn.sort_order, mn.id
        """),
        {"tid": theme_id},
    ).fetchall()

    edges = db.session.execute(
        text("""
            SELECT e.from_node_id, e.to_node_id, e.edge_type, e.edge_label
            FROM map_edges e
            JOIN map_nodes a ON a.id = e.from_node_id AND a.theme_id = :tid
            JOIN map_nodes b ON b.id = e.to_node_id   AND b.theme_id = :tid
        """),
        {"tid": theme_id},
    ).fetchall()

    return success({
        "theme": {
            "id": theme_row.id,
            "slug": theme_row.slug,
            "name_zh": theme_row.name_zh,
            "color_primary": theme_row.color_primary,
        },
        "nodes": [
            {
                "id": r.id,
                "node_key": r.node_key,
                "display_name_zh": r.display_name_zh,
                "cocktail_id": r.cocktail_id,
                "is_entry_node": r.is_entry_node,
                "is_boss": r.is_boss,
                "complexity": r.complexity,
                "base_spirits": r.base_spirits or [],
                "sort_order": r.sort_order,
                "pos_x": float(r.pos_x) if r.pos_x is not None else None,
                "pos_y": float(r.pos_y) if r.pos_y is not None else None,
            }
            for r in nodes
        ],
        "edges": [
            {
                "from": r.from_node_id,
                "to": r.to_node_id,
                "type": r.edge_type,
                "label": r.edge_label,
            }
            for r in edges
        ],
    })
