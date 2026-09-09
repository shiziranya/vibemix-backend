#!/usr/bin/env python3
"""
规范化 cocktail_ingredients 表中的 measure_raw 字段

换算规则（用户要求）：
- oz → ml (1:30)
- cl → ml (1:10) 
- pint → ml (1:473)
- quart → ml (1:946)
- gallon → ml (1:3785)
- dash、barspoon 保留不换算
- tsp → ml (1:5)
- tbsp → ml (1:15)
"""

import os
import re
import sys
from decimal import Decimal
from fractions import Fraction

# 添加项目根目录到路径
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))

from sqlalchemy import create_engine, text

# 单位换算表（换算为ml）
UNIT_CONVERSIONS = {
    'oz': 30,      # 盎司 → ml (用户要求简化为 1:30)
    'cl': 10,      # 厘升 → ml
    'pint': 473,   # 品脱 → ml
    'quart': 946,  # 夸脱 → ml
    'gallon': 3785,# 加仑 → ml
    'tsp': 5,      # 茶匙 → ml
    'tbsp': 15,    # 汤匙 → ml
}

# 不换算的单位（保留原样）
KEEP_UNITS = ['dash', 'dashes', 'barspoon', 'barspoons']

# 描述性关键词映射
DESCRIPTIVE_KEYWORDS = {
    'top up': '补满',
    'fill': '补满',
    'garnish': '装饰用',
    'to taste': '适量',
    'splash': '少许',
    'pinch': '少许',
    'fresh': None,  # 跳过修饰词
    'ground': None,
    'cubed': None,
}


def parse_fraction(value_str):
    """
    解析分数和混合分数
    例如: "1.5" → 1.5, "1/2" → 0.5, "1 1/2" → 1.5
    """
    value_str = value_str.strip()
    
    # 处理混合分数 "1 1/2"
    mixed_match = re.match(r'(\d+)\s+(\d+)/(\d+)', value_str)
    if mixed_match:
        whole = int(mixed_match.group(1))
        frac = Fraction(int(mixed_match.group(2)), int(mixed_match.group(3)))
        return float(whole + frac)
    
    # 处理纯分数 "1/2"
    if '/' in value_str:
        try:
            return float(Fraction(value_str))
        except (ValueError, ZeroDivisionError):
            return None
    
    # 处理小数 "1.5"
    try:
        return float(value_str)
    except ValueError:
        return None


def normalize_measure(measure_raw):
    """
    规范化用量描述
    
    返回: {
        'normalized': str,    # 规范化后的中文用量
        'value': float|None,  # 数值部分
        'unit': str|None,     # 单位
        'type': str          # precise/approximate/descriptive/unclear
    }
    """
    if not measure_raw or not measure_raw.strip():
        return {
            'normalized': '适量',
            'value': None,
            'unit': None,
            'type': 'descriptive'
        }
    
    measure_raw = measure_raw.strip()
    measure_lower = measure_raw.lower()
    
    # 1. 特殊模式：Juice of X (X个水果的汁)
    juice_pattern = r'juice\s+of\s+([\d/\s\.]+)'
    juice_match = re.search(juice_pattern, measure_lower)
    if juice_match:
        value_str = juice_match.group(1).strip()
        value = parse_fraction(value_str)
        if value is not None:
            # 转换为规范化表达：如 "1个青柠汁"、"1/2个柠檬汁"
            if value == int(value):
                normalized = f'{int(value)}个果汁'
            else:
                # 保留分数形式
                normalized = f'{value_str}个果汁'
            return {
                'normalized': normalized,
                'value': value,
                'unit': '个',
                'type': 'approximate'
            }
    
    # 2. 检查描述性关键词
    for keyword, normalized in DESCRIPTIVE_KEYWORDS.items():
        if keyword in measure_lower:
            if normalized is None:
                continue  # 跳过修饰词，继续解析
            return {
                'normalized': normalized,
                'value': None,
                'unit': None,
                'type': 'descriptive'
            }
    
    # 2. 尝试解析 "数值+单位" 格式
    # 匹配模式：数字(可能带空格、分数、范围) + 可选单位
    # 支持: "2 oz", "1.5 cl", "2-3 oz", "1/2 tsp"
    pattern = r'([\d\s/\.\-]+)\s*(oz|ml|cl|pint|quart|gallon|tsp|tbsp|teaspoon|tablespoon|dash|dashes|barspoon|barspoons|shot)?'
    match = re.match(pattern, measure_lower, re.IGNORECASE)
    
    if match:
        value_str = match.group(1)
        unit = match.group(2)
        
        # 处理范围表达式 "2-3" -> 取平均值
        if '-' in value_str and not value_str.strip().startswith('-'):
            parts = value_str.split('-')
            if len(parts) == 2:
                val1 = parse_fraction(parts[0].strip())
                val2 = parse_fraction(parts[1].strip())
                if val1 is not None and val2 is not None:
                    value = (val1 + val2) / 2  # 取平均值
                else:
                    value = None
            else:
                value = None
        else:
            # 解析数值
            value = parse_fraction(value_str)
        
        if value is None:
            return {
                'normalized': '适量',
                'value': None,
                'unit': None,
                'type': 'unclear',
                'note': f'无法解析数值: {value_str}'
            }
        
        # 没有单位的情况
        if not unit:
            # 检查是否只是纯数字（可能表示"个"）
            if re.match(r'^\d+$', value_str.strip()):
                return {
                    'normalized': f'{int(value)}个',
                    'value': value,
                    'unit': '个',
                    'type': 'unclear',
                    'note': '需根据原料类型确认'
                }
            else:
                # 分数但无单位，可能是 "1/2 lime" 这种
                return {
                    'normalized': measure_raw,
                    'value': value,
                    'unit': None,
                    'type': 'unclear',
                    'note': '缺少单位'
                }
        
        # 规范化单位名称
        unit = unit.lower().rstrip('s')  # dashes → dash, barspoons → barspoon
        if unit == 'teaspoon':
            unit = 'tsp'
        elif unit == 'tablespoon':
            unit = 'tbsp'
        
        # 3. 处理需要换算的单位
        if unit in UNIT_CONVERSIONS:
            ml_value = value * UNIT_CONVERSIONS[unit]
            # 四舍五入到整数（小用量保留1位小数）
            if ml_value < 10:
                ml_value = round(ml_value, 1)
            else:
                ml_value = round(ml_value)
            
            return {
                'normalized': f'{ml_value:.10g}ml'.replace('.0ml', 'ml'),  # 去掉 .0
                'value': float(ml_value),
                'unit': 'ml',
                'type': 'precise'
            }
        
        # 4. 处理保留单位（dash, barspoon）
        elif unit in KEEP_UNITS:
            unit_zh = {
                'dash': '滴',
                'barspoon': 'barspoon'
            }.get(unit, unit)
            
            # dash 算约量，barspoon 算精确
            measure_type = 'approximate' if unit == 'dash' else 'precise'
            
            return {
                'normalized': f'{int(value) if value.is_integer() else value}{unit_zh}',
                'value': value,
                'unit': unit_zh,
                'type': measure_type
            }
        
        # 5. ml 不需要换算
        elif unit == 'ml':
            return {
                'normalized': f'{int(value) if value.is_integer() else value}ml',
                'value': value,
                'unit': 'ml',
                'type': 'precise'
            }
        
        # 6. shot 特殊处理
        elif unit == 'shot':
            ml_value = value * 45  # 1 shot = 45ml
            return {
                'normalized': f'{int(ml_value)}ml',
                'value': float(ml_value),
                'unit': 'ml',
                'type': 'precise'
            }
    
    # 7. 无法解析，返回适量
    return {
        'normalized': '适量',
        'value': None,
        'unit': None,
        'type': 'descriptive',
        'original': measure_raw
    }


def main():
    """执行批量规范化"""
    db_url = os.getenv(
        'SUPABASE_DATABASE_URL',
        'postgresql://postgres:postgres123@localhost:5432/tipsy_inspirations'
    )
    engine = create_engine(db_url)
    
    with engine.begin() as conn:
        # 获取所有记录
        result = conn.execute(text("""
            SELECT id, measure_raw
            FROM cocktail_ingredients
            WHERE measure_raw IS NOT NULL
            ORDER BY id
        """))
        
        rows = result.fetchall()
        total = len(rows)
        
        print(f"开始规范化 {total} 条记录...\n")
        
        stats = {
            'precise': 0,
            'approximate': 0,
            'descriptive': 0,
            'unclear': 0,
        }
        
        unclear_cases = []
        
        for idx, row in enumerate(rows, 1):
            ing_id = row.id
            measure_raw = row.measure_raw
            
            # 规范化
            result = normalize_measure(measure_raw)
            
            # 更新数据库
            conn.execute(text("""
                UPDATE cocktail_ingredients
                SET measure_normalized = :normalized,
                    measure_value = :value,
                    measure_unit = :unit,
                    measure_type = :type
                WHERE id = :id
            """), {
                'id': ing_id,
                'normalized': result['normalized'],
                'value': result.get('value'),
                'unit': result.get('unit'),
                'type': result['type']
            })
            
            # 统计
            stats[result['type']] += 1
            
            # 记录需要人工处理的case
            if result['type'] == 'unclear':
                unclear_cases.append({
                    'id': ing_id,
                    'raw': measure_raw,
                    'normalized': result['normalized'],
                    'note': result.get('note', '')
                })
            
            # 进度显示
            if idx % 100 == 0 or idx == total:
                print(f"  处理进度: {idx}/{total} ({idx*100//total}%)")
        
        print(f"\n✅ 规范化完成！")
        print(f"\n统计结果:")
        print(f"  精确用量 (precise): {stats['precise']}")
        print(f"  约量 (approximate): {stats['approximate']}")
        print(f"  描述性 (descriptive): {stats['descriptive']}")
        print(f"  需人工确认 (unclear): {stats['unclear']}")
        
        # 输出需要人工处理的case
        if unclear_cases:
            print(f"\n⚠️  以下 {len(unclear_cases)} 条记录需要人工确认:")
            for case in unclear_cases[:20]:  # 只显示前20条
                print(f"  ID {case['id']}: '{case['raw']}' → '{case['normalized']}' ({case['note']})")
            
            if len(unclear_cases) > 20:
                print(f"  ... 还有 {len(unclear_cases) - 20} 条，请查询数据库")
        
        print("\n可通过以下SQL查看需要人工处理的记录：")
        print("  SELECT id, measure_raw, measure_normalized, measure_type")
        print("  FROM cocktail_ingredients")
        print("  WHERE measure_type = 'unclear';")


if __name__ == '__main__':
    main()
