# v1.2 推荐历史接口格式调整 - 迁移指南

## 概述

将推荐历史接口 (`GET /api/recommend/history`) 的返回格式调整为与推荐接口 (`POST /api/recommend`) 保持一致。

**版本**: v1.2  
**日期**: 2026-08-29

## 变更内容

### 1. 数据库变更

添加新字段到 `recommendation_history` 表：

```sql
ALTER TABLE recommendation_history
ADD COLUMN IF NOT EXISTS ai_mood_caption TEXT;
```

### 2. API 返回格式变更

**旧格式 (v1.1)**:
```json
{
  "items": [
    {
      "cocktail": {
        "ingredients": [...]  // ingredients 在 cocktail 内
      },
      "ai": {
        "reason": "...",
        "poetic_copy": "..."
        // 缺少 mood_caption
      }
    }
  ]
}
```

**新格式 (v1.2)**:
```json
{
  "items": [
    {
      "cocktail": {...},        // 基本信息，不含 ingredients
      "ingredients": [...],     // 移到顶层，包含 status 和 substitute
      "ai": {
        "reason": "...",
        "poetic_copy": "...",
        "mood_caption": "..."   // 新增字段
      }
    }
  ]
}
```

### 3. 新增字段

**ingredients 数组项**:
- `status`: 原料拥有状态 (`owned`/`missing`/`available`)
- `substitute`: 替代建议文本 (无替代时为 `null`)

**ai 对象**:
- `mood_caption`: AI 生成的心情文案

## 迁移步骤

### 1. 应用数据库迁移

```bash
cd /opt/vibemix/vibemix-backend
psql -U your_user -d your_database -f migrations/011_add_ai_mood_caption.sql
```

或使用你的数据库迁移工具。

### 2. 重启后端服务

```bash
# 停止服务
sudo systemctl stop vibemix-backend

# 启动服务
sudo systemctl start vibemix-backend

# 查看日志
sudo journalctl -u vibemix-backend -f
```

### 3. 前端调整

#### 数据结构调整

```javascript
// v1.1 旧格式
const ingredients = item.cocktail.ingredients;

// v1.2 新格式
const ingredients = item.ingredients;
```

#### 向后兼容方案

如果需要同时支持新旧版本：

```javascript
// 兼容写法
const ingredients = item.ingredients || item.cocktail?.ingredients || [];
const moodCaption = item.ai?.mood_caption || '';
```

#### 使用新字段

```javascript
// 显示原料拥有状态
ingredients.forEach(ing => {
  const statusBadge = {
    'owned': { text: '已拥有', color: 'green' },
    'missing': { text: '缺失', color: 'red' },
    'available': { text: '便利店可买', color: 'blue' }
  }[ing.status];
  
  // 显示替代建议
  if (ing.substitute) {
    console.log(`替代建议: ${ing.substitute}`);
  }
});

// 使用心情文案
if (item.ai.mood_caption) {
  displayMoodCaption(item.ai.mood_caption);
}
```

## 测试验证

### 1. 测试推荐历史接口

```bash
# 获取推荐历史
curl -X GET "http://localhost:5000/api/recommend/history?page=1&per_page=5" \
  -H "Authorization: Bearer YOUR_TOKEN" | jq
```

**验证点**:
- ✅ `items[].ingredients` 在顶层（与 `cocktail` 同级）
- ✅ `items[].ingredients[].status` 字段存在
- ✅ `items[].ingredients[].substitute` 字段存在
- ✅ `items[].ai.mood_caption` 字段存在
- ✅ `items[].cocktail` 不包含 `ingredients`

### 2. 测试新推荐保存

```bash
# 发起新推荐
curl -X POST "http://localhost:5000/api/recommend" \
  -H "Authorization: Bearer YOUR_TOKEN" \
  -H "Content-Type: application/json" \
  -d '{
    "mood_tags": ["relaxing"],
    "abv_pref": "low",
    "recipe_type": "classic"
  }' | jq

# 再次获取历史，验证 mood_caption 已保存
curl -X GET "http://localhost:5000/api/recommend/history?page=1&per_page=1" \
  -H "Authorization: Bearer YOUR_TOKEN" | jq '.data.items[0].ai.mood_caption'
```

## 回滚方案

如果需要回滚：

### 1. 后端回滚

```bash
# 切换到旧版本代码
git checkout <previous-commit-hash>

# 重启服务
sudo systemctl restart vibemix-backend
```

### 2. 数据库回滚（可选）

```sql
-- 删除新添加的字段（可选，保留也不影响旧版本）
ALTER TABLE recommendation_history
DROP COLUMN IF EXISTS ai_mood_caption;
```

**注意**: `ai_mood_caption` 字段在旧版本中会被忽略，保留该字段不会影响系统运行。

## 常见问题

### Q1: 旧的推荐记录没有 mood_caption 怎么办？

**A**: 旧记录的 `mood_caption` 会是 `null` 或空字符串，前端应该优雅处理：

```javascript
const caption = item.ai?.mood_caption || '';
if (caption) {
  // 显示心情文案
}
```

### Q2: status 和 substitute 计算会影响性能吗？

**A**: 不会。这些字段在查询时实时计算，基于用户的酒柜数据。已经添加了必要的数据库索引优化查询性能。

### Q3: 前端必须立即升级吗？

**A**: 建议同步升级，但如果使用兼容写法，旧版前端可以继续工作：

```javascript
const ingredients = item.ingredients || item.cocktail?.ingredients || [];
```

## 相关文档

- [API 文档](/opt/vibemix/API_我的卡片和推荐.md)
- [后端设计文档](/opt/vibemix/backend_design.md)

## 联系方式

如有问题，请联系开发团队。
