#!/usr/bin/env python3
"""验证数据库表结构是否包含新字段"""
import sys
import os

# 添加项目路径
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))

from sqlalchemy import text
from app.extensions import db
from app import create_app


def verify_schema():
    """验证 recommendation_history 表是否包含 ai_mood_caption 字段"""
    app = create_app()
    
    with app.app_context():
        try:
            # 查询表结构
            result = db.session.execute(
                text("""
                    SELECT column_name, data_type, is_nullable
                    FROM information_schema.columns
                    WHERE table_name = 'recommendation_history'
                      AND table_schema = 'public'
                    ORDER BY ordinal_position
                """)
            ).fetchall()
            
            print("✓ recommendation_history 表字段列表:")
            print("-" * 70)
            
            has_ai_mood_caption = False
            for row in result:
                column_name, data_type, is_nullable = row
                nullable = "NULL" if is_nullable == "YES" else "NOT NULL"
                print(f"  {column_name:30s} {data_type:20s} {nullable}")
                
                if column_name == "ai_mood_caption":
                    has_ai_mood_caption = True
            
            print("-" * 70)
            
            if has_ai_mood_caption:
                print("\n✅ ai_mood_caption 字段已存在")
                return True
            else:
                print("\n❌ ai_mood_caption 字段不存在")
                print("\n请运行迁移脚本:")
                print("  psql -U your_user -d your_database -f migrations/011_add_ai_mood_caption.sql")
                return False
                
        except Exception as e:
            print(f"❌ 查询失败: {e}")
            return False


if __name__ == "__main__":
    success = verify_schema()
    sys.exit(0 if success else 1)
