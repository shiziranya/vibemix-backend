from __future__ import annotations
from flask import Blueprint, request
from flask_jwt_extended import get_jwt_identity, jwt_required

from ..services.auth_service import auth_service
from ..utils.errors import AppError, ValidationError
from ..utils.response import error, success
from ..utils.validators import validate_password, validate_phone

auth_bp = Blueprint("auth", __name__)


@auth_bp.errorhandler(AppError)
def handle_app_error(e: AppError):
    return error(e.code, e.message, e.http_status)


@auth_bp.route("/register", methods=["POST"])
def register():
    data = request.get_json(silent=True) or {}
    try:
        phone = validate_phone(data.get("phone", ""))
        password = validate_password(data.get("password", ""))
    except ValidationError as e:
        return error(e.code, e.message, e.http_status)

    result = auth_service.register(
        phone=phone,
        password=password,
        nickname=data.get("nickname"),
        avatar_url=data.get("avatar_url"),
    )
    return success(result, http_status=201)


@auth_bp.route("/login", methods=["POST"])
def login():
    data = request.get_json(silent=True) or {}
    try:
        phone = validate_phone(data.get("phone", ""))
        password = validate_password(data.get("password", ""))
    except ValidationError as e:
        return error(e.code, e.message, e.http_status)

    result = auth_service.login(phone=phone, password=password)
    return success(result)


@auth_bp.route("/wx_login", methods=["POST"])
def wx_login():
    data = request.get_json(silent=True) or {}
    code = data.get("code", "").strip()
    if not code:
        return error(4101, "code 不能为空", 422)

    result = auth_service.wx_login(code=code)
    return success(result)


@auth_bp.route("/refresh", methods=["POST"])
@jwt_required(refresh=True)
def refresh():
    user_id = get_jwt_identity()
    result = auth_service.refresh_token(user_id)
    return success(result)


@auth_bp.route("/me", methods=["GET"])
@jwt_required()
def get_me():
    user_id = get_jwt_identity()
    user = auth_service.get_user(user_id)
    return success(user.to_dict())


@auth_bp.route("/me", methods=["PUT"])
@jwt_required()
def update_me():
    user_id = get_jwt_identity()
    data = request.get_json(silent=True) or {}
    result = auth_service.update_profile(
        user_id=user_id,
        nickname=data.get("nickname"),
        avatar_url=data.get("avatar_url"),
    )
    return success(result)


@auth_bp.route("/logout", methods=["POST"])
@jwt_required()
def logout():
    user_id = get_jwt_identity()
    auth_service.revoke_refresh_token(user_id)
    return success(message="已退出登录")
