from __future__ import annotations
"""
Celery 异步任务：卡片合成 + 上传 Supabase Storage。
"""
import logging
import uuid

from ..extensions import celery, db
from ..models.share_card import ShareCard
from ..services.card_service import CardParams, card_service

logger = logging.getLogger(__name__)


@celery.task(bind=True, max_retries=2, default_retry_delay=5)
def async_generate_card(self, card_id: str, params: dict) -> dict:
    """
    params keys:
        cocktail_name, cocktail_name_zh, ai_copy, mood_caption,
        ingredients, user_photo_url, template_id, text_overrides
    """
    try:
        card_params = CardParams(
            cocktail_name=params["cocktail_name"],
            cocktail_name_zh=params.get("cocktail_name_zh", ""),
            ai_copy=params.get("ai_copy", ""),
            mood_caption=params.get("mood_caption", ""),
            ingredients=params.get("ingredients", []),
            user_photo_url=params.get("user_photo_url"),
            template_id=params.get("template_id", ""),
            text_overrides=params.get("text_overrides", {}),
        )

        image_bytes = card_service.generate_card(card_params)
        image_url = _upload_to_storage(card_id, image_bytes)

        card = db.session.get(ShareCard, uuid.UUID(card_id))
        if card:
            card.image_url = image_url
            card.status = "done"
            db.session.commit()

        logger.info("Card %s generated successfully: %s", card_id, image_url)
        return {"card_id": card_id, "status": "done", "image_url": image_url}

    except Exception as exc:
        logger.error("Card generation failed for %s: %s", card_id, exc)
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
