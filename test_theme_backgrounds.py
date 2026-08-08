#!/usr/bin/env python3
"""
主题背景图接口测试脚本
用于验证 background_url 字段是否正确返回
"""

import os
import sys
os.environ['FLASK_ENV'] = 'production'

from app import create_app
from flask_jwt_extended import create_access_token
import requests
import json

def test_theme_background_urls():
    app = create_app()
    
    with app.app_context():
        from app.extensions import db
        from sqlalchemy import text
        
        # 获取测试用户
        user = db.session.execute(text("SELECT id FROM users LIMIT 1")).fetchone()
        
        if not user:
            print("❌ 数据库中没有用户，无法测试")
            return False
        
        token = create_access_token(identity=str(user.id))
        headers = {'Authorization': f'Bearer {token}'}
        base_url = 'http://115.191.50.177:5005'
        
        print("=" * 70)
        print("  主题背景图接口测试")
        print("=" * 70)
        
        # 测试接口 1: GET /api/v1/map/user/stats
        print("\n1️⃣  测试接口: GET /api/v1/map/user/stats")
        print("-" * 70)
        
        response = requests.get(f'{base_url}/api/v1/map/user/stats', headers=headers)
        
        if response.status_code == 200:
            data = response.json()
            if data.get('code') == 0:
                themes = data['data']['themes']
                has_bg = sum(1 for t in themes if t.get('background_url'))
                
                print(f"✅ 接口正常 (状态码: 200)")
                print(f"📊 主题总数: {len(themes)}")
                print(f"🖼️  已配置背景图: {has_bg} 个\n")
                
                for theme in themes[:7]:  # 只显示前7个
                    bg = theme.get('background_url')
                    icon = '✓' if bg else '✗'
                    print(f"   {icon} 主题 {theme['theme_id']:2d} ({theme['name_zh']:8s}): {bg or '未设置'}")
            else:
                print(f"❌ 接口返回错误: {data.get('message')}")
                return False
        else:
            print(f"❌ HTTP 错误: {response.status_code}")
            return False
        
        # 测试接口 2: GET /api/v1/map/themes/{theme_id}
        print("\n2️⃣  测试接口: GET /api/v1/map/themes/:theme_id")
        print("-" * 70)
        
        test_themes = [14, 15, 16]
        all_passed = True
        
        for theme_id in test_themes:
            response = requests.get(f'{base_url}/api/v1/map/themes/{theme_id}', headers=headers)
            
            if response.status_code == 200:
                data = response.json()
                if data.get('code') == 0:
                    theme = data['data']['theme']
                    bg_url = theme.get('background_url')
                    
                    if bg_url:
                        print(f"✅ 主题 {theme_id} ({theme['name_zh']})")
                        print(f"   background_url: {bg_url}")
                    else:
                        print(f"⚠️  主题 {theme_id} ({theme['name_zh']}): background_url 为 null")
                else:
                    print(f"❌ 主题 {theme_id}: {data.get('message')}")
                    all_passed = False
            else:
                print(f"❌ 主题 {theme_id}: HTTP {response.status_code}")
                all_passed = False
        
        print("\n" + "=" * 70)
        if all_passed:
            print("🎉 所有测试通过！")
        else:
            print("⚠️  部分测试失败")
        print("=" * 70)
        
        return all_passed

if __name__ == '__main__':
    success = test_theme_background_urls()
    sys.exit(0 if success else 1)
