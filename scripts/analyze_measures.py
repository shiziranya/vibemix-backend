#!/usr/bin/env python3
"""分析 cocktail_map.json 中的 measure_raw 数据"""

import json
import sys
from collections import Counter

def main():
    with open('/opt/vibemix/cocktail_map.json', 'r', encoding='utf-8') as f:
        data = json.load(f)
    
    measures = []
    for node in data.get('nodes', []):
        ingredients = node.get('ingredients')
        if ingredients:
            for ing in ingredients:
                measure_raw = ing.get('measure_raw')
                if measure_raw:
                    measures.append(measure_raw)
    
    print(f"总共找到 {len(measures)} 条用量记录\n")
    print("=" * 80)
    print("出现频次最高的 measure_raw 值：\n")
    
    counter = Counter(measures)
    for measure, count in counter.most_common(50):
        print(f"{count:4d}x  {measure}")
    
    print("\n" + "=" * 80)
    print(f"唯一值数量: {len(counter)}")

if __name__ == '__main__':
    main()
