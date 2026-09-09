from __future__ import annotations

from datetime import date, datetime

from flask import Blueprint, request
from flask_jwt_extended import get_jwt_identity, jwt_required

from ..services.menu_service import menu_service
from ..utils.errors import AppError
from ..utils.response import error, success

menu_bp = Blueprint("menu", __name__)


@menu_bp.errorhandler(AppError)
def handle_app_error(e: AppError):
    return error(e.code, e.message, e.http_status)


# ── 收藏夹 API ───────────────────────────────────────────────────────────────


@menu_bp.route("/favorites", methods=["POST"])
@jwt_required()
def add_favorite():
    """
    添加鸡尾酒到收藏夹
    
    POST /api/menu/favorites
    Body: {
        "cocktail_id": 123,
        "note": "周末试试",  // 可选
        "add_to_today": false,  // 可选，是否同时添加到今日酒单
        "recommendation_id": 456  // 可选，如果来自LLM推荐
    }
    """
    user_id = get_jwt_identity()
    data = request.get_json(silent=True) or {}

    cocktail_id = data.get("cocktail_id")
    if not cocktail_id or not isinstance(cocktail_id, int):
        return error(4101, "cocktail_id 必填且必须是整数", 422)

    note = data.get("note")
    add_to_today = data.get("add_to_today", False)
    recommendation_id = data.get("recommendation_id")

    result = menu_service.add_to_favorites(
        user_id=user_id,
        cocktail_id=cocktail_id,
        note=note,
        add_to_today=add_to_today,
        recommendation_id=recommendation_id,
    )

    return success(result, http_status=201)


@menu_bp.route("/favorites", methods=["GET"])
@jwt_required()
def get_favorites():
    """
    获取收藏夹列表
    
    GET /api/menu/favorites?exclude_today=true&sort_by=added_at
    
    Query:
        exclude_today: 是否排除今日酒单中的（默认 false）
        sort_by: 排序方式 (added_at|name|difficulty，默认 added_at)
    """
    user_id = get_jwt_identity()

    exclude_today = request.args.get("exclude_today", "false").lower() == "true"
    sort_by = request.args.get("sort_by", "added_at")

    if sort_by not in ["added_at", "name", "difficulty"]:
        return error(4101, "sort_by 必须是 added_at、name 或 difficulty 之一", 422)

    cocktails = menu_service.get_favorites(
        user_id=user_id,
        exclude_today=exclude_today,
        sort_by=sort_by,
    )

    return success({"total": len(cocktails), "cocktails": cocktails})


@menu_bp.route("/favorites/<int:saved_id>", methods=["DELETE"])
@jwt_required()
def delete_favorite(saved_id: int):
    """
    从收藏夹删除（会同时从今日酒单移除）
    
    DELETE /api/menu/favorites/<saved_id>
    """
    user_id = get_jwt_identity()

    success_flag = menu_service.remove_from_favorites(user_id, saved_id)

    if not success_flag:
        return error(4041, "未找到该收藏记录", 404)

    return success({"message": "删除成功"})


@menu_bp.route("/favorites/<int:saved_id>/note", methods=["PATCH"])
@jwt_required()
def update_note(saved_id: int):
    """
    更新个人笔记
    
    PATCH /api/menu/favorites/<saved_id>/note
    Body: {"note": "新笔记内容"}
    """
    user_id = get_jwt_identity()
    data = request.get_json(silent=True) or {}

    note = data.get("note", "")

    success_flag = menu_service.update_note(user_id, saved_id, note)

    if not success_flag:
        return error(4041, "未找到该收藏记录", 404)

    return success({"message": "更新成功"})


# ── 今日酒单 API ─────────────────────────────────────────────────────────────


@menu_bp.route("/today", methods=["POST"])
@jwt_required()
def add_to_today():
    """
    添加鸡尾酒到今日酒单
    
    POST /api/menu/today
    Body: {
        "cocktail_id": 123,
        "note": "晚上要做",  // 可选
        "recommendation_id": 456  // 可选，如果来自LLM推荐
    }
    
    如果不在收藏夹，会先加入收藏夹
    """
    user_id = get_jwt_identity()
    data = request.get_json(silent=True) or {}

    cocktail_id = data.get("cocktail_id")
    if not cocktail_id or not isinstance(cocktail_id, int):
        return error(4101, "cocktail_id 必填且必须是整数", 422)

    note = data.get("note")
    recommendation_id = data.get("recommendation_id")

    result = menu_service.add_to_today(
        user_id=user_id,
        cocktail_id=cocktail_id,
        note=note,
        recommendation_id=recommendation_id,
    )

    return success(result, http_status=201)


@menu_bp.route("/today", methods=["GET"])
@jwt_required()
def get_today():
    """
    获取今日酒单
    
    GET /api/menu/today?date=2026-08-30
    
    Query:
        date: 日期 (YYYY-MM-DD，可选，默认今天)
    """
    user_id = get_jwt_identity()

    date_str = request.args.get("date")
    target_date = None

    if date_str:
        try:
            target_date = datetime.strptime(date_str, "%Y-%m-%d").date()
        except ValueError:
            return error(4101, "date 格式不正确，应为 YYYY-MM-DD", 422)

    result = menu_service.get_today_menu(user_id, target_date)

    return success(result)


@menu_bp.route("/today/<int:saved_id>", methods=["DELETE"])
@jwt_required()
def remove_from_today(saved_id: int):
    """
    从今日酒单移除（保留在收藏夹）
    
    DELETE /api/menu/today/<saved_id>
    """
    user_id = get_jwt_identity()

    success_flag = menu_service.remove_from_today(user_id, saved_id)

    if not success_flag:
        return error(4041, "未找到该记录", 404)

    return success({"message": "已从今日酒单移除"})


@menu_bp.route("/today/<int:saved_id>/priority", methods=["PATCH"])
@jwt_required()
def update_priority(saved_id: int):
    """
    更新优先级
    
    PATCH /api/menu/today/<saved_id>/priority
    Body: {"priority": 10}
    """
    user_id = get_jwt_identity()
    data = request.get_json(silent=True) or {}

    priority = data.get("priority")
    if priority is None or not isinstance(priority, int):
        return error(4101, "priority 必填且必须是整数", 422)

    success_flag = menu_service.update_priority(user_id, saved_id, priority)

    if not success_flag:
        return error(4041, "未找到该记录", 404)

    return success({"message": "优先级更新成功"})


# ── 购物清单 API ─────────────────────────────────────────────────────────────


@menu_bp.route("/shopping-list", methods=["POST"])
@jwt_required()
def generate_shopping_list():
    """
    生成购物清单（基于今日酒单）
    
    POST /api/menu/shopping-list
    Body: {
        "date": "2026-08-30"  // 可选，默认今天
    }
    """
    user_id = get_jwt_identity()
    data = request.get_json(silent=True) or {}

    date_str = data.get("date")
    target_date = None

    if date_str:
        try:
            target_date = datetime.strptime(date_str, "%Y-%m-%d").date()
        except ValueError:
            return error(4101, "date 格式不正确，应为 YYYY-MM-DD", 422)

    result = menu_service.generate_shopping_list(user_id, target_date)

    return success(result)


# ── 批量操作 API ─────────────────────────────────────────────────────────────


@menu_bp.route("/batch", methods=["POST"])
@jwt_required()
def batch_operation():
    """
    批量操作
    
    POST /api/menu/batch
    Body: {
        "action": "add_to_today" | "remove_from_today" | "delete",
        "saved_ids": [1, 2, 3]
    }
    """
    user_id = get_jwt_identity()
    data = request.get_json(silent=True) or {}

    action = data.get("action")
    saved_ids = data.get("saved_ids", [])

    if not action or action not in ["add_to_today", "remove_from_today", "delete"]:
        return error(
            4101,
            "action 必填且必须是 add_to_today、remove_from_today 或 delete 之一",
            422,
        )

    if not isinstance(saved_ids, list) or not saved_ids:
        return error(4101, "saved_ids 必填且必须是非空数组", 422)

    if action == "add_to_today":
        result = menu_service.batch_add_to_today(user_id, saved_ids)
    elif action == "remove_from_today":
        result = menu_service.batch_remove_from_today(user_id, saved_ids)
    else:  # delete
        result = menu_service.batch_delete(user_id, saved_ids)

    return success(result)


# ── 统计 API ─────────────────────────────────────────────────────────────────


@menu_bp.route("/stats", methods=["GET"])
@jwt_required()
def get_stats():
    """
    获取酒单统计数据
    
    GET /api/menu/stats
    """
    user_id = get_jwt_identity()

    # 获取收藏夹数量
    favorites = menu_service.get_favorites(user_id, exclude_today=False)
    favorites_count = len(favorites)

    # 获取今日酒单数量
    today_menu = menu_service.get_today_menu(user_id)
    today_count = today_menu["count"]

    # 获取纯收藏夹数量（不在今日酒单中的）
    favorites_only = menu_service.get_favorites(user_id, exclude_today=True)
    favorites_only_count = len(favorites_only)

    return success({
        "total_favorites": favorites_count,
        "today_count": today_count,
        "favorites_only_count": favorites_only_count,
    })
