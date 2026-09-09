#!/usr/bin/env python3
"""
批量调整cards目录中图片的宽度为750px，保持宽高比
"""
import os
from pathlib import Path
from PIL import Image
import sys

# 目标宽度
TARGET_WIDTH = 750

# cards目录路径
CARDS_DIR = Path(__file__).parent / "app" / "static" / "cards"

def resize_image(image_path, target_width=TARGET_WIDTH):
    """
    调整图片宽度为target_width，保持宽高比
    
    Args:
        image_path: 图片路径
        target_width: 目标宽度
    """
    try:
        with Image.open(image_path) as img:
            # 获取原始尺寸
            original_width, original_height = img.size
            
            # 如果宽度已经小于等于目标宽度，跳过
            if original_width <= target_width:
                print(f"跳过 {image_path.name} - 宽度已经是 {original_width}px")
                return False
            
            # 计算新的高度以保持宽高比
            aspect_ratio = original_height / original_width
            new_height = int(target_width * aspect_ratio)
            
            # 调整大小
            resized_img = img.resize((target_width, new_height), Image.Resampling.LANCZOS)
            
            # 保存，保持原有的EXIF信息和质量
            if img.format == 'JPEG':
                resized_img.save(image_path, 'JPEG', quality=85, optimize=True)
            else:
                resized_img.save(image_path, img.format, optimize=True)
            
            # 获取文件大小
            original_size = os.path.getsize(image_path) / 1024  # KB
            print(f"✓ {image_path.name}: {original_width}x{original_height} -> {target_width}x{new_height}")
            
            return True
            
    except Exception as e:
        print(f"✗ 处理 {image_path.name} 时出错: {e}")
        return False

def main():
    print(f"开始处理cards目录中的图片...")
    print(f"目录: {CARDS_DIR}")
    print(f"目标宽度: {TARGET_WIDTH}px")
    print("-" * 60)
    
    if not CARDS_DIR.exists():
        print(f"错误: 目录不存在 {CARDS_DIR}")
        sys.exit(1)
    
    # 支持的图片格式
    image_extensions = {'.jpg', '.jpeg', '.png', '.gif', '.webp'}
    
    # 获取所有图片文件
    image_files = [
        f for f in CARDS_DIR.iterdir()
        if f.is_file() and f.suffix.lower() in image_extensions
    ]
    
    if not image_files:
        print("未找到图片文件")
        sys.exit(0)
    
    print(f"找到 {len(image_files)} 个图片文件\n")
    
    # 统计
    processed = 0
    skipped = 0
    errors = 0
    
    # 处理每个图片
    for image_file in sorted(image_files):
        result = resize_image(image_file)
        if result:
            processed += 1
        elif result is False:
            skipped += 1
        else:
            errors += 1
    
    # 输出统计
    print("-" * 60)
    print(f"\n处理完成!")
    print(f"已处理: {processed} 个")
    print(f"已跳过: {skipped} 个 (宽度已经 <= {TARGET_WIDTH}px)")
    if errors > 0:
        print(f"出错: {errors} 个")

if __name__ == "__main__":
    main()
