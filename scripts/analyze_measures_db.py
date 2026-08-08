#!/usr/bin/env python3
"""从数据库分析 measure_raw 数据"""

import os
import sys
from collections import Counter

# 添加项目根目录到路径
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))

from sqlalchemy import create_engine, text

def main():
    db_url = os.getenv('SUPABASE_DATABASE_URL', 'postgresql://postgres:postgres123@localhost:5432/tipsy_inspirations')
    engine = create_engine(db_url)
    
    with engine.connect() as conn:
        # 查询所有 measure_raw
        result = conn.execute(text("""
            SELECT measure_raw, COUNT(*) as count
            FROM cocktail_ingredients
            WHERE measure_raw IS NOT NULL
            GROUP BY measure_raw
            ORDER BY count DESC
        """))
        
        rows = result.fetchall()
        
        print(f"总共找到 {len(rows)} 种不同的用量格式\n")
        print("=" * 80)
        print("出现频次最高的 measure_raw 值：\n")
        
        for row in rows[:50]:
            print(f"{row.count:4d}x  {row.measure_raw}")
        
        print("\n" + "=" * 80)
        
        # 按单位分类统计
        oz_count = sum(1 for r in rows if 'oz' in r.measure_raw.lower())
        ml_count = sum(1 for r in rows if 'ml' in r.measure_raw.lower())
        dash_count = sum(1 for r in rows if 'dash' in r.measure_raw.lower())
        cl_count = sum(1 for r in rows if 'cl' in r.measure_raw.lower())
        
        print(f"\n单位统计:")
        print(f"  包含 'oz': {oz_count} 种")
        print(f"  包含 'ml': {ml_count} 种")
        print(f"  包含 'dash': {dash_count} 种")
        print(f"  包含 'cl': {cl_count} 种")

if __name__ == '__main__':
    main()
