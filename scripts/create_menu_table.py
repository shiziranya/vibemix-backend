#!/usr/bin/env python3
"""
酒单功能 - 数据库表创建脚本

使用方法：
    python scripts/create_menu_table.py

说明：
    该脚本会创建 user_saved_cocktails 表和相关索引
"""

import sys
import os

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from app import create_app
from app.extensions import db


def create_menu_table():
    """创建酒单功能所需的数据库表和索引"""
    app = create_app()
    
    with app.app_context():
        print("正在创建酒单功能数据表...")
        
        # 创建表的 SQL
        table_sql = """
        CREATE TABLE IF NOT EXISTS user_saved_cocktails (
            id SERIAL PRIMARY KEY,
            user_id UUID NOT NULL REFERENCES users(id) ON DELETE CASCADE,
            cocktail_id INTEGER NOT NULL REFERENCES cocktails(id) ON DELETE CASCADE,
            is_in_today BOOLEAN NOT NULL DEFAULT FALSE,
            plan_date DATE,
            priority SMALLINT NOT NULL DEFAULT 0,
            personal_note TEXT,
            added_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
            updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
            CONSTRAINT uq_user_cocktail UNIQUE (user_id, cocktail_id)
        );
        """
        
        # 创建索引
        index_sqls = [
            # 用户收藏查询索引
            """
            CREATE INDEX IF NOT EXISTS idx_saved_cocktails_user 
            ON user_saved_cocktails(user_id, added_at DESC);
            """,
            # 今日酒单查询索引
            """
            CREATE INDEX IF NOT EXISTS idx_saved_cocktails_today 
            ON user_saved_cocktails(user_id, is_in_today, plan_date) 
            WHERE is_in_today = TRUE;
            """,
            # 过期酒单清理索引
            """
            CREATE INDEX IF NOT EXISTS idx_saved_cocktails_plan_date 
            ON user_saved_cocktails(plan_date) 
            WHERE is_in_today = TRUE AND plan_date IS NOT NULL;
            """
        ]
        
        try:
            # 创建表
            db.session.execute(db.text(table_sql))
            print("✓ 表创建成功：user_saved_cocktails")
            
            # 创建索引
            for idx_sql in index_sqls:
                db.session.execute(db.text(idx_sql))
            print("✓ 索引创建成功（3个索引）")
            
            db.session.commit()
            
            # 验证表
            verify_sql = """
            SELECT 
                table_name,
                column_name,
                data_type,
                is_nullable
            FROM information_schema.columns
            WHERE table_name = 'user_saved_cocktails'
            ORDER BY ordinal_position;
            """
            result = db.session.execute(db.text(verify_sql))
            columns = result.fetchall()
            
            if columns:
                print(f"\n✓ 表验证成功，共 {len(columns)} 个字段：")
                for col in columns:
                    print(f"  - {col[1]}: {col[2]} (nullable: {col[3]})")
            else:
                print("⚠ 警告：无法验证表是否创建成功")
                
            # 验证索引
            verify_index_sql = """
            SELECT indexname, indexdef
            FROM pg_indexes
            WHERE tablename = 'user_saved_cocktails'
            ORDER BY indexname;
            """
            result = db.session.execute(db.text(verify_index_sql))
            indexes = result.fetchall()
            
            if indexes:
                print(f"\n✓ 索引验证成功，共 {len(indexes)} 个索引：")
                for idx in indexes:
                    print(f"  - {idx[0]}")
                    
        except Exception as e:
            db.session.rollback()
            print(f"✗ 创建失败: {e}")
            return False
            
    return True


if __name__ == "__main__":
    print("=" * 60)
    print("酒单功能 - 数据库表创建")
    print("=" * 60)
    
    success = create_menu_table()
    
    if success:
        print("\n✓ 数据表创建完成！")
        print("\n功能说明：")
        print("- 收藏夹：保存喜欢的鸡尾酒配方")
        print("- 今日酒单：标记今天要做的酒")
        print("- 支持个人笔记和优先级排序")
    else:
        print("\n✗ 数据表创建失败，请检查数据库连接和权限")
        sys.exit(1)
