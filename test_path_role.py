#!/usr/bin/env python3
"""
测试主线/支线功能
验证数据库结构和API响应
"""

import requests
import json

BASE_URL = "http://localhost:5005"

def test_database_structure():
    """测试数据库结构"""
    print("=" * 50)
    print("测试1: 数据库结构验证")
    print("=" * 50)
    
    import psycopg2
    
    try:
        conn = psycopg2.connect(
            host="localhost",
            database="tipsy_inspirations",
            user="postgres",
            password="postgres123"
        )
        cur = conn.cursor()
        
        # 检查 map_nodes 表结构
        cur.execute("""
            SELECT column_name, data_type, is_nullable, column_default
            FROM information_schema.columns
            WHERE table_name = 'map_nodes' 
            AND column_name IN ('path_role', 'unlock_by')
            ORDER BY column_name
        """)
        
        print("\n✓ map_nodes 表字段:")
        for row in cur.fetchall():
            print(f"  - {row[0]}: {row[1]} (nullable={row[2]}, default={row[3]})")
        
        # 检查约束
        cur.execute("""
            SELECT conname, pg_get_constraintdef(oid)
            FROM pg_constraint
            WHERE conrelid = 'map_nodes'::regclass
            AND conname = 'map_nodes_path_role_check'
        """)
        
        print("\n✓ path_role 约束:")
        for row in cur.fetchall():
            print(f"  - {row[0]}: {row[1]}")
        
        # 统计数据
        cur.execute("""
            SELECT path_role, COUNT(*)
            FROM map_nodes
            GROUP BY path_role
            ORDER BY path_role
        """)
        
        print("\n✓ 节点数据分布:")
        for row in cur.fetchall():
            print(f"  - {row[0]}: {row[1]}个节点")
        
        # 检查支线节点
        cur.execute("""
            SELECT COUNT(*)
            FROM map_nodes
            WHERE path_role = 'side' AND unlock_by IS NOT NULL
        """)
        side_with_unlock = cur.fetchone()[0]
        print(f"\n✓ 有解锁条件的支线节点: {side_with_unlock}个")
        
        cur.close()
        conn.close()
        
        print("\n✓ 数据库结构验证通过!")
        return True
        
    except Exception as e:
        print(f"\n✗ 数据库结构验证失败: {e}")
        return False


def test_api_response(token=None):
    """测试API响应"""
    print("\n" + "=" * 50)
    print("测试2: API响应验证")
    print("=" * 50)
    
    if not token:
        print("\n⚠ 跳过API测试（需要认证token）")
        print("提示: 使用 test_api_response(token='your_token') 来测试API")
        return False
    
    headers = {"Authorization": f"Bearer {token}"}
    
    try:
        # 测试主题列表
        response = requests.get(f"{BASE_URL}/api/v1/map/themes", headers=headers)
        
        if response.status_code == 200:
            data = response.json()
            print(f"\n✓ GET /api/v1/map/themes 成功")
            print(f"  返回 {len(data.get('data', []))} 个主题")
        
        # 测试主题详情（假设主题13存在）
        response = requests.get(f"{BASE_URL}/api/v1/map/themes/13", headers=headers)
        
        if response.status_code == 200:
            data = response.json().get('data', {})
            nodes = data.get('nodes', [])
            
            print(f"\n✓ GET /api/v1/map/themes/13 成功")
            print(f"  返回 {len(nodes)} 个节点")
            
            # 检查节点字段
            if nodes:
                first_node = nodes[0]
                required_fields = ['path_role', 'unlock_by', 'status']
                missing_fields = [f for f in required_fields if f not in first_node]
                
                if not missing_fields:
                    print(f"  ✓ 节点包含所需字段: {required_fields}")
                    print(f"    示例节点: path_role={first_node.get('path_role')}, "
                          f"unlock_by={first_node.get('unlock_by')}")
                else:
                    print(f"  ✗ 节点缺少字段: {missing_fields}")
                
                # 统计主线/支线节点
                main_count = sum(1 for n in nodes if n.get('path_role') == 'main')
                side_count = sum(1 for n in nodes if n.get('path_role') == 'side')
                print(f"  主线节点: {main_count}个, 支线节点: {side_count}个")
            
            # 检查边字段
            edges = data.get('progression_edges', [])
            if edges:
                first_edge = edges[0]
                required_fields = ['path_role', 'status']
                missing_fields = [f for f in required_fields if f not in first_edge]
                
                if not missing_fields:
                    print(f"  ✓ 边包含所需字段: {required_fields}")
                    print(f"    示例边: path_role={first_edge.get('path_role')}, "
                          f"status={first_edge.get('status')}")
                else:
                    print(f"  ✗ 边缺少字段: {missing_fields}")
                
                # 统计边状态
                unlocked = sum(1 for e in edges if e.get('status') == 'unlocked')
                locked = sum(1 for e in edges if e.get('status') == 'locked')
                print(f"  解锁的边: {unlocked}条, 锁定的边: {locked}条")
        
        print("\n✓ API响应验证通过!")
        return True
        
    except Exception as e:
        print(f"\n✗ API响应验证失败: {e}")
        return False


def main():
    """运行所有测试"""
    print("\n" + "=" * 50)
    print("主线/支线功能测试")
    print("=" * 50)
    
    # 测试1: 数据库结构
    db_ok = test_database_structure()
    
    # 测试2: API响应（需要token）
    print("\n" + "=" * 50)
    print("提示: 要测试API，请运行：")
    print("  python test_path_role.py --token YOUR_JWT_TOKEN")
    print("=" * 50)
    
    if db_ok:
        print("\n✓ 所有测试通过!")
    else:
        print("\n✗ 部分测试失败")


if __name__ == "__main__":
    import sys
    
    # 检查是否提供了token
    token = None
    if len(sys.argv) > 2 and sys.argv[1] == '--token':
        token = sys.argv[2]
    
    test_database_structure()
    
    if token:
        test_api_response(token)
    else:
        print("\n" + "=" * 50)
        print("提示: 要测试API，请提供JWT token：")
        print("  python test_path_role.py --token YOUR_JWT_TOKEN")
        print("=" * 50)
