#!/usr/bin/env python3
"""
服务状态检查脚本
检查卡片生成相关的所有服务是否正常运行
"""

import requests
import subprocess
import sys

def check_service(name, check_func):
    """检查服务状态"""
    print(f"\n{'='*60}")
    print(f"检查 {name}")
    print('='*60)
    try:
        result = check_func()
        if result:
            print(f"✅ {name} 正常运行")
            return True
        else:
            print(f"❌ {name} 运行异常")
            return False
    except Exception as e:
        print(f"❌ {name} 检查失败: {e}")
        return False


def check_redis():
    """检查 Redis"""
    result = subprocess.run(
        ["redis-cli", "ping"],
        capture_output=True,
        text=True
    )
    if result.returncode == 0 and "PONG" in result.stdout:
        print("   连接状态: ✅ 正常")
        # 获取连接数
        result = subprocess.run(
            ["redis-cli", "info", "clients"],
            capture_output=True,
            text=True
        )
        for line in result.stdout.split('\n'):
            if 'connected_clients' in line:
                print(f"   {line.strip()}")
        return True
    return False


def check_card_gen():
    """检查 card_gen 服务"""
    try:
        response = requests.get("http://localhost:8001/health", timeout=5)
        if response.status_code == 200:
            data = response.json()
            templates = data.get("templates", [])
            print(f"   状态: {data.get('status')}")
            print(f"   可用模板: {len(templates)} 个")
            print(f"   模板示例: {', '.join(templates[:5])}...")
            return True
        else:
            print(f"   HTTP 状态码: {response.status_code}")
            return False
    except requests.exceptions.ConnectionError:
        print("   ❌ 无法连接到 card_gen 服务 (http://localhost:8001)")
        return False
    except Exception as e:
        print(f"   ❌ 错误: {e}")
        return False


def check_celery():
    """检查 Celery Worker"""
    result = subprocess.run(
        ["ps", "aux"],
        capture_output=True,
        text=True
    )
    
    celery_processes = [
        line for line in result.stdout.split('\n')
        if 'celery' in line.lower() and 'worker' in line.lower() and 'grep' not in line
    ]
    
    if celery_processes:
        print(f"   运行中的 Worker 进程: {len(celery_processes)}")
        for proc in celery_processes[:3]:  # 只显示前3个
            # 提取 PID 和关键信息
            parts = proc.split()
            if len(parts) >= 2:
                print(f"   - PID: {parts[1]}")
        return True
    else:
        print("   ❌ 没有找到运行中的 Celery Worker")
        return False


def check_flask():
    """检查 Flask 后端"""
    result = subprocess.run(
        ["ps", "aux"],
        capture_output=True,
        text=True
    )
    
    flask_processes = [
        line for line in result.stdout.split('\n')
        if ('run.py' in line or 'flask' in line.lower() or 'gunicorn' in line.lower())
        and 'grep' not in line
    ]
    
    if flask_processes:
        print(f"   运行中的 Flask 进程: {len(flask_processes)}")
        for proc in flask_processes[:2]:
            parts = proc.split()
            if len(parts) >= 2:
                print(f"   - PID: {parts[1]}")
        
        # 尝试访问一个公开的端点
        try:
            response = requests.get("http://115.191.50.177:5005", timeout=5)
            print(f"   HTTP 连接: ✅ 可访问 (状态码: {response.status_code})")
        except:
            print(f"   HTTP 连接: ⚠️  无法访问")
        
        return True
    else:
        print("   ❌ 没有找到运行中的 Flask 进程")
        return False


def check_playwright():
    """检查 Playwright 浏览器"""
    try:
        result = subprocess.run(
            ["bash", "-c", "cd /opt/vibemix/card_gen && source venv/bin/activate && playwright --version"],
            capture_output=True,
            text=True
        )
        if result.returncode == 0:
            print(f"   版本: {result.stdout.strip()}")
            
            # 检查浏览器安装
            import os
            chromium_path = "/root/.cache/ms-playwright"
            if os.path.exists(chromium_path):
                chromium_dirs = [d for d in os.listdir(chromium_path) if 'chromium' in d.lower()]
                if chromium_dirs:
                    print(f"   已安装浏览器: {', '.join(chromium_dirs)}")
                    return True
            print("   ⚠️  浏览器未安装")
            return False
    except Exception as e:
        print(f"   ❌ 错误: {e}")
        return False


def main():
    """主检查流程"""
    print("\n" + "="*60)
    print("🔍 VibeMix 卡片生成服务状态检查")
    print("="*60)
    
    results = {}
    
    # 检查各个服务
    results["Redis"] = check_service("Redis 消息队列", check_redis)
    results["card_gen"] = check_service("card_gen 生成服务", check_card_gen)
    results["Celery"] = check_service("Celery Worker", check_celery)
    results["Flask"] = check_service("Flask 后端", check_flask)
    results["Playwright"] = check_service("Playwright 浏览器", check_playwright)
    
    # 总结
    print("\n" + "="*60)
    print("📊 总结")
    print("="*60)
    
    all_ok = all(results.values())
    ok_count = sum(results.values())
    total_count = len(results)
    
    for service, status in results.items():
        icon = "✅" if status else "❌"
        print(f"{icon} {service}")
    
    print(f"\n状态: {ok_count}/{total_count} 服务正常")
    
    if all_ok:
        print("\n✅ 所有服务运行正常！")
        print("\n下一步：")
        print("1. 使用有效的用户凭证测试完整的 API 流程")
        print("2. 或者使用 test_card_generation.py 进行直接服务测试")
        return 0
    else:
        print("\n❌ 部分服务异常，请检查上述失败的服务")
        return 1


if __name__ == "__main__":
    sys.exit(main())
