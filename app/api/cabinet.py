from __future__ import annotations
from flask import Blueprint, request
from flask_jwt_extended import get_jwt_identity, jwt_required

from ..services.cabinet_service import cabinet_service
from ..utils.errors import AppError, ValidationError
from ..utils.response import error, success

cabinet_bp = Blueprint("cabinet", __name__)


@cabinet_bp.errorhandler(AppError)
def handle_app_error(e: AppError):
    return error(e.code, e.message, e.http_status)


@cabinet_bp.route("", methods=["GET"])
@jwt_required()
def get_cabinet():
    user_id = get_jwt_identity()
    items = cabinet_service.get_cabinet(user_id)
    return success({"items": items, "total": len(items)})


@cabinet_bp.route("/stats", methods=["GET"])
@jwt_required()
def get_stats():
    user_id = get_jwt_identity()
    stats = cabinet_service.get_stats(user_id)
    return success(stats)


@cabinet_bp.route("/items", methods=["POST"])
@jwt_required()
def add_item():
    user_id = get_jwt_identity()
    data = request.get_json(silent=True) or {}
    family_id = data.get("family_id")
    if not family_id or not isinstance(family_id, int):
        return error(4101, "family_id 必填且必须是整数", 422)

    result = cabinet_service.add_ingredient(user_id, family_id)
    return success(result, http_status=201)


@cabinet_bp.route("/items/<int:family_id>", methods=["DELETE"])
@jwt_required()
def remove_item(family_id: int):
    user_id = get_jwt_identity()
    result = cabinet_service.remove_ingredient(user_id, family_id)
    return success(result)


@cabinet_bp.route("/preview", methods=["GET"])
@jwt_required()
def preview_unlock():
    user_id = get_jwt_identity()
    family_id = request.args.get("family_id", type=int)
    if not family_id:
        return error(4101, "family_id 参数必填", 422)

    count = cabinet_service.preview_unlock(user_id, family_id)
    return success({"new_unlock_count": count})


@cabinet_bp.route("/ingredients", methods=["GET"])
@jwt_required()
def search_ingredients():
    user_id = get_jwt_identity()
    q = request.args.get("q")
    category = request.args.get("category")
    family = request.args.get("family")
    page = request.args.get("page", 1, type=int)
    per_page = min(request.args.get("per_page", 20, type=int), 100)

    result = cabinet_service.search_ingredients(
        q=q, category=category, family=family, page=page, per_page=per_page, user_id=user_id
    )
    return success(result)


@cabinet_bp.route("/recommendation", methods=["GET"])
@jwt_required()
def get_spirit_recommendation():
    """获取推荐的基酒信息
    
    该接口返回添加哪个基酒后能解锁最多配方。
    
    计算逻辑：
    - 只计算 is_easily_available=FALSE 的材料（需要购买的材料）
    - 忽略 is_easily_available=TRUE 的材料（便利店易购，如果汁、糖浆等）
    """
    user_id = get_jwt_identity()
    recommendation = cabinet_service.get_user_spirit_recommendation(user_id)
    
    if recommendation:
        return success(recommendation)
    else:
        return success({
            "family_id": None,
            "unlock_count": 0,
            "family": None,
            "message": "暂无推荐"
        })


@cabinet_bp.route("/recommendation/refresh", methods=["POST"])
@jwt_required()
def refresh_spirit_recommendation():
    """手动刷新推荐的基酒信息
    
    重新计算并更新用户的基酒推荐。
    通常在添加/删除酒柜物品时会自动触发，此接口用于手动刷新。
    """
    user_id = get_jwt_identity()
    cabinet_service.update_user_spirit_recommendation(user_id)
    recommendation = cabinet_service.get_user_spirit_recommendation(user_id)
    
    if recommendation:
        return success(recommendation)
    else:
        return success({
            "family_id": None,
            "unlock_count": 0,
            "family": None,
            "message": "暂无推荐"
        })
