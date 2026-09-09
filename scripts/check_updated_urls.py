#!/usr/bin/env python3
"""
检查最近更新的鸡尾酒图片URL
"""
import sys
from pathlib import Path

# 添加项目根目录到Python路径
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))

from app import create_app
from app.models.cocktail import Cocktail


def check_updated_urls():
    """检查那219条更新的记录"""
    app = create_app()
    
    with app.app_context():
        # 查询那些有/static/cocktail/images/路径的记录
        cocktails = Cocktail.query.filter(
            Cocktail.image_url.like('/static/cocktail/images/%')
        ).order_by(Cocktail.id).all()
        
        print(f"找到 {len(cocktails)} 条使用新图片路径的记录\n")
        
        print("前20条记录:")
        print("-" * 100)
        print(f"{'ID':<6} {'Name':<35} {'中文名':<20} {'Image URL':<40}")
        print("-" * 100)
        
        for c in cocktails[:20]:
            print(f"{c.id:<6} {c.name[:34]:<35} {(c.name_zh or '')[:19]:<20} {c.image_url[:39]:<40}")
        
        if len(cocktails) > 20:
            print(f"... 还有 {len(cocktails) - 20} 条记录")


if __name__ == "__main__":
    check_updated_urls()
