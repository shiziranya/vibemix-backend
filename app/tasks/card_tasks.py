from __future__ import annotations
"""
Celery 异步任务：卡片合成 + 上传 Supabase Storage。
使用 card_gen 微服务生成高质量卡片。
"""
import logging
import uuid

from ..extensions import celery, db
from ..models.share_card import ShareCard
from ..models.cocktail import Cocktail
from ..services.card_gen_client import card_gen_client

logger = logging.getLogger(__name__)


@celery.task(bind=True, max_retries=2, default_retry_delay=5)
def async_generate_card(self, card_id: str, params: dict) -> dict:
    """
    使用 card_gen 服务生成卡片。
    
    params keys:
        cocktail_id, session_id, cocktail_name, cocktail_name_zh, 
        ai_copy, ai_reason, mood_caption, ai_tweaks, prototype_name, 
        prototype_name_zh, ingredients, user_photo_url, template_id
    """
    try:
        # 获取鸡尾酒信息
        cocktail_id = params.get("cocktail_id")
        cocktail = db.session.get(Cocktail, cocktail_id)
        if not cocktail:
            raise ValueError(f"Cocktail {cocktail_id} not found")
        
        # 准备配料信息
        ingredients = params.get("ingredients", [])
        if not ingredients and hasattr(cocktail, "ingredients"):
            ingredients = [
                {
                    "name": ing.ingredient.name if hasattr(ing, "ingredient") else "",
                    "name_zh": ing.ingredient.name_zh if hasattr(ing, "ingredient") else "",
                    "measure": ing.measure or "",
                }
                for ing in cocktail.ingredients
            ]
        
        # 准备步骤信息
        steps = []
        if hasattr(cocktail, "steps") and cocktail.steps:
            try:
                import json
                steps_data = json.loads(cocktail.steps) if isinstance(cocktail.steps, str) else cocktail.steps
                if isinstance(steps_data, list):
                    steps = [{"description": s} if isinstance(s, str) else s for s in steps_data]
            except Exception:
                pass
        
        # 处理图片URL（转换相对路径为绝对路径）
        image_url = params.get("user_photo_url")
        if not image_url:
            image_url = getattr(cocktail, "image_url", None)
        
        if image_url and not image_url.startswith(("http://", "https://")):
            from flask import current_app
            base_url = current_app.config.get("BASE_URL", "").rstrip("/")
            if base_url:
                image_url = f"{base_url}{image_url if image_url.startswith('/') else '/' + image_url}"
            else:
                logger.warning(f"BASE_URL not configured, using relative path: {image_url}")
        
        if not image_url:
            logger.error("No image URL provided for cocktail %s", cocktail_id)
            raise ValueError("No image URL available for this cocktail")

        # 调用 card_gen 服务生成卡片
        image_bytes = card_gen_client.generate_card(
            session_id=params.get("session_id"),
            cocktail_id=cocktail_id,
            cocktail_name=params.get("cocktail_name") or cocktail.name,
            cocktail_name_zh=params.get("cocktail_name_zh") or cocktail.name_zh or cocktail.name,
            ai_reason=params.get("ai_reason", ""),
            ai_poetic=params.get("ai_copy", ""),
            mood_caption=params.get("mood_caption", ""),
            ai_tweaks=params.get("ai_tweaks"),
            prototype_name=params.get("prototype_name"),
            prototype_name_zh=params.get("prototype_name_zh"),
            ingredients=ingredients,
            user_photo_url=image_url,
            template_name=params.get("template_id"),
            abv_level=getattr(cocktail, "abv_level", None),
            difficulty=getattr(cocktail, "difficulty", None),
            mood_tags=getattr(cocktail, "mood_tags", []) if hasattr(cocktail, "mood_tags") else [],
            flavor_tags=getattr(cocktail, "flavor_tags", []) if hasattr(cocktail, "flavor_tags") else [],
            glass_type=getattr(cocktail, "glass_type", None),
            steps=steps,
        )
        
        # 上传到存储
        image_url = _upload_to_storage(card_id, image_bytes)

        # 更新数据库
        card = db.session.get(ShareCard, uuid.UUID(card_id))
        if card:
            card.image_url = image_url
            card.status = "done"
            db.session.commit()

        logger.info("Card %s generated successfully via card_gen: %s", card_id, image_url)
        return {"card_id": card_id, "status": "done", "image_url": image_url}

    except Exception as exc:
        logger.error("Card generation failed for %s: %s", card_id, exc, exc_info=True)
        try:
            card = db.session.get(ShareCard, uuid.UUID(card_id))
            if card:
                card.status = "failed"
                db.session.commit()
        except Exception:
            pass
        raise self.retry(exc=exc)


def _upload_to_storage(card_id: str, image_bytes: bytes) -> str:
    """Upload image bytes to Supabase Storage, return public URL."""
    from flask import current_app

    supabase_url = current_app.config.get("SUPABASE_URL", "")
    service_key = current_app.config.get("SUPABASE_SERVICE_KEY", "")
    bucket = current_app.config.get("SUPABASE_STORAGE_BUCKET", "vibemix")

    if not supabase_url or not service_key:
        # Dev fallback: save locally
        return _save_locally(card_id, image_bytes)

    try:
        from supabase import create_client

        client = create_client(supabase_url, service_key)
        path = f"cards/{card_id}.jpg"
        client.storage.from_(bucket).upload(
            path,
            image_bytes,
            {"content-type": "image/jpeg", "upsert": "true"},
        )
        return client.storage.from_(bucket).get_public_url(path)
    except Exception as e:
        logger.warning("Supabase upload failed, falling back to local: %s", e)
        return _save_locally(card_id, image_bytes)


def _save_locally(card_id: str, image_bytes: bytes) -> str:
    """Dev fallback: save to Flask static folder and return an absolute URL."""
    import os
    from flask import current_app

    static_dir = os.path.join(current_app.root_path, "static", "cards")
    os.makedirs(static_dir, exist_ok=True)

    path = os.path.join(static_dir, f"{card_id}.jpg")
    with open(path, "wb") as f:
        f.write(image_bytes)

    base_url = current_app.config.get("BASE_URL", "").rstrip("/")
    url = f"{base_url}/static/cards/{card_id}.jpg"
    logger.info("Card saved locally: %s -> %s", path, url)
    return url
