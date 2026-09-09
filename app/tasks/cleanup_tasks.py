"""
Celery 定时任务：清理过期的未收藏卡片
"""
import logging
import os
from datetime import datetime, timedelta, timezone

from ..extensions import celery, db
from ..models.share_card import ShareCard

logger = logging.getLogger(__name__)


@celery.task(name="cleanup_unfavorited_cards")
def cleanup_unfavorited_cards():
    """
    清理 24 小时前创建且未收藏的卡片。
    
    删除规则：
    - is_favorited = False
    - created_at < 24 小时前
    
    操作：
    1. 删除图片文件（本地或 Supabase）
    2. 删除数据库记录
    """
    try:
        # 计算截止时间（24 小时前）
        cutoff_time = datetime.now(timezone.utc) - timedelta(hours=24)
        
        # 查询需要清理的卡片
        cards_to_delete = ShareCard.query.filter(
            ShareCard.is_favorited == False,
            ShareCard.created_at < cutoff_time
        ).all()
        
        if not cards_to_delete:
            logger.info("No unfavorited cards to cleanup")
            return {
                "deleted_count": 0,
                "message": "No cards to cleanup"
            }
        
        deleted_count = 0
        deleted_images = 0
        
        for card in cards_to_delete:
            try:
                # 删除图片文件
                if card.image_url:
                    if _delete_card_image(card.image_url):
                        deleted_images += 1
                
                # 删除数据库记录
                db.session.delete(card)
                deleted_count += 1
                
            except Exception as e:
                logger.error(f"Failed to delete card {card.id}: {e}")
                continue
        
        # 提交数据库更改
        db.session.commit()
        
        logger.info(
            f"Cleanup completed: {deleted_count} cards deleted, "
            f"{deleted_images} images deleted"
        )
        
        return {
            "deleted_count": deleted_count,
            "deleted_images": deleted_images,
            "cutoff_time": cutoff_time.isoformat(),
            "message": f"Successfully cleaned up {deleted_count} unfavorited cards"
        }
        
    except Exception as e:
        logger.error(f"Cleanup task failed: {e}", exc_info=True)
        db.session.rollback()
        raise


def _delete_card_image(image_url: str) -> bool:
    """
    删除卡片图片文件。
    
    Args:
        image_url: 图片 URL（可能是本地路径或 Supabase URL）
    
    Returns:
        bool: 是否成功删除
    """
    try:
        from flask import current_app
        
        # 检查是否是本地文件
        if "/static/cards/" in image_url:
            # 本地文件删除
            filename = image_url.split("/static/cards/")[-1]
            static_dir = os.path.join(current_app.root_path, "static", "cards")
            filepath = os.path.join(static_dir, filename)
            
            if os.path.exists(filepath):
                os.remove(filepath)
                logger.info(f"Deleted local image: {filepath}")
                return True
            else:
                logger.warning(f"Local image not found: {filepath}")
                return False
        
        # Supabase Storage 删除
        elif "supabase" in image_url:
            supabase_url = current_app.config.get("SUPABASE_URL", "")
            service_key = current_app.config.get("SUPABASE_SERVICE_KEY", "")
            bucket = current_app.config.get("SUPABASE_STORAGE_BUCKET", "vibemix")
            
            if not supabase_url or not service_key:
                logger.warning("Supabase credentials not configured")
                return False
            
            try:
                from supabase import create_client
                
                client = create_client(supabase_url, service_key)
                
                # 从 URL 提取文件路径
                # 例如: https://.../storage/v1/object/public/vibemix/cards/xxx.jpg
                # 提取: cards/xxx.jpg
                path_parts = image_url.split(f"/object/public/{bucket}/")
                if len(path_parts) > 1:
                    file_path = path_parts[1]
                    client.storage.from_(bucket).remove([file_path])
                    logger.info(f"Deleted Supabase image: {file_path}")
                    return True
                else:
                    logger.warning(f"Could not parse Supabase path from URL: {image_url}")
                    return False
                    
            except Exception as e:
                logger.error(f"Failed to delete Supabase image: {e}")
                return False
        
        else:
            logger.warning(f"Unknown image URL format: {image_url}")
            return False
            
    except Exception as e:
        logger.error(f"Error deleting image {image_url}: {e}")
        return False
