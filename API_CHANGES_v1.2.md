# API 改动说明 v1.2 — 酒柜品类化重构

> 生效版本：v1.2
> 影响模块：酒柜模块 `/api/cabinet`、配方详情 `/api/cocktails/:id`
> 其他模块（认证、推荐、卡片）接口协议**不变**

---

## 核心变化

酒柜不再管理**具体品牌原料**（如"Banks 5 朗姆酒"），改为管理**原料品类**（如"朗姆酒"）。
所有涉及原料 ID 的参数从 `ingredient_id` 统一改为 `family_id`，对应数据源从 `ingredients` 表变为 `ingredient_family` 表。

---

## 1. `POST /api/cabinet/items` — 加入酒柜

### Request Body

```json
// ❌ 旧
{ "ingredient_id": 42 }

// ✅ 新
{ "family_id": 5 }
```

| 字段 | 类型 | 必填 | 说明 |
|------|------|------|------|
| `family_id` | int | ✅ | `ingredient_family` 表的品类 ID |

### Response `201`（结构不变）

```json
{
  "code": 0,
  "data": {
    "total_spirits": 6,
    "unlocked_recipes": 103,
    "newly_unlocked": 16
  },
  "message": "ok"
}
```

### 错误码变更

| code | message | 变化 |
|------|---------|------|
| ~~4201~~ | ~~原料不存在~~ | 废弃 |
| ~~4202~~ | ~~该原料已在酒柜中~~ | 废弃 |
| **4207** | 原料品类不存在 | 新增 |
| **4208** | 该原料品类已在酒柜中 | 新增 |

---

## 2. `DELETE /api/cabinet/items/:id` — 移除酒柜

### 路径参数

```
// ❌ 旧
DELETE /api/cabinet/items/42    （ingredient_id）

// ✅ 新
DELETE /api/cabinet/items/5     （family_id）
```

传入的 ID 含义从**原料 ID** 变为**品类 ID**。

### Response `200`

返回值包含统计信息 + 删除导致的配方减少数：

```json
{
  "code": 0,
  "data": {
    "total": 5,
    "base_spirit_count": 3,
    "modifier_count": 2,
    "unlocked_recipe_count": 42,
    "recipes_lost": 8  // 新增：删除该品类导致减少的配方数
  },
  "message": "ok"
}
```

| 字段 | 类型 | 说明 |
|------|------|------|
| `total` | int | 酒柜中总品类数 |
| `base_spirit_count` | int | 基酒数量 |
| `modifier_count` | int | 辅料数量 |
| `unlocked_recipe_count` | int | 当前可调配方总数 |
| `recipes_lost` | int | 删除该品类导致减少的配方数（**新增**） |

---

## 3. `GET /api/cabinet/preview` — 预览加入后解锁数

### Query 参数

```
// ❌ 旧
GET /api/cabinet/preview?ingredient_id=42

// ✅ 新
GET /api/cabinet/preview?family_id=5
```

| 参数 | 类型 | 必填 | 说明 |
|------|------|------|------|
| `family_id` | int | ✅ | 品类 ID |

### Response `200`（结构不变）

```json
{
  "code": 0,
  "data": {
    "new_unlock_count": 16
  },
  "message": "ok"
}
```

---

## 4. `GET /api/cabinet/ingredients` — 搜索/浏览原料列表

### Query 参数（不变）

| 参数 | 类型 | 必填 | 说明 |
|------|------|------|------|
| `q` | string | ❌ | 关键词（中英文均可） |
| `category` | string | ❌ | 原料分类 |
| `family` | string | ❌ | 基酒大类，如 `rum`、`gin`、`whiskey` |
| `page` | int | ❌ | 页码，默认 `1` |
| `per_page` | int | ❌ | 每页数量，默认 `20`，最大 `100` |

### Response — item 结构变更

现在返回的是 `ingredient_family`（品类）记录，`subcategory` 和 `image_url` 字段已移除，新增 `description`。

| 字段 | 旧版 | 新版 | 说明 |
|------|------|------|------|
| `id` | 原料 ID | **品类 ID** | 含义变化，用于后续 `family_id` 参数 |
| `name` | ✅ | ✅ | 不变 |
| `name_zh` | ✅ | ✅ | 不变 |
| `category` | ✅ | ✅ | 不变 |
| `subcategory` | ✅ 存在 | ❌ **已移除** | — |
| `is_base_spirit` | ✅ | ✅ | 不变 |
| `is_easily_available` | ✅ | ✅ | 不变 |
| `base_spirit_family` | ✅ | ✅ | 不变 |
| `abv_approx` | ✅ | ✅ | 不变 |
| `image_url` | ✅ 存在 | ❌ **已移除** | — |
| `description` | ❌ 不存在 | ✅ **新增** | 品类描述文案 |
| `in_cabinet` | ✅ | ✅ | 不变 |

```json
// ✅ 新 item 结构示例
{
  "id": 5,
  "name": "Rum",
  "name_zh": "朗姆酒",
  "category": "base_spirit",
  "is_base_spirit": true,
  "is_easily_available": false,
  "base_spirit_family": "rum",
  "abv_approx": 40.0,
  "description": "由甘蔗汁或糖蜜发酵蒸馏而成的烈酒",
  "in_cabinet": false
}
```

---

## 5. `GET /api/cabinet` — 获取我的酒柜

### 路径和参数（不变）

### Response — item 结构变更

同 `GET /api/cabinet/ingredients`，每条记录同样从原料变为品类，字段变化一致（见上表）。

```json
{
  "code": 0,
  "data": {
    "items": [
      {
        "id": 5,
        "name": "Rum",
        "name_zh": "朗姆酒",
        "category": "base_spirit",
        "is_base_spirit": true,
        "is_easily_available": false,
        "base_spirit_family": "rum",
        "abv_approx": 40.0,
        "description": "由甘蔗汁或糖蜜发酵蒸馏而成的烈酒",
        "in_cabinet": true
      }
    ],
    "total": 3
  },
  "message": "ok"
}
```

---

## 6. `GET /api/cocktails/:id` — 配方详情（原料状态）

### 路径和参数（不变）

### Response — ingredients 数组中每条记录新增字段

新增 `ingredient_family_id` 字段，前端可用于判断该原料属于哪个品类。`status` 的判断逻辑现在基于品类（用户酒柜中有同一品类即为 `owned`），前端使用方式不变。

```json
// ✅ 新 ingredient 结构示例
{
  "ingredient_id": 128,
  "ingredient_family_id": 5,
  "name": "Banks 5 Island Rum",
  "name_zh": "Banks 5 朗姆酒",
  "measure_raw": "45ml",
  "measure_ml": 45.0,
  "is_easily_available": false,
  "category": "base_spirit",
  "status": "owned",
  "substitute": null
}
```

| 字段 | 变化 | 说明 |
|------|------|------|
| `ingredient_family_id` | ✅ **新增** | 该原料所属品类的 ID，可能为 `null` |
| 其余字段 | 不变 | — |

---

## 改动汇总

| 接口 | 改动类型 | 必须更新 |
|------|---------|---------|
| `POST /api/cabinet/items` | 请求体字段 `ingredient_id` → `family_id` | ✅ 必须 |
| `DELETE /api/cabinet/items/:id` | 路径参数含义变为品类 ID | ✅ 必须 |
| `GET /api/cabinet/preview` | 查询参数 `ingredient_id` → `family_id` | ✅ 必须 |
| `GET /api/cabinet/ingredients` | item 数据结构变化（字段增删） | ✅ 必须 |
| `GET /api/cabinet` | item 数据结构变化（字段增删） | ✅ 必须 |
| `GET /api/cocktails/:id` | ingredient 新增 `ingredient_family_id` 字段 | ⚠️ 兼容（不影响现有逻辑） |
| 错误码 4201、4202 | 废弃，替换为 4207、4208 | ✅ 建议更新错误提示 |
