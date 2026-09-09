#!/usr/bin/env python
"""
验证缩略图功能

快速测试缩略图生成是否正常工作
"""
import os
import sys

# 添加项目路径
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from app import create_app
from app.services.map_service import map_service
from sqlalchemy import text
from app.extensions import db


def verify_thumbnails():
    """验证缩略图功能"""
    app = create_app()
    
    with app.app_context():
        print("=" * 80)
        print("缩略图功能验证")
        print("=" * 80)
        
        # 1. 查询第一个主题
        theme = db.session.execute(
            text("SELECT id, slug, name_zh FROM map_themes WHERE is_active ORDER BY sort_order LIMIT 1")
        ).fetchone()
        
        if not theme:
            print("❌ 没有找到活跃的主题")
            return False
        
        print(f"\n✓ 找到主题: {theme.name_zh} (ID: {theme.id})")
        
        # 2. 查询第一个用户
        user = db.session.execute(
            text("SELECT id FROM users LIMIT 1")
        ).fetchone()
        
        if not user:
            print("❌ 没有找到用户")
            return False
        
        print(f"✓ 找到用户: {user.id}")
        
        # 3. 获取主题图谱数据
        print(f"\n正在获取主题图谱数据...")
        data = map_service.get_theme_graph(theme.id, str(user.id))
        
        if not data:
            print("❌ 获取主题图谱数据失败")
            return False
        
        print(f"✓ 成功获取主题图谱数据")
        
        # 4. 检查节点缩略图
        nodes = data.get('nodes', [])
        print(f"\n节点总数: {len(nodes)}")
        
        if not nodes:
            print("⚠ 没有节点数据")
            return True
        
        # 统计缩略图
        with_thumbnail = sum(1 for n in nodes if n.get('thumbnail_url'))
        without_thumbnail = len(nodes) - with_thumbnail
        
        print(f"✓ 有缩略图的节点: {with_thumbnail}")
        print(f"⚠ 无缩略图的节点: {without_thumbnail}")
        
        # 5. 检查缩略图目录
        thumb_dir = os.path.join(app.root_path, 'static', 'cocktail', 'thumbnails')
        if os.path.exists(thumb_dir):
            thumb_count = len([f for f in os.listdir(thumb_dir) if f.endswith('.jpg')])
            thumb_size = sum(
                os.path.getsize(os.path.join(thumb_dir, f))
                for f in os.listdir(thumb_dir)
                if f.endswith('.jpg')
            )
            print(f"\n缩略图目录: {thumb_dir}")
            print(f"✓ 缩略图文件数: {thumb_count}")
            print(f"✓ 总大小: {thumb_size / 1024:.1f} KB")
        else:
            print(f"\n⚠ 缩略图目录不存在: {thumb_dir}")
        
        # 6. 显示示例节点
        print(f"\n示例节点 (前3个):")
        print("-" * 80)
        for i, node in enumerate(nodes[:3]):
            print(f"\n节点 {i+1}:")
            print(f"  ID: {node.get('id')}")
            print(f"  名称: {node.get('display_name_zh')}")
            print(f"  原图: {node.get('image_url')}")
            print(f"  缩略图: {node.get('thumbnail_url')}")
            
            # 检查缩略图文件是否存在
            if node.get('thumbnail_url'):
                thumb_path = node['thumbnail_url'].replace('http://115.191.50.177:5005', '')
                full_path = os.path.join(app.root_path, thumb_path.lstrip('/'))
                if os.path.exists(full_path):
                    size = os.path.getsize(full_path)
                    print(f"  ✓ 文件存在，大小: {size / 1024:.1f} KB")
                else:
                    print(f"  ❌ 文件不存在: {full_path}")
        
        print("\n" + "=" * 80)
        print("验证完成")
        print("=" * 80)
        
        return with_thumbnail > 0


if __name__ == "__main__":
    try:
        success = verify_thumbnails()
        sys.exit(0 if success else 1)
    except Exception as e:
        print(f"\n❌ 验证失败: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)
