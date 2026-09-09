#!/usr/bin/env python3
"""
测试推荐 API 返回的完整字段（包括中文映射）
"""
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))

from app import create_app
from app.services.recommend_service import recommend_service

app = create_app()


def print_section(title: str):
    print("\n" + "=" * 70)
    print(f"  {title}")
    print("=" * 70)


def main():
    print_section("推荐 API 返回字段测试（含中文映射）")
    
    with app.app_context():
        # 模拟一个推荐请求
        user_id = "00000000-0000-0000-0000-000000000001"  # 测试用户
        prefs = {
            "flavor_tags": ["sweet", "fruity"],
            "abv_pref": "medium",
            "recipe_type": "classic",
        }
        
        try:
            result = recommend_service.recommend(user_id=user_id, prefs=prefs)
            
            print("\n### 完整返回数据")
            print("-" * 70)
            print(json.dumps(result, ensure_ascii=False, indent=2))
            
            print_section("字段说明")
            
            cocktail = result.get("cocktail", {})
            
            print("\n### 基本信息")
            print(f"  配方ID: {cocktail.get('id')}")
            print(f"  英文名: {cocktail.get('name')}")
            print(f"  中文名: {cocktail.get('name_zh')}")
            print(f"  难度: {cocktail.get('difficulty')}")
            
            print("\n### 枚举字段（英文 + 中文）")
            print(f"  酒精度 (英文): {cocktail.get('abv_level')}")
            print(f"  酒精度 (中文): {cocktail.get('abv_level_zh')}")
            print()
            print(f"  杯型 (英文): {cocktail.get('glass_type')}")
            print(f"  杯型 (中文): {cocktail.get('glass_type_zh')}")
            print()
            print(f"  口味标签 (英文): {cocktail.get('flavor_tags')}")
            print(f"  口味标签 (中文): {cocktail.get('flavor_tags_zh')}")
            print()
            print(f"  心情标签 (英文): {cocktail.get('mood_tags')}")
            print(f"  心情标签 (中文): {cocktail.get('mood_tags_zh')}")
            
            print("\n### AI 生成内容")
            ai = result.get("ai", {})
            print(f"  推荐理由: {ai.get('reason')[:50]}...")
            print(f"  诗意文案: {ai.get('poetic_copy')[:50]}...")
            print(f"  心情描述: {ai.get('mood_caption')}")
            
            print("\n### 配料列表")
            ingredients = result.get("ingredients", [])
            print(f"  共 {len(ingredients)} 种配料")
            for ing in ingredients[:3]:
                print(f"    - {ing.get('name_zh')}: {ing.get('measure')} ({ing.get('status')})")
            
            print("\n### 步骤")
            steps = result.get("steps", [])
            print(f"  共 {len(steps)} 个步骤")
            
            print_section("前端使用建议")
            print("""
1. **显示时优先使用中文字段**
   - 使用 abv_level_zh、flavor_tags_zh、glass_type_zh 等
   
2. **逻辑判断时使用英文字段**
   - if (abv_level === 'high') { ... }
   - filter(tag => tag === 'sweet')
   
3. **字段对照表**
   
   | 字段名           | 类型    | 英文字段      | 中文字段         |
   |------------------|---------|---------------|------------------|
   | 酒精度级别       | string  | abv_level     | abv_level_zh     |
   | 杯型             | string  | glass_type    | glass_type_zh    |
   | 口味标签         | array   | flavor_tags   | flavor_tags_zh   |
   | 心情标签         | array   | mood_tags     | mood_tags_zh     |

4. **示例代码**

```javascript
const { cocktail } = recommendData;

// ✅ 显示用中文
<div>
  <span>酒精度: {cocktail.abv_level_zh}</span>
  <span>杯型: {cocktail.glass_type_zh}</span>
  {cocktail.flavor_tags_zh.map(tag => (
    <Tag key={tag}>{tag}</Tag>
  ))}
</div>

// ✅ 逻辑判断用英文
if (cocktail.abv_level === 'high') {
  showWarning('高度酒精');
}

const hasSweet = cocktail.flavor_tags.includes('sweet');
```
""")
            
        except Exception as e:
            print(f"\n❌ 测试失败: {e}")
            import traceback
            traceback.print_exc()
            return
    
    print_section("测试完成")
    print("\n✅ 推荐 API 现在同时返回英文和中文字段！")
    print("   - 英文字段: 用于逻辑判断")
    print("   - 中文字段: 用于界面显示\n")


if __name__ == "__main__":
    main()
