"""
图片处理工具
"""
import os
import io
import hashlib
from pathlib import Path
from typing import Optional
from PIL import Image
from flask import current_app


def generate_thumbnail(image_url: str, size: int = 100, quality: int = 85) -> Optional[str]:
    """
    生成缩略图
    
    Args:
        image_url: 原图URL（完整URL或相对路径）
        size: 缩略图尺寸（宽度，高度按比例缩放）
        quality: JPEG质量（1-100）
    
    Returns:
        缩略图URL（相对路径），失败返回None
    """
    if not image_url:
        return None
    
    try:
        # 解析原图路径
        if image_url.startswith(('http://', 'https://')):
            # 提取相对路径
            # 例如: http://115.191.50.177:5005/static/cocktail/images/57_cuba_libre.jpg
            # 提取: /static/cocktail/images/57_cuba_libre.jpg
            parts = image_url.split('/static/')
            if len(parts) < 2:
                return None
            relative_path = '/static/' + parts[1]
        else:
            relative_path = image_url
        
        # 获取原图文件路径
        # 例如: /static/cocktail/images/57_cuba_libre.jpg -> app/static/cocktail/images/57_cuba_libre.jpg
        if relative_path.startswith('/static/'):
            file_path = relative_path.replace('/static/', '')
        else:
            file_path = relative_path.lstrip('/')
        
        # 构建完整路径
        static_dir = os.path.join(current_app.root_path, 'static')
        original_path = os.path.join(static_dir, file_path)
        
        # 检查原图是否存在
        if not os.path.exists(original_path):
            return None
        
        # 生成缩略图文件名
        # 使用原图路径+尺寸的hash作为缩略图名称，避免重复生成
        path_hash = hashlib.md5(f"{file_path}_{size}".encode()).hexdigest()[:8]
        filename = Path(original_path).stem
        ext = Path(original_path).suffix
        thumb_filename = f"{filename}_thumb{size}_{path_hash}{ext}"
        
        # 缩略图保存目录：static/cocktail/thumbnails/
        thumb_dir = os.path.join(static_dir, 'cocktail', 'thumbnails')
        os.makedirs(thumb_dir, exist_ok=True)
        
        thumb_path = os.path.join(thumb_dir, thumb_filename)
        thumb_relative = f"/static/cocktail/thumbnails/{thumb_filename}"
        
        # 如果缩略图已存在，直接返回
        if os.path.exists(thumb_path):
            return thumb_relative
        
        # 生成缩略图
        with Image.open(original_path) as img:
            # 转换为RGB（处理RGBA等格式）
            if img.mode in ('RGBA', 'LA', 'P'):
                # 创建白色背景
                background = Image.new('RGB', img.size, (255, 255, 255))
                if img.mode == 'P':
                    img = img.convert('RGBA')
                background.paste(img, mask=img.split()[-1] if img.mode in ('RGBA', 'LA') else None)
                img = background
            elif img.mode != 'RGB':
                img = img.convert('RGB')
            
            # 计算缩略图尺寸（保持宽高比）
            aspect = img.height / img.width
            new_width = size
            new_height = int(size * aspect)
            
            # 缩放
            img_resized = img.resize((new_width, new_height), Image.LANCZOS)
            
            # 保存缩略图
            img_resized.save(thumb_path, 'JPEG', quality=quality, optimize=True)
        
        return thumb_relative
    
    except Exception as e:
        # 记录错误但不中断流程
        current_app.logger.warning(f"Failed to generate thumbnail for {image_url}: {e}")
        return None


def get_or_generate_thumbnail(image_url: str, size: int = 100) -> Optional[str]:
    """
    获取或生成缩略图URL
    
    如果缩略图不存在则生成，存在则直接返回
    
    Args:
        image_url: 原图URL
        size: 缩略图尺寸
    
    Returns:
        缩略图URL（相对路径）
    """
    return generate_thumbnail(image_url, size=size)
