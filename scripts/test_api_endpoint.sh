#!/bin/bash
# 测试推荐历史接口的 HTTP 端点

echo "=== 测试推荐历史接口 v1.2 ==="
echo ""

# 1. 先从数据库获取一个测试用户
echo "1. 获取测试用户..."
USER_ID=$(psql postgresql://postgres:postgres123@localhost:5432/tipsy_inspirations -t -c "SELECT user_id FROM recommendation_history LIMIT 1" | xargs)

if [ -z "$USER_ID" ]; then
    echo "❌ 没有找到测试用户"
    exit 1
fi

echo "✓ 测试用户: $USER_ID"
echo ""

# 2. 为该用户生成一个测试 token
echo "2. 生成测试 token..."
cd /opt/vibemix/vibemix-backend
TOKEN=$(python3 -c "
import sys
sys.path.insert(0, '.')
from app import create_app
from flask_jwt_extended import create_access_token

app = create_app()
with app.app_context():
    token = create_access_token(identity='$USER_ID')
    print(token)
")

if [ -z "$TOKEN" ]; then
    echo "❌ token 生成失败"
    exit 1
fi

echo "✓ Token 已生成"
echo ""

# 3. 测试接口
echo "3. 调用接口: GET /api/recommend/history"
RESPONSE=$(curl -s -w "\n%{http_code}" \
  -X GET "http://localhost:5000/api/recommend/history?page=1&per_page=2" \
  -H "Authorization: Bearer $TOKEN")

HTTP_CODE=$(echo "$RESPONSE" | tail -n1)
BODY=$(echo "$RESPONSE" | head -n-1)

echo "HTTP 状态码: $HTTP_CODE"
echo ""

if [ "$HTTP_CODE" != "200" ]; then
    echo "❌ 请求失败"
    echo "$BODY" | jq '.' 2>/dev/null || echo "$BODY"
    exit 1
fi

echo "✓ 请求成功"
echo ""

# 4. 验证响应格式
echo "4. 验证响应格式..."
echo "$BODY" | python3 /opt/vibemix/vibemix-backend/scripts/test_history_api_v12.py

exit $?
