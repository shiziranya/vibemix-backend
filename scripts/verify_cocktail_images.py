#!/usr/bin/env python3
"""
验证鸡尾酒图片URL是否正确更新
"""
import sys
from pathlib import Path

# 添加项目根目录到Python路径
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))

from app import create_app
from app.models.cocktail import Cocktail


def verify_images():
    """验证数据库中的图片URL"""
    app = create_app()
    
    with app.app_context():
        # 查询所有有图片的鸡尾酒
        cocktails_with_images = Cocktail.query.filter(
            Cocktail.image_url.isnot(None)
        ).all()
        
        print(f"数据库中有 {len(cocktails_with_images)} 条鸡尾酒有图片URL")
        
        # 显示前10条
        print("\n前10条记录:")
        print("-" * 80)
        for c in cocktails_with_images[:10]:
            print(f"ID: {c.id:4d} | {c.name:30s} | {c.name_zh:15s} | {c.image_url}")
        
        # 统计图片URL格式
        static_count = sum(1 for c in cocktails_with_images if c.image_url and c.image_url.startswith('/static/cocktail/images/'))
        print(f"\n统计:")
        print(f"  以 /static/cocktail/images/ 开头的: {static_count} 条")
        
        # 检查图片文件是否存在
        images_dir = project_root / "app/static/cocktail/images"
        missing_files = []
        
        for c in cocktails_with_images:
            if c.image_url and c.image_url.startswith('/static/cocktail/images/'):
                filename = c.image_url.replace('/static/cocktail/images/', '')
                filepath = images_dir / filename
                if not filepath.exists():
                    missing_files.append({
                        'id': c.id,
                        'name': c.name,
                        'file': filename
                    })
        
        if missing_files:
            print(f"\n⚠ 警告: 有 {len(missing_files)} 个图片文件不存在:")
            for item in missing_files[:5]:
                print(f"  ID {item['id']}: {item['name']} - {item['file']}")
            if len(missing_files) > 5:
                print(f"  ... 还有 {len(missing_files) - 5} 个文件")
        else:
            print(f"\n✓ 所有图片文件都存在!")


if __name__ == "__main__":
    verify_images()
