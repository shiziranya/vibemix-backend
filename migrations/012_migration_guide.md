# 卡片存储鸡尾酒名称和AI诗意描述 - 迁移指南

## 概述

在 `share_cards` 表中添加 `cocktail_name` 和 `ai_poetic` 字段，用于存储鸡尾酒名称和 AI 生成的诗意描述。

**版本**: v1.3  
**日期**: 2026-08-29

## 变更内容

### 1. 数据库变更

添加新字段到 `share_cards` 表：

```sql
ALTER TABLE share_cards
    ADD COLUMN IF NOT EXISTS cocktail_name VARCHAR(200),
    ADD COLUMN IF NOT EXISTS ai_poetic TEXT;
```

### 2. 数据模型变更

**ShareCard 模型新增字段**:
- `cocktail_name`: 鸡尾酒名称（VARCHAR(200)）
- `ai_poetic`: AI生成的诗意描述（TEXT）

### 3. API 返回格式变更

#### 卡片相关接口

**涉及的接口**:
- `POST /api/card/generate` - 生成卡片
- `POST /api/card/submit` - 提交前端渲染的卡片
- `GET /api/card/{card_id}` - 获取单个卡片
- `GET /api/card/my` - 获取我的卡片列表
- `GET /api/diary/date/{date}` - 获取指定日期的卡片

**新增返回字段**:
```json
{
  "card_id": "...",
  "cocktail_id": 123,
  "cocktail_name": "Mojito",        // 新增：鸡尾酒名称
  "ai_poetic": "清新如夏日微风...",  // 新增：AI诗意描述
  "image_url": "...",
  "status": "done",
  ...
}
```

### 4. 请求参数变更

#### POST /api/card/generate

**新增请求参数**:
```json
{
  "cocktail_id": 123,
  "ai_poetic": "清新如夏日微风，薄荷与朗姆的完美邂逅",  // 可选
  "user_photo_url": "...",
  "mood_caption": "...",
  ...
}
```

#### POST /api/card/submit

**新增表单字段**:
- `ai_poetic` (可选): AI 生成的诗意描述

### 5. 代码变更

**修改的文件**:
1. `/app/models/share_card.py` - 添加字段定义和 to_dict 方法
2. `/app/api/card.py` - 更新创建卡片逻辑，保存新字段
3. `/app/api/diary.py` - 更新返回格式，包含新字段
4. `/app/services/map_service.py` - 更新地图服务中的卡片创建逻辑

## 迁移步骤

### 1. 应用数据库迁移

迁移已自动应用。如需手动应用：

```bash
cd /opt/vibemix/vibemix-backend
PGPASSWORD=postgres123 psql -h localhost -U postgres -d tipsy_inspirations -f migrations/012_add_cocktail_name_and_ai_poetic.sql
```

### 2. 验证数据库结构

```bash
PGPASSWORD=postgres123 psql -h localhost -U postgres -d tipsy_inspirations -c "\d share_cards"
```

应该看到新增的字段：
- `cocktail_name` | character varying(200)
- `ai_poetic` | text

### 3. 重启后端服务（如果已在运行）

```bash
# 停止服务
sudo systemctl stop vibemix-backend

# 启动服务
sudo systemctl start vibemix-backend

# 查看日志
sudo journalctl -u vibemix-backend -f
```

## 使用场景

### 1. 卡片数据快照

即使原始鸡尾酒被删除或修改，卡片仍保留创建时的鸡尾酒名称：

```python
card = ShareCard(
    cocktail_id=123,
    cocktail_name=cocktail.name,  # 保存快照
    ai_poetic="清新如夏日微风...",
    ...
)
```

### 2. 显示AI诗意描述

在卡片上展示更富有诗意的描述，而不仅仅是配方信息：

```javascript
// 前端使用
const card = await fetchCard(cardId);
console.log(card.cocktail_name);  // "Mojito"
console.log(card.ai_poetic);      // "清新如夏日微风，薄荷与朗姆的完美邂逅"
```

### 3. 向后兼容

旧的卡片记录中这两个字段为 `null`，前端应该优雅处理：

```javascript
const cocktailName = card.cocktail_name || card.cocktail?.name || '未知鸡尾酒';
const poeticDesc = card.ai_poetic || '';
```

## 测试验证

### 1. 测试创建卡片

```bash
# 生成卡片
curl -X POST "http://localhost:5005/api/card/generate" \
  -H "Authorization: Bearer YOUR_TOKEN" \
  -H "Content-Type: application/json" \
  -d '{
    "cocktail_id": 1,
    "ai_poetic": "清新如夏日微风，薄荷与朗姆的完美邂逅",
    "mood_caption": "今天想喝点清爽的"
  }' | jq
```

### 2. 测试获取卡片

```bash
# 获取单个卡片
curl -X GET "http://localhost:5005/api/card/{card_id}" \
  -H "Authorization: Bearer YOUR_TOKEN" | jq '.data'
```

**验证点**:
- ✅ `cocktail_name` 字段存在且正确
- ✅ `ai_poetic` 字段存在且正确
- ✅ 其他字段正常返回

### 3. 测试日记接口

```bash
# 获取指定日期的卡片
curl -X GET "http://localhost:5005/api/diary/date/2026-08-29" \
  -H "Authorization: Bearer YOUR_TOKEN" | jq '.data.cards[0]'
```

**验证点**:
- ✅ 返回的卡片包含 `cocktail_name`
- ✅ 返回的卡片包含 `ai_poetic`

## 数据迁移注意事项

### 旧数据处理

现有的卡片记录中 `cocktail_name` 和 `ai_poetic` 字段为 `null`。如果需要回填数据：

```sql
-- 回填鸡尾酒名称（如果关联还存在）
UPDATE share_cards sc
SET cocktail_name = c.name
FROM cocktails c
WHERE sc.cocktail_id = c.id
  AND sc.cocktail_name IS NULL;
```

**注意**: `ai_poetic` 字段通常无法回填，因为这是创建卡片时生成的特定内容。

## 常见问题

### Q1: 旧卡片的 cocktail_name 是空的怎么办？

**A**: 前端应该优雅降级处理：

```javascript
const displayName = card.cocktail_name || card.cocktail?.name || '未知鸡尾酒';
```

### Q2: 为什么要存储 cocktail_name 而不是直接从 cocktail 表读取？

**A**: 
1. **数据快照**: 保留创建卡片时的鸡尾酒名称，即使后续鸡尾酒被修改或删除
2. **性能优化**: 减少 JOIN 查询
3. **数据完整性**: 即使关联的鸡尾酒被删除，卡片信息依然完整

### Q3: ai_poetic 和 mood_caption 有什么区别？

**A**:
- `mood_caption`: 用户输入的心情文案，描述用户当时的心情或场景
- `ai_poetic`: AI 生成的诗意描述，通常是对鸡尾酒本身的艺术化描述

两者配合使用，可以让卡片更加丰富和个性化。

## 回滚方案

如果需要回滚：

### 1. 后端代码回滚

```bash
# 切换到旧版本
git checkout <previous-commit-hash>

# 重启服务
sudo systemctl restart vibemix-backend
```

### 2. 数据库回滚（可选）

```sql
-- 删除新添加的字段（可选，保留也不影响旧版本）
ALTER TABLE share_cards
    DROP COLUMN IF EXISTS cocktail_name,
    DROP COLUMN IF EXISTS ai_poetic;
```

**注意**: 这两个字段在旧版本中会被忽略，保留这些字段不会影响系统运行。

## 相关文档

- [API 文档](/opt/vibemix/API_我的卡片和推荐.md)
- [后端设计文档](/opt/vibemix/backend_design.md)
- [迁移 SQL](/opt/vibemix/vibemix-backend/migrations/012_add_cocktail_name_and_ai_poetic.sql)

## 变更总结

✅ 数据库迁移已应用  
✅ 数据模型已更新  
✅ API 接口已更新  
✅ 所有相关接口已支持新字段  
✅ 向后兼容已处理  

---

**迁移完成时间**: 2026-08-29  
**迁移状态**: 成功 ✅
