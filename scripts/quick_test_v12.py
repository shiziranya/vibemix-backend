#!/usr/bin/env python3
"""快速测试推荐历史接口 v1.2"""
import sys
import os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))

from app import create_app
from app.extensions import db
from sqlalchemy import text

def test_history_query():
    """测试历史查询功能"""
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
                print("⚠️  数据库中没有推荐历史记录，无法测试")
                print("提示: 先发起一次推荐来创建测试数据")
                return False
            
            user_id = result[0]
            print(f"✓ 找到测试用户: {user_id}")
            
            # 导入 recommend_service 来测试新方法
            from app.services.recommend_service import recommend_service
            
            # 调用 get_history 方法
            history_data = recommend_service.get_history(str(user_id), page=1, per_page=3)
            
            print(f"\n✓ 成功调用 get_history 方法")
            print(f"  - 总记录数: {history_data['total']}")
            print(f"  - 当前页: {history_data['page']}")
            print(f"  - 每页数量: {history_data['per_page']}")
            print(f"  - 总页数: {history_data['total_pages']}")
            print(f"  - 返回记录: {len(history_data['items'])} 条")
            
            if len(history_data['items']) > 0:
                item = history_data['items'][0]
                print(f"\n✓ 第一条记录格式检查:")
                
                # 检查关键字段
                checks = []
                
                # 1. 检查 ingredients 是否在顶层
                if 'ingredients' in item:
                    checks.append(("✅", "ingredients 在顶层"))
                else:
                    checks.append(("❌", "ingredients 字段缺失"))
                
                # 2. 检查 cocktail 是否不包含 ingredients
                if 'cocktail' in item:
                    if 'ingredients' not in item['cocktail']:
                        checks.append(("✅", "cocktail 不包含 ingredients"))
                    else:
                        checks.append(("❌", "cocktail 仍包含 ingredients（应该移除）"))
                
                # 3. 检查 ai 是否包含 mood_caption
                if 'ai' in item and 'mood_caption' in item['ai']:
                    mood_caption = item['ai']['mood_caption'] or '(空)'
                    checks.append(("✅", f"ai.mood_caption 存在: {mood_caption}"))
                else:
                    checks.append(("❌", "ai.mood_caption 缺失"))
                
                # 4. 检查 ingredients 是否包含 status
                if 'ingredients' in item and len(item['ingredients']) > 0:
                    ing = item['ingredients'][0]
                    if 'status' in ing:
                        checks.append(("✅", f"ingredients[0].status = {ing['status']}"))
                    else:
                        checks.append(("❌", "ingredients[0].status 缺失"))
                    
                    if 'substitute' in ing:
                        checks.append(("✅", f"ingredients[0].substitute 存在"))
                    else:
                        checks.append(("❌", "ingredients[0].substitute 缺失"))
                
                for icon, msg in checks:
                    print(f"  {icon} {msg}")
                
                # 显示详细信息
                print(f"\n详细信息:")
                print(f"  - 鸡尾酒: {item.get('cocktail', {}).get('name_zh', 'N/A')}")
                print(f"  - 原料数量: {len(item.get('ingredients', []))}")
                print(f"  - 推荐理由: {item.get('ai', {}).get('reason', '')[:50]}...")
                
                # 统计原料状态
                if item.get('ingredients'):
                    status_count = {}
                    for ing in item['ingredients']:
                        status = ing.get('status', 'unknown')
                        status_count[status] = status_count.get(status, 0) + 1
                    print(f"  - 原料状态分布: {status_count}")
                
                # 判断是否全部通过
                all_passed = all(icon == "✅" for icon, _ in checks)
                if all_passed:
                    print(f"\n🎉 所有检查通过！v1.2 格式正确")
                    return True
                else:
                    print(f"\n⚠️  部分检查未通过，请检查代码")
                    return False
            else:
                print("⚠️  返回的记录为空")
                return False
                
        except Exception as e:
            print(f"❌ 测试失败: {e}")
            import traceback
            traceback.print_exc()
            return False

if __name__ == "__main__":
    success = test_history_query()
    sys.exit(0 if success else 1)
