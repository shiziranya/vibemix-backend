#!/usr/bin/env python3
"""
端到端测试：完整的卡片生成流程
测试从 API 请求到最终生成卡片的整个流程
"""

import requests
import time
import sys
import json

# 配置
BASE_URL = "http://115.191.50.177:5005"
TEST_USER_ID = 1
TEST_COCKTAIL_ID = 100  # English Rose Cocktail

# 获取 JWT Token
def get_auth_token():
    """获取测试用的 JWT Token"""
    try:
        response = requests.post(
            f"{BASE_URL}/api/auth/login",
            json={
                "identifier": "test@example.com",
                "password": "test123456",
                "login_type": "email"
            }
        )
        if response.status_code == 200:
            data = response.json()
            return data["data"]["access_token"]
        else:
            print(f"❌ 登录失败: {response.status_code}")
            print(response.text)
            return None
    except Exception as e:
        print(f"❌ 登录异常: {e}")
        return None


def test_get_templates(token):
    """测试获取模板列表"""
    print("\n" + "="*60)
    print("1️⃣  测试获取模板列表")
    print("="*60)
    
    try:
        response = requests.get(
            f"{BASE_URL}/api/card/templates",
            headers={"Authorization": f"Bearer {token}"}
        )
        
        print(f"状态码: {response.status_code}")
        
        if response.status_code == 200:
            data = response.json()
            templates = data["data"]["templates"]
            print(f"✅ 成功获取 {len(templates)} 个模板")
            print(f"模板列表: {', '.join(templates[:10])}...")
            return templates[0] if templates else None
        else:
            print(f"❌ 失败: {response.text}")
            return None
    except Exception as e:
        print(f"❌ 异常: {e}")
        return None


def test_generate_card(token, template_id):
    """测试生成卡片"""
    print("\n" + "="*60)
    print("2️⃣  测试生成卡片")
    print("="*60)
    
    payload = {
        "cocktail_id": TEST_COCKTAIL_ID,
        "cocktail_name": "English Rose",
        "cocktail_name_zh": "英式玫瑰",
        "ai_copy": "优雅的玫瑰色调，伴随着清新的果香，是一款完美的夏日鸡尾酒。",
        "mood_caption": "浪漫优雅",
        "template_id": template_id,
        "use_system_image": True,
        "ingredients": [
            {
                "name": "Gin",
                "name_zh": "金酒",
                "measure": "45ml"
            },
            {
                "name": "Rose Syrup",
                "name_zh": "玫瑰糖浆",
                "measure": "15ml"
            }
        ]
    }
    
    print(f"请求参数:")
    print(f"  - cocktail_id: {TEST_COCKTAIL_ID}")
    print(f"  - template: {template_id}")
    print(f"  - use_system_image: True")
    
    try:
        response = requests.post(
            f"{BASE_URL}/api/card/generate",
            headers={
                "Authorization": f"Bearer {token}",
                "Content-Type": "application/json"
            },
            json=payload
        )
        
        print(f"状态码: {response.status_code}")
        
        if response.status_code in [200, 201]:
            data = response.json()
            card_id = data["data"]["card_id"]
            status = data["data"]["status"]
            print(f"✅ 卡片生成任务已提交")
            print(f"   Card ID: {card_id}")
            print(f"   状态: {status}")
            return card_id
        else:
            print(f"❌ 失败: {response.text}")
            return None
    except Exception as e:
        print(f"❌ 异常: {e}")
        import traceback
        traceback.print_exc()
        return None


def test_check_status(token, card_id, max_wait=60):
    """测试检查卡片状态"""
    print("\n" + "="*60)
    print("3️⃣  测试检查卡片状态")
    print("="*60)
    
    start_time = time.time()
    check_count = 0
    
    while time.time() - start_time < max_wait:
        check_count += 1
        try:
            response = requests.get(
                f"{BASE_URL}/api/card/{card_id}",
                headers={"Authorization": f"Bearer {token}"}
            )
            
            if response.status_code == 200:
                data = response.json()
                card = data["data"]["card"]
                status = card["status"]
                
                print(f"[检查 #{check_count}] 状态: {status}", end="")
                
                if status == "done":
                    image_url = card.get("image_url")
                    print(f" ✅")
                    print(f"   图片URL: {image_url}")
                    return image_url
                elif status == "failed":
                    error_msg = card.get("error_message", "未知错误")
                    print(f" ❌")
                    print(f"   错误信息: {error_msg}")
                    return None
                else:
                    print(f" ⏳ (等待中...)")
                    time.sleep(3)
            else:
                print(f"\n❌ 查询失败: {response.text}")
                return None
                
        except Exception as e:
            print(f"\n❌ 异常: {e}")
            return None
    
    print(f"\n⚠️  超时：等待了 {max_wait} 秒，卡片仍未生成完成")
    return None


def test_verify_image(image_url):
    """测试验证图片"""
    print("\n" + "="*60)
    print("4️⃣  测试验证图片")
    print("="*60)
    
    if not image_url:
        print("❌ 没有图片URL可供验证")
        return False
    
    # 将相对路径转换为完整 URL
    if image_url.startswith("/"):
        full_url = f"{BASE_URL}{image_url}"
    else:
        full_url = image_url
    
    print(f"图片URL: {full_url}")
    
    try:
        response = requests.head(full_url, timeout=10)
        print(f"状态码: {response.status_code}")
        
        if response.status_code == 200:
            content_type = response.headers.get("Content-Type", "")
            content_length = response.headers.get("Content-Length", "0")
            
            print(f"   Content-Type: {content_type}")
            print(f"   Content-Length: {content_length} bytes")
            
            if "image" in content_type and int(content_length) > 10000:
                print("✅ 图片验证成功！")
                return True
            else:
                print(f"❌ 图片可能无效（太小或类型错误）")
                return False
        else:
            print(f"❌ 无法访问图片")
            return False
    except Exception as e:
        print(f"❌ 验证异常: {e}")
        return False


def main():
    """主测试流程"""
    print("\n" + "="*60)
    print("🚀 开始端到端测试")
    print("="*60)
    
    # 步骤 0: 登录获取 token
    print("\n0️⃣  获取认证 Token...")
    token = get_auth_token()
    if not token:
        print("❌ 无法获取 Token，测试终止")
        # 尝试不使用认证（如果配置允许）
        token = "dummy_token"
        print("⚠️  将尝试不使用认证进行测试")
    else:
        print(f"✅ Token 获取成功")
    
    # 步骤 1: 获取模板
    template_id = test_get_templates(token)
    if not template_id:
        print("\n❌ 无法获取模板，使用默认模板 'circulus'")
        template_id = "circulus"
    
    # 步骤 2: 生成卡片
    card_id = test_generate_card(token, template_id)
    if not card_id:
        print("\n❌ 测试失败：无法提交卡片生成任务")
        sys.exit(1)
    
    # 步骤 3: 检查状态
    image_url = test_check_status(token, card_id, max_wait=90)
    if not image_url:
        print("\n❌ 测试失败：卡片生成失败或超时")
        sys.exit(1)
    
    # 步骤 4: 验证图片
    success = test_verify_image(image_url)
    
    # 最终结果
    print("\n" + "="*60)
    if success:
        print("✅ 端到端测试全部通过！")
        print("="*60)
        print(f"\n生成的卡片URL: {BASE_URL}{image_url if image_url.startswith('/') else image_url}")
        sys.exit(0)
    else:
        print("❌ 端到端测试失败")
        print("="*60)
        sys.exit(1)


if __name__ == "__main__":
    main()
