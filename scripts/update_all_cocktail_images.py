#!/usr/bin/env python3
"""
扫描图片目录，将所有图片地址更新到数据库
"""
import os
import sys
import re
from pathlib import Path

# 添加项目根目录到Python路径
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))

from app import create_app
from app.models.cocktail import Cocktail
from app.extensions import db


def update_all_images(dry_run: bool = False):
    """
    扫描图片目录，更新所有鸡尾酒的图片URL
    
    Args:
        dry_run: 如果为True，只打印将要更新的数据，不实际更新数据库
    """
    app = create_app()
    images_dir = project_root / "app/static/cocktail/images"
    
    # 获取所有jpg图片
    image_files = sorted(images_dir.glob("*.jpg"))
    print(f"在图片目录中找到 {len(image_files)} 个JPG文件")
    
    # 解析文件名，提取ID和名称
    image_map = {}
    for img_file in image_files:
        # 文件名格式: {id}_{name}.jpg
        match = re.match(r'^(\d+)_(.+)\.jpg$', img_file.name)
        if match:
            cocktail_id = int(match.group(1))
            image_url = f"/static/cocktail/images/{img_file.name}"
            image_map[cocktail_id] = image_url
    
    print(f"成功解析 {len(image_map)} 个图片文件名")
    
    with app.app_context():
        if dry_run:
            print("\n=== DRY RUN 模式 - 不会实际更新数据库 ===")
            print("前10条示例:")
            for i, (cocktail_id, image_url) in enumerate(list(image_map.items())[:10]):
                cocktail = Cocktail.query.filter_by(id=cocktail_id).first()
                if cocktail:
                    print(f"  ID {cocktail_id:4d}: {cocktail.name:30s} -> {image_url}")
            print(f"... 共 {len(image_map)} 条记录")
            return
        
        # 批量更新数据库
        print("\n开始更新数据库...")
        success_count = 0
        not_found_count = 0
        skipped_count = 0
        error_count = 0
        
        for cocktail_id, image_url in image_map.items():
            try:
                cocktail = Cocktail.query.filter_by(id=cocktail_id).first()
                if cocktail:
                    # 检查是否已经有本地图片路径（避免覆盖）
                    if cocktail.image_url and cocktail.image_url.startswith('/static/cocktail/images/'):
                        skipped_count += 1
                    else:
                        cocktail.image_url = image_url
                        success_count += 1
                        if success_count % 100 == 0:
                            print(f"  已更新 {success_count} 条记录...")
                else:
                    not_found_count += 1
                    if not_found_count <= 5:  # 只打印前5个
                        print(f"  警告: 未找到ID为 {cocktail_id} 的鸡尾酒")
            except Exception as e:
                error_count += 1
                print(f"  错误: 更新ID {cocktail_id} 时出错: {e}")
        
        # 提交事务
        try:
            db.session.commit()
            print(f"\n✓ 数据库更新完成!")
            print(f"  成功更新: {success_count} 条")
            print(f"  已有本地图片（跳过）: {skipped_count} 条")
            print(f"  未找到: {not_found_count} 条")
            print(f"  错误: {error_count} 条")
            print(f"  总计: {success_count + skipped_count} 条记录现在有本地图片")
        except Exception as e:
            db.session.rollback()
            print(f"\n✗ 数据库提交失败: {e}")
            return False
        
        return True


if __name__ == "__main__":
    import argparse
    
    parser = argparse.ArgumentParser(description='扫描图片目录，更新所有鸡尾酒的图片URL')
    parser.add_argument('--dry-run', action='store_true', help='预览模式，不实际更新数据库')
    parser.add_argument('--execute', action='store_true', help='直接执行更新')
    args = parser.parse_args()
    
    images_dir = project_root / "app/static/cocktail/images"
    if not images_dir.exists():
        print(f"错误: 图片目录不存在: {images_dir}")
        sys.exit(1)
    
    if args.dry_run:
        update_all_images(dry_run=True)
    elif args.execute:
        update_all_images(dry_run=False)
    else:
        # 默认：先预览，再询问
        update_all_images(dry_run=True)
        print("\n" + "=" * 80)
        try:
            response = input("\n是否继续执行实际更新? (yes/no): ").strip().lower()
            if response in ['yes', 'y']:
                print("\n执行实际更新")
                print("=" * 80)
                update_all_images(dry_run=False)
            else:
                print("已取消更新")
        except EOFError:
            print("\n非交互式环境，请使用 --execute 参数直接执行更新")
            sys.exit(1)
