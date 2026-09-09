#!/usr/bin/env python3
"""
使用 LLM 智能生成鸡尾酒配方的中文用量

对于复杂的、难以用规则处理的用量描述，使用 LLM 理解上下文并生成准确的中文用量。
"""

import os
import sys
import json
import time
from decimal import Decimal

sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))

from sqlalchemy import create_engine, text
from anthropic import Anthropic

# 初始化 Anthropic 客户端
client = Anthropic(api_key=os.getenv('ANTHROPIC_API_KEY'))

def get_cocktail_ingredients(conn, cocktail_id):
    """获取一个鸡尾酒的所有原料"""
    result = conn.execute(text("""
        SELECT 
            ci.id,
            ci.measure_raw,
            ci.measure_normalized,
            ci.measure_type,
            ing.name as ingredient_name,
            ing.name_zh as ingredient_name_zh,
            ing.category
        FROM cocktail_ingredients ci
        JOIN ingredients ing ON ci.ingredient_id = ing.id
        WHERE ci.cocktail_id = :cocktail_id
        ORDER BY ci.sort_order
    """), {'cocktail_id': cocktail_id})
    
    return result.fetchall()


def normalize_with_llm(cocktail_name, ingredients_data):
    """
    使用 LLM 批量标准化一个鸡尾酒的所有原料用量
    
    返回: list of dict with keys: id, normalized_zh, value, unit
    """
    # 构建提示词
    ingredients_list = []
    for ing in ingredients_data:
        ingredients_list.append({
            'id': ing.id,
            'name': ing.ingredient_name_zh or ing.ingredient_name,
            'name_en': ing.ingredient_name,
            'category': ing.category,
            'measure_raw': ing.measure_raw or '无',
        })
    
    prompt = f"""你是一个专业调酒师，请将以下鸡尾酒配方的原料用量标准化为中文表达。

鸡尾酒: {cocktail_name}

原料列表:
{json.dumps(ingredients_list, ensure_ascii=False, indent=2)}

标准化要求:
1. 体积单位统一转换为毫升(ml)，1 oz = 30ml, 1 cl = 10ml
2. 如果是范围(如2-3 oz)，取中间值(如2.5 oz = 75ml)
3. 如果是"Juice of 1"这种表达，转换为"1个青柠榨汁"或"1个柠檬榨汁"
4. 如果是纯数字配水果/薄荷等，转换为"X个/片/叶"
5. dash 转换为"滴"，splash 转换为"少许"
6. 茶匙(tsp)转换为5ml，汤匙(tbsp)转换为15ml
7. 如果原始数据为空或None，推断合理用量(如苏打水"补满"、装饰"适量")
8. 保持专业、简洁的中文表达

请返回JSON格式，每个原料包含:
- id: 原料ID
- normalized_zh: 中文用量(如"75ml"、"1个青柠榨汁"、"3-4片薄荷叶")
- measure_ml: 换算后的毫升数(如果不是液体或无法确定，填null)
- measure_type: "precise"(精确) / "approximate"(约量) / "descriptive"(描述性)

只返回JSON，不要其他内容。"""

    try:
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
        
        # 提取JSON（去除可能的markdown代码块）
        if response_text.startswith('```'):
            lines = response_text.split('\n')
            response_text = '\n'.join(lines[1:-1])
        
        result = json.loads(response_text)
        return result
        
    except Exception as e:
        print(f"  ❌ LLM调用失败: {e}")
        return None


def main():
    """执行批量标准化"""
    db_url = os.getenv(
        'SUPABASE_DATABASE_URL',
        'postgresql://postgres:postgres123@localhost:5432/tipsy_inspirations'
    )
    engine = create_engine(db_url)
    
    with engine.begin() as conn:
        # 获取所有鸡尾酒
        cocktails = conn.execute(text("""
            SELECT id, name, name_zh
            FROM cocktails
            ORDER BY id
        """)).fetchall()
        
        total = len(cocktails)
        print(f"开始处理 {total} 个鸡尾酒配方...\n")
        
        stats = {
            'success': 0,
            'failed': 0,
            'updated_ingredients': 0,
        }
        
        for idx, cocktail in enumerate(cocktails, 1):
            cocktail_id = cocktail.id
            cocktail_name = cocktail.name_zh or cocktail.name
            
            print(f"[{idx}/{total}] {cocktail_name}...")
            
            # 获取这个鸡尾酒的所有原料
            ingredients = get_cocktail_ingredients(conn, cocktail_id)
            
            if not ingredients:
                print(f"  跳过：无原料")
                continue
            
            # 调用 LLM 标准化
            result = normalize_with_llm(cocktail_name, ingredients)
            
            if not result:
                stats['failed'] += 1
                continue
            
            # 更新数据库
            for item in result:
                try:
                    conn.execute(text("""
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
                    stats['updated_ingredients'] += 1
                except Exception as e:
                    print(f"  ⚠️  更新原料 {item['id']} 失败: {e}")
            
            stats['success'] += 1
            
            # 进度显示
            if idx % 10 == 0:
                print(f"  进度: {idx}/{total} ({idx*100//total}%)")
            
            # API 限流
            time.sleep(0.5)
        
        print(f"\n✅ 处理完成！")
        print(f"\n统计结果:")
        print(f"  成功: {stats['success']}")
        print(f"  失败: {stats['failed']}")
        print(f"  更新原料数: {stats['updated_ingredients']}")


if __name__ == '__main__':
    if not os.getenv('ANTHROPIC_API_KEY'):
        print("❌ 错误: 请设置 ANTHROPIC_API_KEY 环境变量")
        sys.exit(1)
    
    main()
