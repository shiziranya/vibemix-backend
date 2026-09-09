#!/usr/bin/env python3
"""
测试新的 /api/card/templates/with-ingredients 接口
"""
import requests

BASE_URL = "http://115.191.50.177:5005"

# 不需要真实 token，先测试接口是否存在
response = requests.get(
    f"{BASE_URL}/api/card/templates/with-ingredients",
    headers={"Authorization": "Bearer test_token"}
)

print(f"Status Code: {response.status_code}")
print(f"Response: {response.text[:500]}")

if response.status_code == 422:  # JWT 验证失败
    print("\n✅ 接口存在（需要有效的 JWT token）")
elif response.status_code == 200:
    import json
    data = response.json()
    print("\n✅ 接口调用成功！")
    print(f"支持配料的模板数量: {data['data']['total']}")
    print(f"模板列表: {data['data']['templates']}")
else:
    print(f"\n❌ 接口调用失败: {response.status_code}")
