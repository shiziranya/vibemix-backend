#!/usr/bin/env python3
"""
智能标准化所有鸡尾酒配方的中文用量
基于规则引擎 + 上下文推断
"""

import os
import sys
import re

sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))

from sqlalchemy import create_engine, text


def smart_normalize(measure_raw, ingredient_name, ingredient_name_zh, category):
    """
    智能标准化用量
    
    返回: (normalized_zh, measure_ml, measure_type)
    """
    if not measure_raw or measure_raw.strip() == '':
        # 根据原料类型推断默认用量
        if category in ['juice', 'soda', 'water']:
            return ('补满', 60, 'descriptive')
        elif category == 'garnish':
            return ('装饰用', None, 'descriptive')
        else:
            return ('适量', None, 'descriptive')
    
    measure_lower = measure_raw.lower().strip()
    name_lower = ingredient_name.lower()
    
    # 0. 预处理：统一单位拼写
    # ounce/ounces → oz
    measure_lower = re.sub(r'\b(\d+(?:[/.]\d+)?)\s*ounces?\b', r'\1 oz', measure_lower)
    # tblsp → tbsp
    measure_lower = re.sub(r'\btblsp\b', 'tbsp', measure_lower)
    # bsp → barspoon
    measure_lower = re.sub(r'\bbsp\b', 'barspoon', measure_lower)
    
    # 1. 处理蛋清 (Egg White)
    if 'egg white' in measure_lower or 'egg' in name_lower:
        num_match = re.search(r'(\d+)', measure_lower)
        if num_match:
            num = num_match.group(1)
            return (f'{num}个蛋清', None, 'precise')
        else:
            return ('1个蛋清', None, 'precise')
    
    # 2. 处理装饰品的纯数字
    if category == 'garnish':
        num_match = re.match(r'^(\d+)$', measure_lower)
        if num_match:
            num = num_match.group(1)
            if 'cherry' in name_lower or '樱桃' in (ingredient_name_zh or ''):
                return (f'{num}颗樱桃', None, 'precise')
            elif 'olive' in name_lower or '橄榄' in (ingredient_name_zh or ''):
                return (f'{num}颗橄榄', None, 'precise')
            elif 'clove' in name_lower or '丁香' in (ingredient_name_zh or ''):
                return (f'{num}颗丁香', None, 'precise')
            elif 'raspberry' in name_lower or 'raspberries' in name_lower:
                return (f'{num}颗树莓', None, 'precise')
            elif 'orange' in name_lower or '橙' in (ingredient_name_zh or ''):
                return (f'{num}片橙片', None, 'approximate')
            else:
                return (f'{num}个', None, 'approximate')
    
    # 3. 处理 float (浮在表面)
    if 'float' in measure_lower:
        ing_zh = ingredient_name_zh or ingredient_name
        return (f'浮层{ing_zh}', 10, 'descriptive')
    
    # 4. 处理 muddled (捣碎)
    if measure_lower == 'muddled':
        return ('捣碎', None, 'descriptive')
    
    # 5. 处理 juiced (榨汁)
    if measure_lower == 'juiced':
        return ('榨汁', None, 'descriptive')
    
    # 6. 处理 "Juice of X" 格式
    juice_match = re.match(r'juice of (\d+(?:[/.]\d+)?)\s*(lime|lemon|orange)?', measure_lower)
    if juice_match:
        num = juice_match.group(1)
        fruit = juice_match.group(2)
        
        # 解析数字
        if '/' in num:
            parts = num.split('/')
            num_val = float(parts[0]) / float(parts[1])
        else:
            num_val = float(num)
        
        # 确定水果类型
        if fruit:
            fruit_zh = {'lime': '青柠', 'lemon': '柠檬', 'orange': '橙子'}.get(fruit, fruit)
        elif 'lime' in name_lower:
            fruit_zh = '青柠'
        elif 'lemon' in name_lower:
            fruit_zh = '柠檬'
        elif 'orange' in name_lower:
            fruit_zh = '橙子'
        else:
            fruit_zh = ingredient_name_zh or ingredient_name
        
        if num_val == 1:
            normalized = f'1个{fruit_zh}榨汁'
            ml = 30
        elif num_val == 0.5:
            normalized = f'半个{fruit_zh}榨汁'
            ml = 15
        elif num_val == 0.25:
            normalized = f'1/4个{fruit_zh}榨汁'
            ml = 8
        else:
            normalized = f'{num_val}个{fruit_zh}榨汁'
            ml = int(num_val * 30)
        
        return (normalized, ml, 'approximate')
    
    # 7. 处理纯数字 + 水果/薄荷/叶子
    if re.match(r'^\d+(?:-\d+)?$', measure_raw.strip()):
        nums = measure_raw.strip().split('-')
        if len(nums) == 2:
            avg = (int(nums[0]) + int(nums[1])) / 2
        else:
            avg = int(nums[0])
        
        # 根据原料类型判断
        if 'mint' in name_lower or '薄荷' in (ingredient_name_zh or ''):
            if avg > 10:
                return (f'{int(avg)}片薄荷叶', None, 'approximate')
            else:
                return (f'{int(avg)}片薄荷叶', None, 'approximate')
        elif 'lime' in name_lower or 'lemon' in name_lower:
            fruit_zh = '青柠' if 'lime' in name_lower else '柠檬'
            return (f'{int(avg)}个{fruit_zh}', int(avg * 30), 'approximate')
        elif 'leaf' in name_lower or 'leaves' in name_lower:
            return (f'{int(avg)}片叶子', None, 'approximate')
        elif category == 'fruit':
            return (f'{int(avg)}个', None, 'approximate')
        else:
            return (f'{int(avg)}个', None, 'unclear')
    
    # 8. 处理描述性词汇
    descriptive_map = {
        'top': ('补满', 60, 'descriptive'),
        'top up': ('补满', 60, 'descriptive'),
        'fill': ('补满', 60, 'descriptive'),
        'garnish': ('装饰用', None, 'descriptive'),
        'splash': ('少许', 5, 'approximate'),
        'pinch': ('少许', None, 'descriptive'),
        'to taste': ('适量', None, 'descriptive'),
        'twist': ('1条果皮', None, 'descriptive'),
        'wedge': ('1角', None, 'descriptive'),
        'slice': ('1片', None, 'descriptive'),
        'sprig': ('1小枝', None, 'descriptive'),
        'whole': ('1个', None, 'approximate'),
    }
    
    for keyword, (zh, ml, typ) in descriptive_map.items():
        if keyword in measure_lower:
            # 提取可能的数量
            num_match = re.search(r'(\d+)\s*' + keyword, measure_lower)
            if num_match:
                num = num_match.group(1)
                if ml:
                    return (f'{num}{zh}', int(num) * ml, typ)
                else:
                    return (f'{num}{zh}', None, typ)
            return (zh, ml, typ)
    
    # 9. 处理 "X part(s)" 格式
    part_match = re.match(r'(\d+(?:\.\d+)?)\s*parts?', measure_lower)
    if part_match:
        num = float(part_match.group(1))
        # part 通常是比例，转换为实际用量（假设1 part = 30ml）
        ml = int(num * 30)
        return (f'{ml}ml', ml, 'approximate')
    
    # 10. 处理 cup 单位
    cup_match = re.match(r'(\d+(?:/\d+)?)\s*cup', measure_lower)
    if cup_match:
        frac = cup_match.group(1)
        if '/' in frac:
            parts = frac.split('/')
            val = float(parts[0]) / float(parts[1])
        else:
            val = float(frac)
        ml = int(val * 240)  # 1 cup = 240ml
        return (f'{ml}ml', ml, 'precise')
    
    # 11. 处理 cube/cubes (糖块/冰块)
    if 'cube' in measure_lower:
        num_match = re.search(r'(\d+)\s*cube', measure_lower)
        if num_match:
            num = num_match.group(1)
            if 'sugar' in name_lower or '糖' in (ingredient_name_zh or ''):
                return (f'{num}块方糖', 5 * int(num), 'approximate')
            elif 'ice' in name_lower or '冰' in (ingredient_name_zh or ''):
                return ('适量冰块', None, 'descriptive')
        else:
            if 'sugar' in name_lower or '糖' in (ingredient_name_zh or ''):
                return ('1块方糖', 5, 'approximate')
            elif 'ice' in name_lower or '冰' in (ingredient_name_zh or ''):
                return ('适量冰块', None, 'descriptive')
    
    # 12. 处理 drop/drops (滴)
    drop_match = re.match(r'(\d+)\s*drops?', measure_lower)
    if drop_match:
        num = int(drop_match.group(1))
        return (f'{num}滴', None, 'approximate')
    
    # 13. 已经是标准化的保持原样
    if re.match(r'^\d+(?:\.\d+)?ml$', measure_lower):
        ml = float(re.match(r'^([\d.]+)ml$', measure_lower).group(1))
        return (f'{int(ml)}ml', ml, 'precise')
    
    # 14. 其他情况返回原值
    return (measure_raw, None, 'unclear')


def main():
    db_url = os.getenv(
        'SUPABASE_DATABASE_URL',
        'postgresql://postgres:postgres123@localhost:5432/tipsy_inspirations'
    )
    engine = create_engine(db_url)
    
    with engine.begin() as conn:
        # 获取所有需要处理的原料
        result = conn.execute(text("""
            SELECT 
                ci.id,
                ci.measure_raw,
                ci.measure_normalized as current_normalized,
                ci.measure_type as current_type,
                ing.name as ingredient_name,
                ing.name_zh as ingredient_name_zh,
                ing.category,
                c.name as cocktail_name,
                c.name_zh as cocktail_name_zh
            FROM cocktail_ingredients ci
            JOIN ingredients ing ON ci.ingredient_id = ing.id
            JOIN cocktails c ON ci.cocktail_id = c.id
            WHERE ci.measure_type IN ('unclear', 'descriptive') 
               OR ci.measure_normalized IS NULL
               OR ci.measure_normalized IN ('适量', '2-4')
            ORDER BY c.id, ci.sort_order
        """))
        
        rows = result.fetchall()
        total = len(rows)
        
        print(f"找到 {total} 条需要优化的用量记录\n")
        
        stats = {
            'updated': 0,
            'skipped': 0,
        }
        
        for idx, row in enumerate(rows, 1):
            normalized, ml, measure_type = smart_normalize(
                row.measure_raw,
                row.ingredient_name,
                row.ingredient_name_zh,
                row.category
            )
            
            # 如果和当前一样，跳过
            if normalized == row.current_normalized:
                stats['skipped'] += 1
                continue
            
            # 更新数据库
            conn.execute(text("""
                UPDATE cocktail_ingredients
                SET measure_normalized = :normalized,
                    measure_ml = :ml,
                    measure_type = :type
                WHERE id = :id
            """), {
                'id': row.id,
                'normalized': normalized,
                'ml': ml,
                'type': measure_type
            })
            
            stats['updated'] += 1
            
            # 显示进度
            if stats['updated'] % 100 == 0:
                print(f"  已更新 {stats['updated']}/{total} 条...")
        
        print(f"\n✅ 处理完成！")
        print(f"  更新: {stats['updated']}")
        print(f"  跳过: {stats['skipped']}")
        print(f"  总计: {total}")


if __name__ == '__main__':
    main()
