#!/usr/bin/env python3
"""
测试用量规范化逻辑

运行: python3 scripts/test_normalize.py
"""

import sys
import os

# 添加项目根目录到路径
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))

# 导入规范化函数（注意：这里假设我们可以从 normalize_measures.py 导入）
# 实际使用时，可以将 normalize_measure 函数提取到单独的模块
import re
from fractions import Fraction


def parse_fraction(value_str):
    """解析分数和混合分数"""
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
    """规范化用量描述"""
    UNIT_CONVERSIONS = {
        'oz': 30,
        'cl': 10,
        'pint': 473,
        'quart': 946,
        'gallon': 3785,
        'tsp': 5,
        'tbsp': 15,
    }
    
    KEEP_UNITS = ['dash', 'dashes', 'barspoon', 'barspoons']
    
    DESCRIPTIVE_KEYWORDS = {
        'top up': '补满',
        'fill': '补满',
        'garnish': '装饰用',
        'to taste': '适量',
        'splash': '少许',
        'pinch': '少许',
    }
    
    if not measure_raw or not measure_raw.strip():
        return {'normalized': '适量', 'value': None, 'unit': None, 'type': 'descriptive'}
    
    measure_raw = measure_raw.strip()
    measure_lower = measure_raw.lower()
    
    # 检查描述性关键词
    for keyword, normalized in DESCRIPTIVE_KEYWORDS.items():
        if keyword in measure_lower:
            if normalized is None:
                continue
            return {'normalized': normalized, 'value': None, 'unit': None, 'type': 'descriptive'}
    
    # 解析 "数值+单位" 格式
    pattern = r'([\d\s/\.]+)\s*(oz|ml|cl|pint|quart|gallon|tsp|tbsp|teaspoon|tablespoon|dash|dashes|barspoon|barspoons|shot)?'
    match = re.match(pattern, measure_lower, re.IGNORECASE)
    
    if match:
        value_str = match.group(1)
        unit = match.group(2)
        
        value = parse_fraction(value_str)
        if value is None:
            return {'normalized': '适量', 'value': None, 'unit': None, 'type': 'unclear'}
        
        if not unit:
            if re.match(r'^\d+$', value_str.strip()):
                return {'normalized': f'{int(value)}个', 'value': value, 'unit': '个', 'type': 'unclear'}
            else:
                return {'normalized': measure_raw, 'value': value, 'unit': None, 'type': 'unclear'}
        
        unit = unit.lower().rstrip('s')
        if unit == 'teaspoon':
            unit = 'tsp'
        elif unit == 'tablespoon':
            unit = 'tbsp'
        
        # 需要换算的单位
        if unit in UNIT_CONVERSIONS:
            ml_value = value * UNIT_CONVERSIONS[unit]
            if ml_value < 10:
                ml_value = round(ml_value, 1)
            else:
                ml_value = round(ml_value)
            
            return {
                'normalized': f'{ml_value:.10g}ml'.replace('.0ml', 'ml'),
                'value': float(ml_value),
                'unit': 'ml',
                'type': 'precise'
            }
        
        # 保留单位
        elif unit in KEEP_UNITS:
            unit_zh = {'dash': '滴', 'barspoon': 'barspoon'}.get(unit, unit)
            measure_type = 'approximate' if unit == 'dash' else 'precise'
            
            return {
                'normalized': f'{int(value) if value.is_integer() else value}{unit_zh}',
                'value': value,
                'unit': unit_zh,
                'type': measure_type
            }
        
        # ml 不需要换算
        elif unit == 'ml':
            return {
                'normalized': f'{int(value) if value.is_integer() else value}ml',
                'value': value,
                'unit': 'ml',
                'type': 'precise'
            }
        
        # shot
        elif unit == 'shot':
            ml_value = value * 45
            return {
                'normalized': f'{int(ml_value)}ml',
                'value': float(ml_value),
                'unit': 'ml',
                'type': 'precise'
            }
    
    return {'normalized': '适量', 'value': None, 'unit': None, 'type': 'descriptive', 'original': measure_raw}


def run_tests():
    """运行测试用例"""
    test_cases = [
        # oz 换算
        ("1 oz", "30ml", 30.0, "ml", "precise"),
        ("1.5 oz", "45ml", 45.0, "ml", "precise"),
        ("1 1/2 oz", "45ml", 45.0, "ml", "precise"),
        ("2 oz", "60ml", 60.0, "ml", "precise"),
        
        # ml 保持
        ("30ml", "30ml", 30.0, "ml", "precise"),
        ("45 ml", "45ml", 45.0, "ml", "precise"),
        
        # cl 换算
        ("3 cl", "30ml", 30.0, "ml", "precise"),
        ("4.5 cl", "45ml", 45.0, "ml", "precise"),
        
        # tsp/tbsp 换算
        ("1 tsp", "5ml", 5.0, "ml", "precise"),
        ("1 tbsp", "15ml", 15.0, "ml", "precise"),
        ("2 teaspoon", "10ml", 10.0, "ml", "precise"),
        
        # dash (保留)
        ("2 dashes", "2滴", 2.0, "滴", "approximate"),
        ("1 dash", "1滴", 1.0, "滴", "approximate"),
        
        # barspoon (保留)
        ("1 barspoon", "1barspoon", 1.0, "barspoon", "precise"),
        
        # shot
        ("1 shot", "45ml", 45.0, "ml", "precise"),
        
        # 描述性
        ("splash", "少许", None, None, "descriptive"),
        ("to taste", "适量", None, None, "descriptive"),
        ("garnish", "装饰用", None, None, "descriptive"),
        ("top up", "补满", None, None, "descriptive"),
        
        # 边缘情况
        ("", "适量", None, None, "descriptive"),
        ("1/2", "0.5个", 0.5, "个", "unclear"),
    ]
    
    print("=" * 80)
    print("用量规范化测试")
    print("=" * 80)
    print()
    
    passed = 0
    failed = 0
    
    for raw, exp_norm, exp_val, exp_unit, exp_type in test_cases:
        result = normalize_measure(raw)
        
        success = (
            result['normalized'] == exp_norm and
            result.get('value') == exp_val and
            result.get('unit') == exp_unit and
            result['type'] == exp_type
        )
        
        if success:
            passed += 1
            status = "✅ PASS"
        else:
            failed += 1
            status = "❌ FAIL"
        
        print(f"{status}  '{raw}'")
        print(f"       期望: {exp_norm} (value={exp_val}, unit={exp_unit}, type={exp_type})")
        print(f"       实际: {result['normalized']} (value={result.get('value')}, unit={result.get('unit')}, type={result['type']})")
        print()
    
    print("=" * 80)
    print(f"测试结果: {passed} 通过, {failed} 失败")
    print("=" * 80)
    
    return failed == 0


if __name__ == '__main__':
    success = run_tests()
    sys.exit(0 if success else 1)
