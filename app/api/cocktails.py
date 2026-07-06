from __future__ import annotations
from flask import Blueprint, request
from flask_jwt_extended import get_jwt_identity, jwt_required

from ..services.cocktail_service import cocktail_service
from ..utils.errors import AppError
from ..utils.response import error, success

cocktails_bp = Blueprint("cocktails", __name__)


@cocktails_bp.errorhandler(AppError)
def handle_app_error(e: AppError):
    return error(e.code, e.message, e.http_status)


@cocktails_bp.route("", methods=["GET"])
@jwt_required()
def search_cocktails():
    q = request.args.get("q")
    category = request.args.get("category")
    limit = min(request.args.get("limit", 20, type=int), 100)
    offset = request.args.get("offset", 0, type=int)

    items = cocktail_service.search(q=q, category=category, limit=limit, offset=offset)
    return success({"items": items, "count": len(items)})


@cocktails_bp.route("/<int:cocktail_id>", methods=["GET"])
@jwt_required()
def get_cocktail(cocktail_id: int):
    user_id = get_jwt_identity()
    result = cocktail_service.get_detail(cocktail_id, user_id=user_id)
    return success(result)


@cocktails_bp.route("/<int:cocktail_id>/steps", methods=["GET"])
@jwt_required()
def get_steps(cocktail_id: int):
    steps = cocktail_service.get_steps(cocktail_id)
    return success({"steps": steps})
