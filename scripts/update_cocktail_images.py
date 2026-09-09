#!/usr/bin/env python3
"""
更新数据库中鸡尾酒的图片URL
从CSV文件中读取图片路径并更新到数据库
"""
import os
import sys
import csv
import argparse
from pathlib import Path

# 添加项目根目录到Python路径
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))

from app import create_app
from app.models.cocktail import Cocktail
from app.extensions import db


def update_cocktail_images(csv_path: str, dry_run: bool = False):
    """
    从CSV文件读取图片路径并更新数据库
    
    Args:
        csv_path: CSV文件路径
        dry_run: 如果为True，只打印将要更新的数据，不实际更新数据库
    """
    app = create_app()
    
    with app.app_context():
        # 读取CSV文件
        print(f"正在读取CSV文件: {csv_path}")
        updates = []
        
        with open(csv_path, 'r', encoding='utf-8-sig') as f:
            reader = csv.DictReader(f)
            for row in reader:
                cocktail_id = int(row['id'])
                output_image = row['output_image']  # 格式: output/images/1087_salty_swede.jpg
                
                # 提取文件名
                if output_image and output_image.startswith('output/images/'):
                    filename = output_image.replace('output/images/', '')
                    # 生成静态资源URL
                    image_url = f"/static/cocktail/images/{filename}"
                    updates.append({
                        'id': cocktail_id,
                        'image_url': image_url,
                        'name': row['name'],
                        'name_zh': row['name_zh']
                    })
        
        print(f"从CSV中读取到 {len(updates)} 条记录")
        
        if dry_run:
            print("\n=== DRY RUN 模式 - 不会实际更新数据库 ===")
            print("前10条示例:")
            for item in updates[:10]:
                print(f"  ID {item['id']}: {item['name']} ({item['name_zh']}) -> {item['image_url']}")
            print(f"... 共 {len(updates)} 条记录")
            return
        
        # 批量更新数据库
        print("\n开始更新数据库...")
        success_count = 0
        not_found_count = 0
        error_count = 0
        
        for item in updates:
            try:
                cocktail = Cocktail.query.filter_by(id=item['id']).first()
                if cocktail:
                    cocktail.image_url = item['image_url']
                    success_count += 1
                    if success_count % 100 == 0:
                        print(f"  已更新 {success_count} 条记录...")
                else:
                    not_found_count += 1
                    print(f"  警告: 未找到ID为 {item['id']} 的鸡尾酒")
            except Exception as e:
                error_count += 1
                print(f"  错误: 更新ID {item['id']} 时出错: {e}")
        
        # 提交事务
        try:
            db.session.commit()
            print(f"\n✓ 数据库更新完成!")
            print(f"  成功更新: {success_count} 条")
            print(f"  未找到: {not_found_count} 条")
            print(f"  错误: {error_count} 条")
        except Exception as e:
            db.session.rollback()
            print(f"\n✗ 数据库提交失败: {e}")
            return False
        
        return True


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description='更新数据库中鸡尾酒的图片URL')
    parser.add_argument('--dry-run', action='store_true', help='预览模式，不实际更新数据库')
    parser.add_argument('--execute', action='store_true', help='直接执行更新，不需要确认')
    args = parser.parse_args()
    
    csv_path = project_root / "app/static/cocktail/output_manifest_noimg - Sheet1.csv"
    
    # 检查CSV文件是否存在
    if not csv_path.exists():
        print(f"错误: CSV文件不存在: {csv_path}")
        sys.exit(1)
    
    # 检查图片目录是否存在
    images_dir = project_root / "app/static/cocktail/images"
    if not images_dir.exists():
        print(f"警告: 图片目录不存在: {images_dir}")
        print("请先解压图片zip文件")
        sys.exit(1)
    
    # 统计图片数量
    image_count = len(list(images_dir.glob("*.jpg")))
    print(f"图片目录中有 {image_count} 个JPG文件")
    
    if args.dry_run:
        # 仅预览模式
        print("\n预览模式 (Dry Run)")
        print("=" * 60)
        update_cocktail_images(str(csv_path), dry_run=True)
    elif args.execute:
        # 直接执行更新
        print("\n执行实际更新")
        print("=" * 60)
        update_cocktail_images(str(csv_path), dry_run=False)
    else:
        # 默认：先预览，再询问
        print("\n第一步: 预览将要更新的数据 (Dry Run)")
        print("=" * 60)
        update_cocktail_images(str(csv_path), dry_run=True)
        
        # 询问是否继续
        print("\n" + "=" * 60)
        try:
            response = input("\n是否继续执行实际更新? (yes/no): ").strip().lower()
            
            if response in ['yes', 'y']:
                print("\n第二步: 执行实际更新")
                print("=" * 60)
                update_cocktail_images(str(csv_path), dry_run=False)
            else:
                print("已取消更新")
        except EOFError:
            print("\n非交互式环境，请使用 --execute 参数直接执行更新")
            print("或使用 --dry-run 参数仅预览")
            sys.exit(1)
