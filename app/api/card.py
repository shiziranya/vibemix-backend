from __future__ import annotations
import json
import uuid

from flask import Blueprint, current_app, request
from flask_jwt_extended import get_jwt_identity, jwt_required

from ..extensions import db
from ..models.cocktail import Cocktail
from ..models.share_card import ShareCard
from ..services.card_gen_client import card_gen_client
from ..tasks.card_tasks import async_generate_card
from ..utils.errors import AppError, CardNotFound, ValidationError
from ..utils.response import error, success
from ..utils.validators import validate_card_request

card_bp = Blueprint("card", __name__)


@card_bp.errorhandler(AppError)
def handle_app_error(e: AppError):
    return error(e.code, e.message, e.http_status)


# ── 模板接口 ───────────────────────────────────────────────────────────────────

@card_bp.route("/templates", methods=["GET"])
@jwt_required()
def get_templates():
    """
    GET /api/card/templates
    返回 card_gen 服务提供的所有模板名称列表（33个模板）。
    """
    templates = card_gen_client.get_available_templates()
    if not templates:
        return error(5001, "无法获取模板列表，card_gen 服务可能未启动", 503)
    
    # 随机选择一个作为默认模板（用于前端随机选择）
    import random
    default_template = random.choice(templates) if templates else None
    
    return success({
        "templates": templates,
        "total": len(templates),
        "default_template_id": default_template,
        "note": "建议前端随机选择一个模板用于卡片生成"
    })


@card_bp.route("/templates/with-ingredients", methods=["GET"])
@jwt_required()
def get_ingredient_templates():
    """
    GET /api/card/templates/with-ingredients
    获取支持显示配料的模板列表（推荐用于生成卡片）。
    
    这些模板在 card_gen 服务的 ContentSlot 配置中设置了 show_ingredients=True，
    可以正确显示配料列表而不是标签。
    """
    # 支持配料显示的模板（基于 card_gen/app/analysis/content_select.py 分析）
    INGREDIENT_TEMPLATES = [
        'vesper', 'strata', 'herald', 'docket', 'carte',
        'lucent', 'vitrine', 'index', 'haze', 'remedy',
        'entry', 'materia', 'vinyl', 'saffron'
    ]
    
    all_templates = card_gen_client.get_available_templates()
    filtered = [t for t in all_templates if t in INGREDIENT_TEMPLATES]
    
    return success({
        "templates": filtered,
        "total": len(filtered),
        "note": "这些模板支持显示配料列表，推荐用于生成卡片",
        "usage": "从这些模板中随机选择一个，确保卡片显示配料而不是标签"
    })


@card_bp.route("/templates/<template_id>", methods=["GET"])
@jwt_required()
def get_template_detail(template_id: str):
    """
    GET /api/card/templates/:template_id
    验证模板是否存在于 card_gen 服务中。
    """
    templates = card_gen_client.get_available_templates()
    if template_id not in templates:
        return error(4207, f"模板 '{template_id}' 不存在", 404)

    return success({
        "template_id": template_id,
        "exists": True,
        "note": "该模板由 card_gen 服务提供"
    })


# ── 照片上传 ───────────────────────────────────────────────────────────────────

@card_bp.route("/upload-photo", methods=["POST"])
@jwt_required()
def upload_photo():
    """Upload user cocktail photo to Supabase Storage."""
    user_id = get_jwt_identity()

    if "file" not in request.files:
        return error(4101, "请上传文件（字段名: file）", 422)

    file = request.files["file"]
    if not file.filename:
        return error(4101, "文件名不能为空", 422)

    ext = file.filename.rsplit(".", 1)[-1].lower()
    if ext not in {"jpg", "jpeg", "png"}:
        return error(4101, "仅支持 jpg / png 格式", 422)

    data = file.read()
    if len(data) > 10 * 1024 * 1024:
        return error(4101, "文件大小不能超过 10MB", 422)

    photo_url = _upload_photo_to_storage(user_id, data, ext)
    return success({"photo_url": photo_url}, http_status=201)


# ── 卡片生成 ───────────────────────────────────────────────────────────────────

@card_bp.route("/generate", methods=["POST"])
@jwt_required()
def generate_card():
    """
    POST /api/card/generate
    触发异步卡片合成，使用 card_gen 服务生成高质量卡片。

    Body 字段：
      cocktail_id        int     必填：鸡尾酒ID
      session_id         str     可选：推荐会话ID
      template_id        str     可选：模板ID，不传则随机选择
      user_photo_url     str     可选：用户上传的图片URL
      mood_caption       str     可选：心情描述
      ai_copy            str     可选：AI诗意文案
      ai_reason          str     可选：AI推荐理由
      ai_tweaks          dict    可选：配方调整（原创模式）
      prototype_name     str     可选：原型鸡尾酒名称（原创模式）
      prototype_name_zh  str     可选：原型鸡尾酒中文名（原创模式）
      ingredients        list    可选：配料列表
    """
    user_id = get_jwt_identity()
    data = request.get_json(silent=True) or {}

    try:
        params = validate_card_request(data)
    except ValidationError as e:
        return error(e.code, e.message, e.http_status)

    cocktail = db.session.get(Cocktail, params["cocktail_id"])
    if not cocktail:
        return error(4203, "配方不存在", 404)

    # 获取或随机选择模板
    template_id = params.get("template_id")
    if not template_id:
        templates = card_gen_client.get_available_templates()
        if templates:
            import random
            template_id = random.choice(templates)
        else:
            return error(5001, "无法获取模板列表，card_gen 服务可能未启动", 503)

    card = ShareCard(
        id=uuid.uuid4(),
        user_id=uuid.UUID(user_id),
        cocktail_id=params["cocktail_id"],
        cocktail_name=data.get("cocktail_name") or cocktail.name_zh or cocktail.name,
        ai_poetic=data.get("ai_copy", ""),
        session_id=params.get("session_id"),
        layout="portrait",
        template_id=template_id,
        text_overrides={},
        user_photo_url=params.get("user_photo_url"),
        mood_caption=params.get("mood_caption", ""),
        status="pending",
    )
    db.session.add(card)
    db.session.commit()

    task_params = {
        "cocktail_id":      params["cocktail_id"],
        "session_id":       params.get("session_id"),
        "cocktail_name":    data.get("cocktail_name") or cocktail.name,
        "cocktail_name_zh": data.get("cocktail_name_zh") or cocktail.name_zh or cocktail.name,
        "ai_copy":          data.get("ai_copy", ""),
        "ai_reason":        data.get("ai_reason", ""),
        "mood_caption":     params.get("mood_caption", ""),
        "ai_tweaks":        data.get("ai_tweaks"),
        "prototype_name":   data.get("prototype_name"),
        "prototype_name_zh": data.get("prototype_name_zh"),
        "ingredients":      data.get("ingredients", []),
        "user_photo_url":   params.get("user_photo_url"),
        "template_id":      template_id,
    }

    try:
        async_generate_card.delay(str(card.id), task_params)
    except Exception as e:
        current_app.logger.warning(
            "Celery broker unavailable (%s), running card generation synchronously", e
        )
        try:
            async_generate_card(str(card.id), task_params)
        except Exception as sync_err:
            current_app.logger.error("Sync card generation failed: %s", sync_err)

    return success({"card_id": str(card.id), "status": "pending", "template_id": template_id}, http_status=202)


# ── 前端直接上传卡片图片 ────────────────────────────────────────────────────────

@card_bp.route("/submit", methods=["POST"])
@jwt_required()
def submit_card():
    """
    POST /api/card/submit
    前端 Canvas 渲染完毕后将图片直接上传，后端存储并立即返回结果。

    multipart/form-data:
        image          file   必填，Canvas 导出的 PNG 或 JPEG（最大 20 MB）
        cocktail_id    int    必填
        template_id    str    可选，默认随机选择
        session_id     str    可选
        user_photo_url str    可选
        mood_caption   str    可选
    """
    user_id = get_jwt_identity()

    if "image" not in request.files:
        return error(4101, "请上传卡片图片（字段名: image）", 422)

    file = request.files["image"]

    # Determine format from Content-Type first (reliable), then filename fallback.
    content_type = (file.content_type or "").lower()
    if "png" in content_type:
        mime_ext = "png"
    elif "jpeg" in content_type or "jpg" in content_type:
        mime_ext = "jpg"
    else:
        raw_ext = (file.filename.rsplit(".", 1)[-1] if file.filename and "." in file.filename else "").lower()
        if raw_ext == "png":
            mime_ext = "png"
        elif raw_ext in {"jpg", "jpeg"}:
            mime_ext = "jpg"
        else:
            return error(4101, "仅支持 jpg / png 格式（Content-Type 或文件名需包含格式信息）", 422)

    image_data = file.read()
    if len(image_data) > 20 * 1024 * 1024:
        return error(4101, "文件大小不能超过 20MB", 422)

    # 解析表单字段
    cocktail_id_raw = request.form.get("cocktail_id")
    if not cocktail_id_raw:
        return error(4101, "cocktail_id 必填", 422)
    
    try:
        cocktail_id = int(cocktail_id_raw)
    except (ValueError, TypeError):
        return error(4101, "cocktail_id 必须是整数或可转换为整数的字符串", 422)

    # 获取或随机选择模板
    template_id = request.form.get("template_id")
    if not template_id:
        templates = card_gen_client.get_available_templates()
        if templates:
            import random
            template_id = random.choice(templates)

    session_id = request.form.get("session_id")
    user_photo_url = request.form.get("user_photo_url")
    mood_caption = request.form.get("mood_caption", "")

    cocktail = db.session.get(Cocktail, cocktail_id)
    if not cocktail:
        return error(4203, "配方不存在", 404)

    card_id = uuid.uuid4()
    image_url = _upload_card_image_to_storage(str(card_id), image_data, mime_ext)

    card = ShareCard(
        id=card_id,
        user_id=uuid.UUID(user_id),
        cocktail_id=cocktail_id,
        cocktail_name=cocktail.name_zh or cocktail.name,
        session_id=session_id,
        layout="portrait",
        template_id=template_id,
        text_overrides={},
        user_photo_url=user_photo_url,
        mood_caption=mood_caption,
        image_url=image_url,
        status="done",
    )
    db.session.add(card)
    db.session.commit()

    return success(
        {"card_id": str(card_id), "image_url": image_url, "status": "done", "template_id": template_id},
        http_status=201,
    )


# ── 卡片查询 ───────────────────────────────────────────────────────────────────

@card_bp.route("/<card_id>", methods=["GET"])
@jwt_required()
def get_card(card_id: str):
    user_id = get_jwt_identity()
    try:
        card_uuid = uuid.UUID(card_id)
    except ValueError:
        return error(4101, "card_id 格式不正确", 422)

    card = db.session.get(ShareCard, card_uuid)
    if not card or str(card.user_id) != user_id:
        raise CardNotFound()

    return success(card.to_dict())


@card_bp.route("/my", methods=["GET"])
@jwt_required()
def my_cards():
    """
    GET /api/card/my
    获取当前用户的卡片列表。
    
    查询参数：
      page          int    页码（默认 1）
      per_page      int    每页数量（默认 20，最大 50）
      include_temp  bool   是否包含未收藏的临时卡片（默认 false）
    
    默认只返回已收藏的卡片，未收藏的卡片会在 24 小时后自动清理。
    """
    user_id = get_jwt_identity()
    page = request.args.get("page", 1, type=int)
    per_page = min(request.args.get("per_page", 20, type=int), 50)
    include_temp = request.args.get("include_temp", "false").lower() == "true"

    # 构建查询
    query = db.session.query(ShareCard).filter_by(user_id=uuid.UUID(user_id))
    
    # 默认只返回已收藏的卡片
    if not include_temp:
        query = query.filter_by(is_favorited=True)

    total = query.count()
    cards = (
        query.order_by(ShareCard.created_at.desc())
        .offset((page - 1) * per_page)
        .limit(per_page)
        .all()
    )
    
    return success(
        {
            "items": [c.to_dict() for c in cards],
            "total": total,
            "page": page,
            "per_page": per_page,
            "include_temp": include_temp,
            "note": "默认只显示收藏的卡片，未收藏的卡片会在 24 小时后自动清理"
        }
    )


# ── 卡片收藏 ──────────────────────────────────────────────────────────────────

@card_bp.route("/<card_id>/favorite", methods=["POST"])
@jwt_required()
def favorite_card(card_id: str):
    """
    POST /api/card/{card_id}/favorite
    收藏卡片。收藏后的卡片会永久保存，不会被自动清理。
    """
    user_id = get_jwt_identity()
    
    try:
        card_uuid = uuid.UUID(card_id)
    except ValueError:
        return error(4101, "card_id 格式不正确", 422)
    
    card = db.session.get(ShareCard, card_uuid)
    if not card or str(card.user_id) != user_id:
        raise CardNotFound()
    
    if card.is_favorited:
        return success({
            "card_id": str(card.id),
            "is_favorited": True,
            "message": "卡片已经收藏过了"
        })
    
    card.is_favorited = True
    db.session.commit()
    
    return success({
        "card_id": str(card.id),
        "is_favorited": True,
        "message": "收藏成功"
    })


@card_bp.route("/<card_id>/favorite", methods=["DELETE"])
@jwt_required()
def unfavorite_card(card_id: str):
    """
    DELETE /api/card/{card_id}/favorite
    取消收藏卡片。取消收藏后，卡片会在 24 小时后被自动清理。
    """
    user_id = get_jwt_identity()
    
    try:
        card_uuid = uuid.UUID(card_id)
    except ValueError:
        return error(4101, "card_id 格式不正确", 422)
    
    card = db.session.get(ShareCard, card_uuid)
    if not card or str(card.user_id) != user_id:
        raise CardNotFound()
    
    if not card.is_favorited:
        return success({
            "card_id": str(card.id),
            "is_favorited": False,
            "message": "卡片本来就没有收藏"
        })
    
    card.is_favorited = False
    db.session.commit()
    
    return success({
        "card_id": str(card.id),
        "is_favorited": False,
        "message": "已取消收藏，该卡片将在 24 小时后被自动清理"
    })


# ── Storage helpers ────────────────────────────────────────────────────────────

def _upload_photo_to_storage(user_id: str, data: bytes, ext: str) -> str:
    supabase_url = current_app.config.get("SUPABASE_URL", "")
    service_key = current_app.config.get("SUPABASE_SERVICE_KEY", "")
    bucket = current_app.config.get("SUPABASE_STORAGE_BUCKET", "vibemix")

    if not supabase_url or not service_key:
        import os
        static_dir = os.path.join(current_app.root_path, "static", "photos")
        os.makedirs(static_dir, exist_ok=True)
        name = uuid.uuid4().hex
        filepath = os.path.join(static_dir, f"{name}.{ext}")
        with open(filepath, "wb") as f:
            f.write(data)
        base_url = current_app.config.get("BASE_URL", "").rstrip("/")
        return f"{base_url}/static/photos/{name}.{ext}"

    from supabase import create_client

    client = create_client(supabase_url, service_key)
    path = f"photos/{user_id}/{uuid.uuid4().hex}.{ext}"
    client.storage.from_(bucket).upload(
        path,
        data,
        {"content-type": f"image/{ext}", "upsert": "true"},
    )
    return client.storage.from_(bucket).get_public_url(path)


def _upload_card_image_to_storage(card_id: str, data: bytes, ext: str) -> str:
    """Upload a frontend-rendered card image to storage, return public URL."""
    import os

    supabase_url = current_app.config.get("SUPABASE_URL", "")
    service_key = current_app.config.get("SUPABASE_SERVICE_KEY", "")
    bucket = current_app.config.get("SUPABASE_STORAGE_BUCKET", "vibemix")

    if not supabase_url or not service_key:
        static_dir = os.path.join(current_app.root_path, "static", "cards")
        os.makedirs(static_dir, exist_ok=True)
        filepath = os.path.join(static_dir, f"{card_id}.{ext}")
        with open(filepath, "wb") as f:
            f.write(data)
        base_url = current_app.config.get("BASE_URL", "").rstrip("/")
        return f"{base_url}/static/cards/{card_id}.{ext}"

    from supabase import create_client

    client = create_client(supabase_url, service_key)
    path = f"cards/{card_id}.{ext}"
    client.storage.from_(bucket).upload(
        path,
        data,
        {"content-type": f"image/{ext}", "upsert": "true"},
    )
    return client.storage.from_(bucket).get_public_url(path)
