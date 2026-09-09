#!/usr/bin/env python3
"""测试鸡尾酒名字结构 - 验证 name 在 cocktail 对象中，而不是 ai 对象中"""
import sys
import os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))

from app import create_app
from app.extensions import db
from sqlalchemy import text

def test_structure():
    """测试推荐历史接口的数据结构"""
    app = create_app()
    
    with app.app_context():
        try:
            # 查询一个有推荐历史的用户
            result = db.session.execute(
                text("""
                    SELECT DISTINCT user_id 
                    FROM recommendation_history 
                    WHERE cocktail_id IS NOT NULL
                    LIMIT 1
                """)
            ).first()
            
            if not result:
                print("⚠️  数据库中没有推荐历史记录")
                return False
            
            user_id = result[0]
            print(f"✓ 测试用户: {user_id}")
            
            # 导入 recommend_service
            from app.services.recommend_service import recommend_service
            
            # 调用 get_history 方法
            history_data = recommend_service.get_history(str(user_id), page=1, per_page=1)
            
            if len(history_data['items']) == 0:
                print("⚠️  没有历史记录")
                return False
            
            item = history_data['items'][0]
            
            print(f"\n✓ 数据结构检查:")
            
            # 检查 cocktail 对象
            if 'cocktail' not in item:
                print("  ❌ 缺少 cocktail 对象")
                return False
            
            cocktail = item['cocktail']
            
            # 检查 cocktail.name 存在
            if 'name' not in cocktail:
                print("  ❌ cocktail 缺少 name 字段")
                return False
            else:
                print(f"  ✅ cocktail.name = '{cocktail['name']}'")
            
            if 'name_zh' not in cocktail:
                print("  ❌ cocktail 缺少 name_zh 字段")
                return False
            else:
                print(f"  ✅ cocktail.name_zh = '{cocktail['name_zh']}'")
            
            # 检查 ai 对象
            if 'ai' not in item:
                print("  ❌ 缺少 ai 对象")
                return False
            
            ai = item['ai']
            
            # 检查 ai 对象不应该包含 cocktail_name
            if 'cocktail_name' in ai:
                print(f"  ❌ ai 对象不应该包含 cocktail_name 字段（当前值: {ai['cocktail_name']}）")
                return False
            else:
                print("  ✅ ai 对象不包含 cocktail_name")
            
            if 'cocktail_name_zh' in ai:
                print(f"  ❌ ai 对象不应该包含 cocktail_name_zh 字段（当前值: {ai['cocktail_name_zh']}）")
                return False
            else:
                print("  ✅ ai 对象不包含 cocktail_name_zh")
            
            if 'prototype_name' in ai:
                print(f"  ❌ ai 对象不应该包含 prototype_name 字段（当前值: {ai['prototype_name']}）")
                return False
            else:
                print("  ✅ ai 对象不包含 prototype_name")
            
            if 'prototype_name_zh' in ai:
                print(f"  ❌ ai 对象不应该包含 prototype_name_zh 字段（当前值: {ai['prototype_name_zh']}）")
                return False
            else:
                print("  ✅ ai 对象不包含 prototype_name_zh")
            
            # 检查 ai 应该包含的字段
            required_ai_fields = ['reason', 'poetic_copy', 'mood_caption', 'tweaks']
            for field in required_ai_fields:
                if field not in ai:
                    print(f"  ❌ ai 缺少 {field} 字段")
                    return False
            
            print(f"  ✅ ai 对象包含所有必需字段: {required_ai_fields}")
            
            print(f"\n🎉 结构检查通过！")
            print(f"\n数据示例:")
            print(f"  - 鸡尾酒名字: {cocktail.get('name')} / {cocktail.get('name_zh')}")
            print(f"  - AI 文案: {ai.get('reason', '')[:50]}...")
            
            return True
                
        except Exception as e:
            print(f"❌ 测试失败: {e}")
            import traceback
            traceback.print_exc()
            return False

if __name__ == "__main__":
    success = test_structure()
    sys.exit(0 if success else 1)
