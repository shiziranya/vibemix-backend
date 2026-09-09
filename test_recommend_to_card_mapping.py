#!/usr/bin/env python3
"""
测试推荐接口数据传递到卡片生成的完整性
"""

import json

# 模拟推荐接口返回的数据
RECOMMEND_RESPONSE = {
    "session_id": "sess_abc123",
    "cocktail": {
        "id": 100,
        "name": "English Rose",
        "name_zh": "英式玫瑰",
        "abv_level": "medium",
        "difficulty": 2,
        "image_url": "http://115.191.50.177:5005/static/cocktail/images/100_english_rose_cocktail.jpg",
        "mood_tags": ["浪漫", "优雅"],
        "flavor_tags": ["清新", "果香"],
        "glass_type": "cocktail"
    },
    "ai": {
        "reason": "这款酒融合了金酒的清爽和玫瑰的优雅，完美契合你想要放松的心情。",
        "poetic_copy": "优雅的玫瑰色调，伴随着清新的果香，是一款完美的夏日鸡尾酒。",
        "mood_caption": "浪漫优雅",
        "tweaks": None  # 经典模式下为 None，原创模式下会有值
    },
    "ingredients": [
        {
            "ingredient_family_id": 1,
            "ingredient_id": 10,
            "name": "Gin",
            "name_zh": "金酒",
            "measure": "45ml",
            "measure_raw": "45ml",
            "measure_ml": 45.0,
            "is_easily_available": True,
            "category": "spirits",
            "status": "owned",
            "substitute": None
        },
        {
            "ingredient_family_id": 2,
            "ingredient_id": 20,
            "name": "Rose Syrup",
            "name_zh": "玫瑰糖浆",
            "measure": "15ml",
            "measure_raw": "15ml",
            "measure_ml": 15.0,
            "is_easily_available": False,
            "category": "syrup",
            "status": "missing",
            "substitute": {"name_zh": "玫瑰露", "note": "可用玫瑰露代替"}
        }
    ],
    "steps": [
        {"order": 1, "text": "在调酒杯中加入冰块", "duration_hint": None},
        {"order": 2, "text": "倒入金酒和玫瑰糖浆", "duration_hint": "10秒"},
        {"order": 3, "text": "搅拌均匀后滤入鸡尾酒杯", "duration_hint": "15秒"}
    ]
}

# 前端应该传递给 /api/card/generate 的完整数据
CARD_GENERATE_REQUEST = {
    # 基本字段
    "cocktail_id": RECOMMEND_RESPONSE["cocktail"]["id"],
    "session_id": RECOMMEND_RESPONSE["session_id"],
    
    # AI 生成的名称（如果推荐接口有返回，前端应该传递）
    "cocktail_name": RECOMMEND_RESPONSE["cocktail"]["name"],
    "cocktail_name_zh": RECOMMEND_RESPONSE["cocktail"]["name_zh"],
    
    # AI 内容字段
    "ai_poetic": RECOMMEND_RESPONSE["ai"]["poetic_copy"],
    "ai_reason": RECOMMEND_RESPONSE["ai"]["reason"],  # ✅ 新增：推荐理由
    "mood_caption": RECOMMEND_RESPONSE["ai"]["mood_caption"],
    "ai_tweaks": RECOMMEND_RESPONSE["ai"]["tweaks"],  # ✅ 新增：调整信息（原创模式）
    
    # 原型信息（如果是原创模式，推荐接口会返回）
    "prototype_name": None,  # ✅ 新增：原型英文名
    "prototype_name_zh": None,  # ✅ 新增：原型中文名
    
    # 配料和图片
    "ingredients": RECOMMEND_RESPONSE["ingredients"],
    "use_system_image": True,
    
    # 可选字段
    "template_id": "circulus",  # 或者随机选择一个模板
}

# 原创模式的例子
ORIGINAL_MODE_RESPONSE = {
    "session_id": "sess_xyz789",
    "cocktail": {
        "id": 9999,
        "name": "Twilight Rose",  # AI 创造的新名字
        "name_zh": "暮光玫瑰",
        "abv_level": "medium",
        "difficulty": 3,
        "image_url": "http://115.191.50.177:5005/static/cocktail/images/default.jpg",
        "mood_tags": ["浪漫", "神秘"],
        "flavor_tags": ["玫瑰", "柑橘"],
        "glass_type": "coupe"
    },
    "ai": {
        "reason": "基于你喜欢的玫瑰元素，我为你调整了 French Rose 的配方，增加了柑橘的清新感。",
        "poetic_copy": "暮光中绽放的玫瑰，带着柑橘的微光。",
        "mood_caption": "浪漫神秘",
        "tweaks": {  # ✅ 原创模式会有 tweaks
            "prototype_id": 101,
            "changes": [
                {"ingredient": "柠檬汁", "change": "增加至 20ml"},
                {"ingredient": "玫瑰糖浆", "change": "减少至 10ml"}
            ]
        }
    },
    "ingredients": [
        {"ingredient_id": 30, "name_zh": "伏特加", "measure": "30ml", "status": "owned"},
        {"ingredient_id": 40, "name_zh": "柠檬汁", "measure": "20ml", "status": "owned"}
    ],
    "steps": [
        {"order": 1, "text": "混合所有配料", "duration_hint": None}
    ]
}

ORIGINAL_MODE_CARD_REQUEST = {
    "cocktail_id": ORIGINAL_MODE_RESPONSE["cocktail"]["id"],
    "session_id": ORIGINAL_MODE_RESPONSE["session_id"],
    "cocktail_name": ORIGINAL_MODE_RESPONSE["cocktail"]["name"],
    "cocktail_name_zh": ORIGINAL_MODE_RESPONSE["cocktail"]["name_zh"],
    "ai_poetic": ORIGINAL_MODE_RESPONSE["ai"]["poetic_copy"],
    "ai_reason": ORIGINAL_MODE_RESPONSE["ai"]["reason"],
    "mood_caption": ORIGINAL_MODE_RESPONSE["ai"]["mood_caption"],
    "ai_tweaks": ORIGINAL_MODE_RESPONSE["ai"]["tweaks"],  # ✅ 包含调整信息
    "prototype_name": "French Rose",  # ✅ 原型英文名
    "prototype_name_zh": "法式玫瑰",  # ✅ 原型中文名
    "ingredients": ORIGINAL_MODE_RESPONSE["ingredients"],
    "use_system_image": True,
    "template_id": "vesper",
}


def main():
    print("=" * 70)
    print("推荐接口 → 卡片生成 数据映射测试")
    print("=" * 70)
    
    print("\n1️⃣  经典模式 - 推荐接口返回示例")
    print("-" * 70)
    print(json.dumps(RECOMMEND_RESPONSE, ensure_ascii=False, indent=2))
    
    print("\n2️⃣  经典模式 - 前端应传递给 /api/card/generate 的数据")
    print("-" * 70)
    print(json.dumps(CARD_GENERATE_REQUEST, ensure_ascii=False, indent=2))
    
    print("\n3️⃣  原创模式 - 推荐接口返回示例（部分）")
    print("-" * 70)
    print(json.dumps({
        "session_id": ORIGINAL_MODE_RESPONSE["session_id"],
        "cocktail": ORIGINAL_MODE_RESPONSE["cocktail"],
        "ai": ORIGINAL_MODE_RESPONSE["ai"]
    }, ensure_ascii=False, indent=2))
    
    print("\n4️⃣  原创模式 - 前端应传递给 /api/card/generate 的数据")
    print("-" * 70)
    print(json.dumps(ORIGINAL_MODE_CARD_REQUEST, ensure_ascii=False, indent=2))
    
    print("\n" + "=" * 70)
    print("✅ 字段完整性检查")
    print("=" * 70)
    
    required_fields = [
        ("session_id", "会话ID"),
        ("cocktail_id", "鸡尾酒ID"),
        ("ai_reason", "AI推荐理由"),
        ("ai_poetic", "诗意文案"),
        ("mood_caption", "心情描述"),
        ("ai_tweaks", "配方调整（原创模式）"),
        ("prototype_name", "原型名称（原创模式）"),
        ("prototype_name_zh", "原型中文名（原创模式）"),
        ("ingredients", "配料列表"),
    ]
    
    print("\n经典模式：")
    for field, desc in required_fields:
        value = CARD_GENERATE_REQUEST.get(field)
        status = "✅" if value is not None else "⚠️"
        print(f"  {status} {field:20s} {desc:30s} = {value}")
    
    print("\n原创模式：")
    for field, desc in required_fields:
        value = ORIGINAL_MODE_CARD_REQUEST.get(field)
        status = "✅" if value else "⚠️"
        print(f"  {status} {field:20s} {desc:30s} = {repr(value)[:50]}")
    
    print("\n" + "=" * 70)
    print("📝 前端集成建议")
    print("=" * 70)
    print("""
1. 从推荐接口获取完整的 response 后，直接将所有字段传递给卡片生成接口
2. 特别注意传递以下新增字段：
   - session_id: 关联推荐会话
   - ai_reason: AI推荐理由（重要！）
   - ai_tweaks: 配方调整信息（原创模式）
   - prototype_name/zh: 原型名称（原创模式）
   - ingredients: 完整的配料列表（包括 status、substitute 等）

3. 示例代码（JavaScript）：
   ```javascript
   // 1. 获取推荐
   const recommendResponse = await fetch('/api/recommend', {
     method: 'POST',
     body: JSON.stringify(userPrefs)
   }).then(r => r.json());
   
   const data = recommendResponse.data;
   
   // 2. 随机选择模板
   const templates = await fetch('/api/card/templates').then(r => r.json());
   const randomTemplate = templates.data.templates[
     Math.floor(Math.random() * templates.data.templates.length)
   ];
   
   // 3. 生成卡片（传递所有推荐接口返回的字段）
   const cardRequest = {
     // 基本信息
     cocktail_id: data.cocktail.id,
     session_id: data.session_id,  // ✅ 新增
     
     // AI 名称
     cocktail_name: data.cocktail.name,
     cocktail_name_zh: data.cocktail.name_zh,
     
     // AI 内容
     ai_poetic: data.ai.poetic_copy,
     ai_reason: data.ai.reason,  // ✅ 新增（重要！）
     mood_caption: data.ai.mood_caption,
     ai_tweaks: data.ai.tweaks,  // ✅ 新增
     
     // 原型信息（原创模式）
     prototype_name: data.ai.prototype_name,  // ✅ 新增
     prototype_name_zh: data.ai.prototype_name_zh,  // ✅ 新增
     
     // 配料和步骤
     ingredients: data.ingredients,  // ✅ 完整的配料数据
     
     // 模板和图片
     template_id: randomTemplate,
     use_system_image: true
   };
   
   const cardResponse = await fetch('/api/card/generate', {
     method: 'POST',
     headers: { 'Authorization': `Bearer ${token}` },
     body: JSON.stringify(cardRequest)
   }).then(r => r.json());
   ```
""")
    
    print("\n✅ 测试完成！")


if __name__ == "__main__":
    main()
