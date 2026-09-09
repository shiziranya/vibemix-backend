# Migration 014: 添加推荐关联功能

## 概述
将用户收藏的鸡尾酒关联到 LLM 推荐记录，使前端可以查询推荐详情。

## 执行迁移

```bash
# 连接到数据库并执行迁移
psql -h <host> -U <user> -d vibemix < migrations/014_add_recommendation_id_to_saved_cocktails.sql
```

## 修改内容

### 1. 数据库变更
- 在 `user_saved_cocktails` 表添加 `recommendation_id` 字段
- 外键关联到 `recommendation_history.id`
- 删除推荐记录时，收藏记录的 `recommendation_id` 自动设为 NULL
- 添加索引优化查询性能

### 2. 模型变更 (`app/models/saved_cocktail.py`)
- 添加 `recommendation_id: Mapped[Optional[int]]` 字段
- 在 `to_dict()` 方法中返回 `recommendation_id`

### 3. Service 层变更 (`app/services/menu_service.py`)
- `add_to_favorites()`: 添加 `recommendation_id` 参数
- `add_to_today()`: 添加 `recommendation_id` 参数
- `_build_saved_cocktail_response()`: 在响应中包含 `recommendation_id`

### 4. API 层变更 (`app/api/menu.py`)
- `POST /api/menu/favorites`: 接受 `recommendation_id` 参数
- `POST /api/menu/today`: 接受 `recommendation_id` 参数
- `GET /api/menu/favorites`: 响应中包含 `recommendation_id`
- `GET /api/menu/today`: 响应中包含 `recommendation_id`

## API 使用示例

### 添加收藏（来自推荐）
```json
POST /api/menu/favorites
{
    "cocktail_id": 123,
    "note": "很喜欢这个推荐",
    "recommendation_id": 456
}
```

### 获取收藏列表
```json
GET /api/menu/favorites

Response:
{
    "code": 0,
    "data": {
        "total": 1,
        "cocktails": [
            {
                "saved_id": 1,
                "recommendation_id": 456,
                "is_in_today": false,
                "cocktail": { ... }
            }
        ]
    }
}
```

### 前端使用推荐ID查询详情
```javascript
// 1. 获取收藏列表
const { cocktails } = await fetch('/api/menu/favorites').then(r => r.json())

// 2. 如果有推荐ID，可以查询推荐详情
const cocktail = cocktails[0]
if (cocktail.recommendation_id) {
    const recommendation = await fetch(
        `/api/recommend/history/${cocktail.recommendation_id}`
    ).then(r => r.json())
    
    // recommendation 包含 ai_reason, ai_poetic, ai_mood_caption 等字段
}
```

## 向后兼容性
- ✅ `recommendation_id` 是可选字段，默认为 NULL
- ✅ 现有的收藏记录不受影响
- ✅ API 参数向后兼容，不传 `recommendation_id` 也能正常工作

## 验证
1. 执行迁移后，检查字段是否添加成功：
   ```sql
   \d user_saved_cocktails
   ```
2. 测试添加收藏（带推荐ID）
3. 测试添加收藏（不带推荐ID）
4. 测试获取收藏列表，确认返回 recommendation_id
