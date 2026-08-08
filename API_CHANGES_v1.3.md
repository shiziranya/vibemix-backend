# API 改动说明 v1.3 — 星图模块重构

> 生效版本：v1.3  
> 影响模块：星图模块 `/api/v1/map`  
> 其他模块（认证、酒柜、推荐、卡片）接口协议**不变**

---

## 核心变化

1. **节点不再存储冗余字段**：`map_nodes` 表移除了 `display_name_zh`、`complexity`、`base_spirits`，改从关联的 `cocktails` 表获取对应数据（`name_zh`、`complexity_score`、`gateway_spirit`）。
2. **边类型扩展**：`map_edges` 新增三种类型 `prerequisite`、`archetype_bridge`、`variant`，其中 `prerequisite` 承担原 `progression` 的解锁前置语义，两者在状态计算时等价。
3. **"缺少基酒"接口数据源变更**：从节点自有的 `base_spirits`（`ingredient_family.slug` 数组）改为鸡尾酒的 `base_spirit_ids`（`ingredient_family.id` 数组），响应字段随之调整。

---

## 1. `GET /api/v1/map/themes/:theme_id` — 主题图谱

### 认证
`Authorization: Bearer <token>` 必填

### node 对象字段变更

| 字段 | 旧版 | 新版 | 说明 |
|------|------|------|------|
| `display_name_zh` | 节点自有字段 | 来自 `cocktails.name_zh` | 字段名不变，数据源改变 |
| `complexity` | 节点自有字段（整数 1-5） | 来自 `cocktails.complexity_score` | 字段名不变，数据源改变 |
| `base_spirits` | `string[]` 基酒 slug 数组 | ❌ **已移除** | — |
| `has_all_spirits` | `boolean` | ❌ **已移除** | 解锁条件不再基于基酒 |
| `owned_spirit_count` | `int` | ❌ **已移除** | — |
| `missing_spirit_count` | `int` | ❌ **已移除** | — |
| `gateway_spirit` | ❌ 不存在 | ✅ **新增** `string \| null` | 该鸡尾酒的代表基酒类别，如 `"rum"`、`"gin"` |
| `image_url` | ❌ 不存在 | ✅ **新增** `string \| null` | 鸡尾酒图片 URL |

```json
// ✅ 新 node 结构示例
{
  "id": 323,
  "node_key": "t_0",
  "display_name_zh": "自由古巴",
  "cocktail_id": 277,
  "is_entry_node": true,
  "is_boss": false,
  "complexity": 2,
  "gateway_spirit": "rum",
  "image_url": "https://cdn.example.com/mojito.jpg",
  "reward_xp": 10,
  "sort_order": 1,
  "pos_x": 370.0,
  "pos_y": 80.0,
  "status": "available"
}
```

`status` 取值不变：`"locked"` / `"available"` / `"completed"`

### 边（edges）结构变更

旧版只有两组边，新版分为四组：

| 字段 | 旧版 | 新版 | 说明 |
|------|------|------|------|
| `progression_edges` | `{from, to}[]` | `{from, to}[]` | 现包含 `prerequisite` 和 `progression` 两种类型，语义不变：需完成前置节点才可解锁 |
| `association_edges` | `{from, to, label}[]` | `{from, to, label}[]` | 不变 |
| `variant_edges` | ❌ 不存在 | ✅ **新增** `{from, to}[]` | 节点间变体关系 |
| `archetype_bridge_edges` | ❌ 不存在 | ✅ **新增** `{from, to, label}[]` | 跨原型桥接关系 |

```json
// ✅ 新响应结构示例
{
  "code": 0,
  "data": {
    "theme": { "id": 13, "slug": "classic", "name_zh": "经典基石", "color_primary": "#C9A84C", "color_secondary": null, "portal_cocktail_id": null },
    "nodes": [ /* node 对象数组 */ ],
    "progression_edges": [{ "from": 465, "to": 466 }],
    "association_edges": [{ "from": 465, "to": 470, "label": null }],
    "variant_edges": [],
    "archetype_bridge_edges": []
  },
  "message": "ok"
}
```

---

## 2. `GET /api/v1/map/themes/:theme_id/layout` — 主题布局（无需认证）

> 供星图编辑器在无登录状态下加载布局数据。

### node 对象字段变更（同接口 1）

| 字段 | 旧版 | 新版 |
|------|------|------|
| `display_name_zh` | 节点自有 | 来自 `cocktails.name_zh` |
| `complexity` | 节点自有 | 来自 `cocktails.complexity_score` |
| `base_spirits` | `string[]` | ❌ **已移除** |
| `reward_xp` | ❌ 不存在 | ✅ **新增** `int` |
| `gateway_spirit` | ❌ 不存在 | ✅ **新增** `string \| null` |
| `image_url` | ❌ 不存在 | ✅ **新增** `string \| null` |

### 边（edges）结构

Layout 接口返回所有边的扁平数组（不分组），每条边带 `type` 字段，取值现在包含全部 5 种：

```
"prerequisite" | "progression" | "association" | "archetype_bridge" | "variant"
```

```json
// ✅ 边结构示例
{
  "edges": [
    { "from": 323, "to": 324, "type": "prerequisite", "label": null },
    { "from": 323, "to": 330, "type": "association",  "label": "风味相近" }
  ]
}
```

---

## 3. `GET /api/v1/map/nodes/:node_id/missing-spirits` — 缺少的基酒

### 认证
`Authorization: Bearer <token>` 必填

### Response — item 字段变更

数据源从节点的 `base_spirits`（slug 数组）改为鸡尾酒的 `base_spirit_ids`（ingredient_family ID 数组）。

| 字段 | 旧版 | 新版 | 说明 |
|------|------|------|------|
| `id` | ✅ | ✅ | `ingredient_family.id` |
| `slug` | ✅ 存在 | ❌ **已移除** | `ingredient_family` 表无此字段 |
| `name` | ❌ 不存在 | ✅ **新增** `string` | 品类英文名 |
| `name_zh` | ✅ | ✅ | 不变 |
| `name_en` | ✅ 存在 | ❌ **已移除** | 同 `name`，已合并 |
| `category` | ✅ | ✅ | 不变 |
| `abv_min` | ✅ 存在 | ❌ **已移除** | — |
| `abv_max` | ✅ 存在 | ❌ **已移除** | — |
| `base_spirit_family` | ❌ 不存在 | ✅ **新增** `string \| null` | 大类，如 `"rum"`、`"gin"` |

```json
// ✅ 新 item 结构示例
{
  "code": 0,
  "data": {
    "items": [
      {
        "id": 15,
        "name": "朗姆酒",
        "name_zh": "朗姆酒",
        "category": "base_spirit",
        "base_spirit_family": "rum"
      }
    ],
    "count": 1
  },
  "message": "ok"
}
```

---

## 4. 未变更接口

| 接口 | 说明 |
|------|------|
| `GET /api/v1/map/themes` | 主题列表（含进度），字段不变 |
| `GET /api/v1/map/themes/list` | 公开主题列表，字段不变 |
| `POST /api/v1/map/nodes/:node_id/complete` | 完成节点，字段不变 |
| `PATCH /api/v1/map/nodes/positions` | 批量更新位置，字段不变 |
| `GET /api/v1/map/stats` | 用户统计，字段不变 |

---

## 改动汇总

| 接口 | 改动类型 | 必须更新 |
|------|---------|---------|
| `GET /api/v1/map/themes/:id` | node 字段增删、边响应新增两组 | ✅ 必须 |
| `GET /api/v1/map/themes/:id/layout` | node 字段增删、边新增类型 | ✅ 必须 |
| `GET /api/v1/map/nodes/:id/missing-spirits` | item 字段增删 | ✅ 必须 |
