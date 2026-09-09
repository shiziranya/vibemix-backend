#!/usr/bin/env python3
"""
测试API返回的图片URL格式
"""
from app import create_app
from app.services.cocktail_service import cocktail_service
import json

app = create_app()

with app.app_context():
    print("=" * 80)
    print("API接口图片URL返回测试")
    print("=" * 80)
    
    # 测试1: 搜索接口
    print("\n【测试1】GET /api/v1/cocktails (搜索接口)")
    print("-" * 80)
    results = cocktail_service.search(limit=5)
    print(f"返回 {len(results)} 条记录\n")
    
    for i, item in enumerate(results, 1):
        print(f"{i}. ID: {item['id']:4d} | {item['name']}")
        print(f"   中文名: {item.get('name_zh', '无')}")
        print(f"   图片URL: {item.get('image_url', '无')}")
        
        # 验证URL格式
        url = item.get('image_url', '')
        if url:
            if url.startswith('http://') or url.startswith('https://'):
                print(f"   ✓ URL格式正确（完整URL）")
            else:
                print(f"   ✗ URL格式错误（相对路径）")
        print()
    
    # 测试2: 详情接口
    print("\n【测试2】GET /api/v1/cocktails/<id> (详情接口)")
    print("-" * 80)
    detail = cocktail_service.get_detail(904, user_id=None)
    
    print(f"鸡尾酒: {detail['name']} ({detail.get('name_zh', '无')})")
    print(f"ID: {detail['id']}")
    print(f"分类: {detail.get('category', '无')}")
    print(f"图片URL: {detail.get('image_url', '无')}")
    
    # 验证详情数据
    url = detail.get('image_url', '')
    if url:
        if url.startswith('http://') or url.startswith('https://'):
            print(f"✓ URL格式正确（完整URL）")
        else:
            print(f"✗ URL格式错误（相对路径）")
    
    print(f"\n其他字段:")
    print(f"  原料: {len(detail.get('ingredients', []))} 个")
    print(f"  步骤: {len(detail.get('steps', []))} 步")
    print(f"  难度: {detail.get('difficulty', '无')}")
    print(f"  酒精度: {detail.get('abv_level', '无')}")
    
    # 测试3: JSON序列化
    print("\n【测试3】JSON序列化测试")
    print("-" * 80)
    try:
        json_str = json.dumps(detail, ensure_ascii=False)
        print(f"✓ JSON序列化成功，长度: {len(json_str)} 字符")
        
        # 检查JSON中的image_url
        detail_obj = json.loads(json_str)
        url = detail_obj.get('image_url', '')
        if url and (url.startswith('http://') or url.startswith('https://')):
            print(f"✓ JSON中的image_url格式正确")
        else:
            print(f"✗ JSON中的image_url格式错误: {url}")
    except Exception as e:
        print(f"✗ JSON序列化失败: {e}")
    
    print("\n" + "=" * 80)
    print("测试完成")
    print("=" * 80)
