# 优先使用AI返回的鸡尾酒名称

## 变更原因

在**原创特调模式**（original mode）下，AI 会为鸡尾酒起一个有创意、有梗的新名字，比如：

- "电子布洛芬" - 适合被领导骂了想喝烈的
- "勿扰模式" - 不想说话的时候
- "工位度假计划" - 想喝热带风味的

这些名字比原始配方的标准名称更有个性，更符合用户当时的情绪和场景。因此，在保存卡片时应该**优先使用AI返回的名称**，而不是数据库中的标准名称。

## 变更内容

### 1. 卡片生成接口 - POST /api/card/generate

**请求参数新增**:
```json
{
  "cocktail_id": 123,
  "cocktail_name": "电子布洛芬",           // 新增：AI返回的名称（可选）
  "cocktail_name_zh": "电子布洛芬",        // 新增：AI返回的中文名称（可选）
  "ai_poetic": "解决不了领导，先解决这杯", // AI诗意描述（可选）
  "mood_caption": "...",
  ...
}
```

**逻辑变更**:
```python
# 优先使用AI返回的名称，降级到数据库名称
cocktail_name = data.get("cocktail_name") or cocktail.name

card = ShareCard(
    cocktail_name=cocktail_name,  # 保存AI改名后的名称
    ...
)
```

### 2. 卡片提交接口 - POST /api/card/submit

**表单字段新增**:
```
cocktail_name  (可选)  AI返回的鸡尾酒名称
ai_poetic      (可选)  AI生成的诗意描述
```

**逻辑变更**:
```python
# 优先使用AI返回的名称，降级到数据库名称
cocktail_name = request.form.get("cocktail_name") or cocktail.name

card = ShareCard(
    cocktail_name=cocktail_name,
    ...
)
```

### 3. 地图服务 - map_service.py

**card_params 参数新增**:
```python
card_params = {
    "cocktail_name": "电子布洛芬",  # AI返回的名称（可选）
    "ai_poetic": "...",
    ...
}
```

**逻辑变更**:
```python
# 优先使用AI返回的名称，降级到数据库名称
cocktail_name = card_params.get("cocktail_name") or cocktail.name

card = ShareCard(
    cocktail_name=cocktail_name,
    ...
)
```

## 降级策略

所有三处修改都采用了**优雅降级**策略：

```python
cocktail_name = ai_returned_name or database_name
```

- 如果前端传递了AI返回的名称 → 使用AI名称 ✨
- 如果前端没有传递 → 降级到数据库中的标准名称 ✅
- 保证向后兼容，不影响现有功能

## 使用场景

### 经典模式 (classic)

AI **不会改名**，严格使用数据库中的标准名称：

```json
{
  "cocktail_id": 123,
  "cocktail_name": "Mojito",     // 与数据库一致，不改名
  "cocktail_name_zh": "莫吉托"
}
```

前端可以不传 `cocktail_name`，后端会自动使用数据库名称。

### 原创特调模式 (original)

AI **会改名**，起一个有梗、能截图分享的新名字：

```json
{
  "selected_id": 123,                    // 原型配方ID
  "cocktail_name": "Electric Painkiller", // AI创意命名
  "cocktail_name_zh": "电子布洛芬",       // 有梗的中文名
  "prototype_name": "Mojito",            // 原型配方名（保留）
  "prototype_name_zh": "莫吉托"
}
```

前端**必须**传递 `cocktail_name`，保存AI的创意命名。

## 前端调用示例

### 经典模式

```javascript
// 可以不传 cocktail_name，后端会使用数据库名称
await fetch('/api/card/generate', {
  method: 'POST',
  body: JSON.stringify({
    cocktail_id: 123,
    // cocktail_name 不传，后端自动使用 "Mojito"
    ai_poetic: "清新如夏日微风...",
    mood_caption: "今天想喝点清爽的"
  })
});
```

### 原创特调模式

```javascript
// 推荐接口返回的数据
const recommendation = {
  selected_id: 123,
  cocktail_name: "Electric Painkiller",
  cocktail_name_zh: "电子布洛芬",
  prototype_name: "Mojito",
  ai_poetic: "解决不了领导，先解决这杯",
  ...
};

// 创建卡片时传递AI改名后的名称
await fetch('/api/card/generate', {
  method: 'POST',
  body: JSON.stringify({
    cocktail_id: recommendation.selected_id,
    cocktail_name: recommendation.cocktail_name_zh,  // 传递AI改名
    cocktail_name_zh: recommendation.cocktail_name_zh,
    ai_poetic: recommendation.ai_poetic,
    mood_caption: "..."
  })
});
```

### 提交卡片（Canvas渲染）

```javascript
const formData = new FormData();
formData.append('image', imageFile);
formData.append('cocktail_id', recommendation.selected_id);
formData.append('cocktail_name', recommendation.cocktail_name_zh); // 传递AI改名
formData.append('ai_poetic', recommendation.ai_poetic);

await fetch('/api/card/submit', {
  method: 'POST',
  body: formData
});
```

## 数据库存储

存储的 `cocktail_name` 字段内容：

| 模式 | 存储的名称 | 示例 |
|------|-----------|------|
| 经典模式 (classic) | 数据库标准名称 | "Mojito" |
| 原创特调 (original) | AI 创意命名 | "电子布洛芬" |

## 显示优先级

当前端展示卡片名称时，推荐的优先级：

```javascript
// 优先级：卡片快照名称 > 关联鸡尾酒名称 > 默认值
const displayName = 
  card.cocktail_name ||           // 1. 卡片创建时保存的名称（AI改名或原始名）
  card.cocktail?.name ||          // 2. 关联鸡尾酒的当前名称
  '未知鸡尾酒';                   // 3. 默认值
```

## 修改的文件

1. ✅ `/app/api/card.py`
   - `POST /api/card/generate` - 优先使用AI返回的名称
   - `POST /api/card/submit` - 优先使用AI返回的名称

2. ✅ `/app/services/map_service.py`
   - `complete_node_with_card()` - 优先使用AI返回的名称

## 向后兼容性

✅ **完全向后兼容**

- 前端如果不传 `cocktail_name`，后端自动使用数据库名称
- 经典模式不需要改动，继续使用数据库名称
- 原创特调模式可以充分利用AI的创意命名

## 测试建议

### 测试场景1：经典模式（不传名称）

```bash
curl -X POST "http://localhost:5005/api/card/generate" \
  -H "Authorization: Bearer YOUR_TOKEN" \
  -H "Content-Type: application/json" \
  -d '{
    "cocktail_id": 1,
    "mood_caption": "今天想喝点清爽的"
  }'

# 验证：卡片的 cocktail_name 应该是数据库中的标准名称（如 "Mojito"）
```

### 测试场景2：原创特调模式（传递AI改名）

```bash
curl -X POST "http://localhost:5005/api/card/generate" \
  -H "Authorization: Bearer YOUR_TOKEN" \
  -H "Content-Type: application/json" \
  -d '{
    "cocktail_id": 1,
    "cocktail_name": "电子布洛芬",
    "ai_poetic": "解决不了领导，先解决这杯",
    "mood_caption": "被领导骂了"
  }'

# 验证：卡片的 cocktail_name 应该是 "电子布洛芬"
```

### 测试场景3：提交卡片（Canvas渲染）

```bash
curl -X POST "http://localhost:5005/api/card/submit" \
  -H "Authorization: Bearer YOUR_TOKEN" \
  -F "image=@card.png" \
  -F "cocktail_id=1" \
  -F "cocktail_name=电子布洛芬" \
  -F "ai_poetic=解决不了领导，先解决这杯"

# 验证：返回的 cocktail_name 应该是 "电子布洛芬"
```

## 好处

1. **更好的用户体验**
   - 原创特调模式的卡片显示更有个性的名字
   - 名字更符合用户当时的情绪和场景

2. **数据完整性**
   - 卡片保存创建时的名称快照
   - 即使后续数据库配方被修改，卡片仍保留原始名称

3. **灵活性**
   - 经典模式和原创模式都能正常工作
   - 前端可以选择是否传递AI名称

4. **向后兼容**
   - 不传名称时自动降级到数据库名称
   - 不影响现有功能

---

**变更日期**: 2026-08-30  
**状态**: ✅ 完成  
**向后兼容**: ✅ 是
