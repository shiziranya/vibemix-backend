from __future__ import annotations
import json
import uuid

from flask import Blueprint, current_app, request
from flask_jwt_extended import get_jwt_identity, jwt_required

from ..extensions import db
from ..models.cocktail import Cocktail
from ..models.share_card import ShareCard
from ..services.card_templates import (
    DEFAULT_TEMPLATE_ID,
    FONT_ROLES,
    get_template,
    get_required_font_roles,
    list_templates,
)
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
    返回所有模板摘要列表（平铺，不含 text_layers 和 decorations）。
    """
    return success({
        "templates": list_templates(),
        "default_template_id": DEFAULT_TEMPLATE_ID,
    })


@card_bp.route("/templates/<template_id>", methods=["GET"])
@jwt_required()
def get_template_detail(template_id: str):
    """
    GET /api/card/templates/:template_id
    返回单个模板的完整定义（含 text_layers、decorations、fonts 信息），
    前端用于实时 Canvas 预览。同时返回该模板所需的 font_roles 信息，
    前端可据此批量加载 Google Fonts。
    """
    tmpl = get_template(template_id)
    if not tmpl:
        return error(4207, "模板不存在", 404)

    # 附上该模板用到的字体角色及其 Google Fonts URL，方便前端批量加载
    required_roles = get_required_font_roles(template_id)
    fonts_needed = {role: FONT_ROLES[role] for role in required_roles if role in FONT_ROLES}
    # 前端不需要 backend_files，过滤掉
    fonts_for_frontend = {
        role: {k: v for k, v in info.items() if k != "backend_files"}
        for role, info in fonts_needed.items()
    }

    return success({
        "template": tmpl,
        "fonts": fonts_for_frontend,
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
    触发异步卡片合成。

    Body 新增字段：
      template_id    str   模板 ID，不传则使用默认模板
      text_overrides dict  前端拖拽产生的文字层位置覆盖
                           格式：{"layer_id": {"x": 0.06, "y": 0.65}, ...}
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

    template_id = params.get("template_id") or DEFAULT_TEMPLATE_ID
    text_overrides = params.get("text_overrides") or {}

    card = ShareCard(
        id=uuid.uuid4(),
        user_id=uuid.UUID(user_id),
        cocktail_id=params["cocktail_id"],
        session_id=params.get("session_id"),
        layout="portrait",
        template_id=template_id,
        text_overrides=text_overrides,
        user_photo_url=params.get("user_photo_url"),
        mood_caption=params.get("mood_caption", ""),
        status="pending",
    )
    db.session.add(card)
    db.session.commit()

    task_params = {
        "cocktail_name":    cocktail.name,
        "cocktail_name_zh": cocktail.name_zh or cocktail.name,
        "ai_copy":          data.get("ai_copy", ""),
        "mood_caption":     params.get("mood_caption", ""),
        "ingredients":      data.get("ingredients", []),
        "user_photo_url":   params.get("user_photo_url"),
        "template_id":      template_id,
        "text_overrides":   text_overrides,
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

    return success({"card_id": str(card.id), "status": "pending"}, http_status=202)


# ── 前端直接上传卡片图片 ────────────────────────────────────────────────────────

@card_bp.route("/submit", methods=["POST"])
@jwt_required()
def submit_card():
    """
    POST /api/card/submit
    前端 Canvas 渲染完毕后将图片直接上传，后端存储并立即返回结果。
    预览与最终结果由同一份 Canvas 代码生成，保证完全一致。

    multipart/form-data:
        image          file   必填，Canvas 导出的 PNG 或 JPEG（最大 20 MB）
        cocktail_id    int    必填
        template_id    str    可选，默认使用默认模板
        text_overrides str    可选，JSON 字符串，格式同 /generate
        session_id     str    可选
        user_photo_url str    可选
        mood_caption   str    可选
    """
    user_id = get_jwt_identity()

    if "image" not in request.files:
        return error(4101, "请上传卡片图片（字段名: image）", 422)

    file = request.files["image"]

    # Determine format from Content-Type first (reliable), then filename fallback.
    # canvas.toBlob() defaults to image/png even when the filename says .jpg.
    content_type = (file.content_type or "").lower()
    if "png" in content_type:
        mime_ext = "png"
    elif "jpeg" in content_type or "jpg" in content_type:
        mime_ext = "jpg"
    else:
        # Fall back to filename extension
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

    # ── 解析表单字段 ──
    try:
        cocktail_id = int(request.form.get("cocktail_id", ""))
    except (ValueError, TypeError):
        return error(4101, "cocktail_id 必填且必须是整数", 422)

    raw_overrides = request.form.get("text_overrides") or "{}"
    try:
        text_overrides = json.loads(raw_overrides)
        if not isinstance(text_overrides, dict):
            text_overrides = {}
    except Exception:
        text_overrides = {}

    template_id = request.form.get("template_id") or DEFAULT_TEMPLATE_ID
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
        session_id=session_id,
        layout="portrait",
        template_id=template_id,
        text_overrides=text_overrides,
        user_photo_url=user_photo_url,
        mood_caption=mood_caption,
        image_url=image_url,
        status="done",
    )
    db.session.add(card)
    db.session.commit()

    return success(
        {"card_id": str(card_id), "image_url": image_url, "status": "done"},
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
    user_id = get_jwt_identity()
    page = request.args.get("page", 1, type=int)
    per_page = min(request.args.get("per_page", 20, type=int), 50)

    total = (
        db.session.query(ShareCard)
        .filter_by(user_id=uuid.UUID(user_id))
        .count()
    )
    cards = (
        db.session.query(ShareCard)
        .filter_by(user_id=uuid.UUID(user_id))
        .order_by(ShareCard.created_at.desc())
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
        }
    )


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
