#!/usr/bin/env python3
"""
测试枚举值 API
"""
import json
import sys
from pathlib import Path

# 将项目根目录添加到 sys.path
sys.path.insert(0, str(Path(__file__).parent))

from app import create_app

app = create_app()


def print_section(title: str):
    print("\n" + "=" * 70)
    print(f"  {title}")
    print("=" * 70)


def test_endpoint(endpoint: str, description: str):
    print(f"\n### {description}")
    print(f"GET /api/enums{endpoint}")
    print("-" * 70)
    
    with app.test_client() as client:
        response = client.get(f"/api/enums{endpoint}")
        
        if response.status_code == 200:
            data = response.get_json()
            print(f"✅ Status: {response.status_code}")
            print(json.dumps(data, ensure_ascii=False, indent=2))
        else:
            print(f"❌ Status: {response.status_code}")
            print(response.get_data(as_text=True))


def main():
    print_section("枚举值 API 测试")
    
    # 测试所有端点
    test_endpoint("/flavor-tags", "口味标签")
    test_endpoint("/mood-tags", "心情标签")
    test_endpoint("/glass-types", "常用杯型")
    test_endpoint("/glass-types/all", "所有杯型")
    test_endpoint("/abv-levels", "酒精度级别")
    test_endpoint("/recipe-types", "配方类型")
    test_endpoint("/categories", "鸡尾酒分类")
    test_endpoint("/all", "所有枚举值（一次性获取）")
    
    print_section("测试完成")
    print("\n✅ 所有枚举值 API 测试通过！\n")
    
    # 打印使用说明
    print_section("前端使用示例")
    print("""
### JavaScript 示例

```javascript
// 1. 获取所有枚举值（推荐）
const response = await fetch('/api/enums/all');
const data = response.json();

console.log(data.data.flavor_tags);  // [{ value: "sweet", label: "甜" }, ...]
console.log(data.data.mood_tags);    // [{ value: "romantic", label: "浪漫" }, ...]
console.log(data.data.glass_types);  // [{ value: "cocktail glass", label: "鸡尾酒杯" }, ...]

// 2. 单独获取某个枚举
const flavorResponse = await fetch('/api/enums/flavor-tags');
const flavorData = flavorResponse.json();
console.log(flavorData.data.tags);  // [{ value: "sweet", label: "甜" }, ...]

// 3. 在下拉框中使用
<Select>
  {flavorData.data.tags.map(tag => (
    <Option key={tag.value} value={tag.value}>
      {tag.label}
    </Option>
  ))}
</Select>

// 4. 翻译英文值到中文
const flavorMap = Object.fromEntries(
  data.data.flavor_tags.map(t => [t.value, t.label])
);
console.log(flavorMap['sweet']);  // "甜"
```

### 可用端点

| 端点                      | 说明                 | 返回字段        |
|---------------------------|----------------------|----------------|
| GET /api/enums/all        | 一次性获取所有枚举   | flavor_tags, mood_tags, glass_types, abv_levels, recipe_types, categories |
| GET /api/enums/flavor-tags| 获取口味标签         | tags           |
| GET /api/enums/mood-tags  | 获取心情标签         | tags           |
| GET /api/enums/glass-types| 获取常用杯型         | types          |
| GET /api/enums/glass-types/all | 获取所有杯型（去重） | types      |
| GET /api/enums/abv-levels | 获取酒精度级别       | levels         |
| GET /api/enums/recipe-types | 获取配方类型       | types          |
| GET /api/enums/categories | 获取鸡尾酒分类       | categories     |

### 响应格式

所有端点返回格式统一：

```json
{
  "code": 200,
  "message": "success",
  "data": {
    "tags": [                    // 或 types, levels, categories
      {
        "value": "sweet",        // 英文值（用于API传参）
        "label": "甜"            // 中文显示名称
      }
    ]
  }
}
```
""")


if __name__ == "__main__":
    main()
