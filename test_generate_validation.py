#!/usr/bin/env python3
"""
测试 generate 接口的验证和模板系统
"""
import requests
import json

# 配置
API_BASE_URL = "http://localhost:5005/api/card"
# 替换为实际的 token
ACCESS_TOKEN = "YOUR_TOKEN_HERE"

def test_generate_validation():
    """测试不同模板的验证"""
    
    headers = {
        "Authorization": f"Bearer {ACCESS_TOKEN}",
        "Content-Type": "application/json"
    }
    
    # 测试用例
    test_cases = [
        {
            "name": "使用 circulus 模板",
            "data": {
                "cocktail_id": 1,
                "template_id": "circulus"
            }
        },
        {
            "name": "使用 vesper 模板",
            "data": {
                "cocktail_id": 1,
                "template_id": "vesper"
            }
        },
        {
            "name": "使用旧的 amber 模板（应该也通过）",
            "data": {
                "cocktail_id": 1,
                "template_id": "amber"
            }
        },
        {
            "name": "不传模板（使用默认）",
            "data": {
                "cocktail_id": 1
            }
        },
        {
            "name": "无效的 cocktail_id（应该失败）",
            "data": {
                "template_id": "circulus"
            }
        }
    ]
    
    print("=" * 60)
    print("测试 /api/card/generate 接口验证")
    print("=" * 60)
    print()
    
    for i, test in enumerate(test_cases, 1):
        print(f"测试 {i}: {test['name']}")
        print(f"  请求数据: {json.dumps(test['data'], ensure_ascii=False)}")
        
        try:
            response = requests.post(
                f"{API_BASE_URL}/generate",
                headers=headers,
                json=test['data'],
                timeout=5
            )
            
            print(f"  状态码: {response.status_code}")
            
            result = response.json()
            
            if response.status_code == 202:
                print(f"  ✅ 成功: card_id = {result['data']['card_id']}")
            elif response.status_code == 422:
                print(f"  ⚠️  验证失败: {result.get('message', 'Unknown error')}")
            else:
                print(f"  ❌ 失败: {result.get('message', 'Unknown error')}")
                
        except requests.exceptions.ConnectionError:
            print(f"  ❌ 连接失败: 请确保 backend 服务正在运行")
        except Exception as e:
            print(f"  ❌ 错误: {e}")
        
        print()

if __name__ == "__main__":
    print("提示: 请在运行前替换 ACCESS_TOKEN")
    print()
    test_generate_validation()
