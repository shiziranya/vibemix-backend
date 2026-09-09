#!/usr/bin/env python3
"""
测试 LLM 标准化 - 只处理莫吉托
"""

import os
import sys
import json

sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))

from sqlalchemy import create_engine, text
from anthropic import Anthropic

client = Anthropic(api_key=os.getenv('ANTHROPIC_API_KEY'))

def main():
    db_url = os.getenv(
        'SUPABASE_DATABASE_URL',
        'postgresql://postgres:postgres123@localhost:5432/tipsy_inspirations'
    )
    engine = create_engine(db_url)
    
    with engine.connect() as conn:
        # 获取莫吉托的配方
        result = conn.execute(text("""
            SELECT 
                c.name, c.name_zh,
                ci.id as ingredient_id,
                ci.measure_raw,
                ci.measure_normalized as current_normalized,
                ing.name as ingredient_name,
                ing.name_zh as ingredient_name_zh,
                ing.category
            FROM cocktails c
            JOIN cocktail_ingredients ci ON c.id = ci.cocktail_id
            JOIN ingredients ing ON ci.ingredient_id = ing.id
            WHERE c.name = 'Mojito'
            ORDER BY ci.sort_order
        """))
        
        rows = result.fetchall()
        
        # 构建输入数据
        ingredients_list = []
        for row in rows:
            ingredients_list.append({
                'id': row.ingredient_id,
                'name': row.ingredient_name_zh or row.ingredient_name,
                'name_en': row.ingredient_name,
                'category': row.category,
                'measure_raw': row.measure_raw or '无',
                'current_normalized': row.current_normalized,
            })
        
        print("=== 莫吉托当前配方 ===")
        for ing in ingredients_list:
            print(f"{ing['name']:15} | 原始: {ing['measure_raw']:20} | 当前: {ing['current_normalized']}")
        
        print("\n正在调用 Claude API...")
        
        prompt = f"""你是一个专业调酒师，请将以下鸡尾酒配方的原料用量标准化为中文表达。

鸡尾酒: 莫吉托 (Mojito)

原料列表:
{json.dumps(ingredients_list, ensure_ascii=False, indent=2)}

标准化要求:
1. 体积单位统一转换为毫升(ml)，1 oz = 30ml, 1 cl = 10ml
2. 如果是范围(如2-3 oz)，取中间值(如2.5 oz = 75ml)
3. 如果是"Juice of 1"这种表达，转换为"1个青柠榨汁"或"1个柠檬榨汁"
4. 如果是纯数字配水果/薄荷等，转换为"X片/叶"（薄荷用"片"，mint leaves用"片"）
5. dash 转换为"滴"，splash 转换为"少许"
6. 茶匙(tsp)转换为5ml，汤匙(tbsp)转换为15ml
7. 如果原始数据为空或None，推断合理用量(如苏打水"补满"、装饰"适量")
8. 保持专业、简洁的中文表达

请返回JSON格式，每个原料包含:
- id: 原料ID
- normalized_zh: 中文用量(如"75ml"、"1个青柠榨汁"、"3片薄荷叶")
- measure_ml: 换算后的毫升数(如果不是液体或无法确定，填null)
- measure_type: "precise"(精确) / "approximate"(约量) / "descriptive"(描述性)

只返回JSON数组，不要其他内容。"""

        message = client.messages.create(
            model="claude-3-5-sonnet-20241022",
            max_tokens=2000,
            temperature=0,
            messages=[{
                "role": "user",
                "content": prompt
            }]
        )
        
        response_text = message.content[0].text.strip()
        
        # 提取JSON
        if response_text.startswith('```'):
            lines = response_text.split('\n')
            if lines[0].startswith('```json'):
                response_text = '\n'.join(lines[1:-1])
            else:
                response_text = '\n'.join(lines[1:-1])
        
        result = json.loads(response_text)
        
        print("\n=== LLM 建议的标准化 ===")
        for item in result:
            ing_data = next(i for i in ingredients_list if i['id'] == item['id'])
            print(f"{ing_data['name']:15} | {item['normalized_zh']:20} | [{item['measure_type']}] {item['measure_ml']}ml")
        
        print("\n是否应用这些更改？(y/n)")
        response = input().strip().lower()
        
        if response == 'y':
            with engine.begin() as conn_write:
                for item in result:
                    conn_write.execute(text("""
                        UPDATE cocktail_ingredients
                        SET measure_normalized = :normalized,
                            measure_ml = :ml,
                            measure_type = :type
                        WHERE id = :id
                    """), {
                        'id': item['id'],
                        'normalized': item['normalized_zh'],
                        'ml': item.get('measure_ml'),
                        'type': item.get('measure_type', 'descriptive')
                    })
            print("✅ 已更新！")
        else:
            print("已取消")


if __name__ == '__main__':
    if not os.getenv('ANTHROPIC_API_KEY'):
        print("❌ 错误: 请设置 ANTHROPIC_API_KEY 环境变量")
        sys.exit(1)
    
    main()
