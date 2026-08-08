# VibeMix — 星图探索功能 API 文档

> 版本：v1.3  
> 更新时间：2026-07-12  
> Base URL：`http://115.191.50.177:5005`（本地开发替换为 `http://localhost:5000`）

---

## 版本迭代记录

### v1.6 — 2026-07-19

- **用量规范化功能**：
  - 原料列表新增 `measure` 字段（规范化后的中文用量，如"45ml"、"2滴"、"适量"）
  - 原料列表新增 `measure_value` 字段（数值部分，用于计算和排序）
  - 原料列表新增 `measure_unit` 字段（单位部分，ml/滴/barspoon等）
  - 原料列表新增 `measure_type` 字段（类型标记：precise/approximate/descriptive/unclear）
  - 英制单位自动换算为毫升（oz 使用 1:30 简化换算）
  - 保留调酒专业术语（dash → "滴"、barspoon）
  - 原有字段（`measure_raw`, `measure_ml`）完全保留，向后兼容
  - 详细说明请查看 `API_用量规范化更新.md`

### v1.5 — 2026-07-19

- **主线/支线功能**：
  - 节点新增 `path_role` 字段（`'main'` | `'side'`），区分主线节点和支线节点
  - 节点新增 `unlock_by` 字段（`int | null`），支线节点可通过购买指定鸡尾酒解锁
  - 边新增 `path_role` 字段（`'main'` | `'side'`），区分主线关系和支线关系
  - 边新增 `status` 字段（`'locked'` | `'unlocked'`），根据 from 节点的解锁状态计算边的可见性
  - 节点解锁逻辑更新：主线节点需完成前置节点，支线节点可通过完成 `unlock_by` 指定的鸡尾酒解锁

### v1.4 — 2026-07-19

- **用户统计新增 `is_unlocked` 字段**：`GET /api/v1/map/stats` 每个主题条目新增 `is_unlocked`（bool）。判断规则：入口节点无前置边则始终为 `true`（如经典基石）；子主题需其入口节点的所有跨主题前置鸡尾酒均已完成后才为 `true`。移除原 `unlocked`（节点维度计数）字段

### v1.3 — 2026-07-12

- **节点详情新增 `missing_ingredients`**：`GET /api/v1/map/nodes/:node_id` 返回数据中新增 `missing_ingredients` 数组，包含该鸡尾酒中 `is_easily_available=false` 且用户酒柜没有的材料，用于前端引导用户购买
- **节点新增 `unlocks_theme` 字段**：`GET /api/v1/map/themes/:theme_id` 的节点中新增 `unlocks_theme` 对象（或 `null`）。若该节点完成后可解锁某个子主题（即存在跨主题前置出边），则返回目标主题的 `id`、`name_zh`、`slug`、`color_primary`；前端可借此展示"完成此节点将解锁 XX 主题"的引导
- **节点完成状态跨主题共享**：同一鸡尾酒在不同主题中的节点，完成状态完全共享。在任意主题中完成该鸡尾酒节点，其他主题中相同鸡尾酒的节点将自动显示为 `completed`，且可作为后续节点的前置条件

### v1.2 — 2026-07-12

- **节点字段精简**：`map_nodes` 表移除 `display_name_zh`、`complexity`、`base_spirits`，改从关联 `cocktails` 表读取，节点响应新增 `gateway_spirit`、`image_url`
- **节点状态简化**：移除 `unlocked` 状态，现只有三种状态：`locked` / `available` / `completed`，解锁条件不再依赖基酒检查
- **解锁逻辑修正**：修复入口节点数据（每个主题只有一个真实入口节点），修复跨主题前置边计算（子主题首节点通过主题 13 的门户节点解锁）
- **边类型扩展**：新增 `prerequisite`、`archetype_bridge`、`variant` 三种类型；图谱接口响应新增 `variant_edges`、`archetype_bridge_edges` 两组；`prerequisite` 与 `progression` 共同决定前置解锁条件
- **新增节点详情接口** `GET /api/v1/map/nodes/:node_id`：返回鸡尾酒故事、食材（含酒柜匹配状态）、制作步骤；包含 `required_spirits` 和 `can_complete` 字段
- **完成节点前置校验**：`POST /api/v1/map/nodes/:node_id/complete` 现在要求用户酒柜中必须有鸡尾酒所需的基酒，否则返回 4403
- **缺失基酒接口**：数据源改为 `cocktail_ingredients` 表（`is_base_spirit=true` 的品类），响应字段调整（移除 `slug`/`name_en`/`abv_min`/`abv_max`，新增 `name`/`base_spirit_family`）
- **统计接口路径**：新增 `/user/stats` 别名，`/stats` 和 `/user/stats` 均可访问

### v1.1 — 2026-07-05

初始版本。

---

## 目录

- [1. 功能概述](#1-功能概述)
- [2. 接口概览](#2-接口概览)
- [3. 节点状态说明](#3-节点状态说明)
- [4. 主题列表（需登录）](#4-主题列表需登录)
- [5. 主题星图（需登录）](#5-主题星图需登录)
- [6. 节点详情（需登录）](#6-节点详情需登录)
- [7. 完成节点](#7-完成节点)
- [8. 缺失基酒](#8-缺失基酒)
- [9. 用户统计](#9-用户统计)
- [10. 公开接口（无需登录）](#10-公开接口无需登录)
- [11. 编辑器接口](#11-编辑器接口)
- [12. 数据模型](#12-数据模型)
- [13. 错误码](#13-错误码)
- [14. 前端调用流程](#14-前端调用流程)

---

## 1. 功能概述

星图探索是 VibeMix 的核心留存功能，类似多邻国关卡地图：

- **多个主题**：每个主题对应一组鸡尾酒节点（如经典基石、热带风情等）
- **节点**：每个节点对应一款鸡尾酒，含复杂度（1-5）和 Boss 标记
- **解锁逻辑**：入口节点（`is_entry_node: true`）直接可用；非入口节点需要所有 `prerequisite` / `progression` 类型的前置节点全部完成后才能访问
- **四种边关系**：`prerequisite`（前置解锁）/ `association`（风味关联）/ `variant`（配方变体）/ `archetype_bridge`（原型桥接）

```
locked → available（前置全部完成）→ completed（用户完成节点）
```

**认证方式**：大部分接口需 JWT Token，无需认证的接口会单独标注。

```
Authorization: Bearer <access_token>
```

**统一响应格式**：

```json
// 成功
{ "code": 0, "data": { ... }, "message": "ok" }

// 失败
{ "code": 4401, "data": null, "message": "主题不存在" }
```

---

## 2. 接口概览

| 方法 | 路径 | 认证 | 说明 |
|------|------|------|------|
| `GET` | `/api/v1/map/themes` | ✅ JWT | 主题列表 + 用户进度摘要 |
| `GET` | `/api/v1/map/themes/:theme_id` | ✅ JWT | 完整星图（节点 + 四类边 + 状态） |
| `GET` | `/api/v1/map/nodes/:node_id` | ✅ JWT | 节点详情（鸡尾酒故事/食材/步骤 + 基酒状态） |
| `POST` | `/api/v1/map/nodes/:node_id/complete` | ✅ JWT | 标记节点完成（需拥有所需基酒） |
| `GET` | `/api/v1/map/nodes/:node_id/missing-spirits` | ✅ JWT | 节点关联鸡尾酒缺失的基酒 |
| `GET` | `/api/v1/map/stats` | ✅ JWT | 用户全局地图统计 |
| `GET` | `/api/v1/map/user/stats` | ✅ JWT | 同上（别名） |
| `GET` | `/api/v1/map/themes/list` | ❌ 无需 | 主题基本列表（供编辑器） |
| `GET` | `/api/v1/map/themes/:theme_id/layout` | ❌ 无需 | 主题节点 + 边布局（供编辑器） |
| `PATCH` | `/api/v1/map/nodes/positions` | ✅ JWT | 批量更新节点坐标（编辑器专用） |

---

## 3. 节点状态说明

| 状态 | 含义 | 触发条件 | UI 建议 |
|------|------|----------|---------|
| `locked` | 已锁定 | 存在未完成的前置节点 | 灰色节点，不可交互 |
| `available` | 可完成 | 入口节点，或所有前置节点均已完成 | 高亮显示，可点击查看配方 |
| `completed` | 已完成 | 用户已调用完成接口 | 打勾 + 特效，会解锁后继节点 |

> **入口节点**（`is_entry_node: true`）：无前置依赖，主题开放时直接为 `available`。  
> **Boss 节点**（`is_boss: true`）：主题终极节点，通常奖励经验更高。

---

## 4. 主题列表（需登录）

### `GET /api/v1/map/themes`

获取所有活跃主题及当前用户的完成进度，用于首页主题选择。

**请求示例**

```bash
GET /api/v1/map/themes
Authorization: Bearer eyJhbGci...
```

**成功响应** `200`

```json
{
  "code": 0,
  "data": {
    "themes": [
      {
        "id": 13,
        "slug": "classic",
        "name_zh": "经典基石",
        "sort_order": 0,
        "color_primary": "#C9A84C",
        "icon_url": null,
        "portal_cocktail_id": null,
        "node_total": 25,
        "node_completed": 3
      },
      {
        "id": 14,
        "slug": "tropical",
        "name_zh": "热带风情",
        "sort_order": 1,
        "color_primary": "#2A9D8F",
        "icon_url": null,
        "portal_cocktail_id": 78,
        "node_total": 27,
        "node_completed": 0
      }
    ],
    "total": 2
  },
  "message": "ok"
}
```

**字段说明**

| 字段 | 类型 | 说明 |
|------|------|------|
| `id` | int | 主题 ID |
| `slug` | string | 主题标识 |
| `name_zh` | string | 中文名 |
| `sort_order` | int | 排列顺序 |
| `color_primary` | string \| null | 主题主色（十六进制） |
| `icon_url` | string \| null | 主题图标 URL |
| `portal_cocktail_id` | int \| null | 星门配方 ID（经典基石为 null，其余主题有值） |
| `node_total` | int | 主题节点总数 |
| `node_completed` | int | 用户已完成节点数 |

---

## 5. 主题星图（需登录）

### `GET /api/v1/map/themes/:theme_id`

获取指定主题的完整星图：所有节点（含用户状态）+ 四类边。前端以此数据渲染整张星图。

**Path 参数**

| 参数 | 类型 | 说明 |
|------|------|------|
| `theme_id` | int | 主题 ID |

**请求示例**

```bash
GET /api/v1/map/themes/13
Authorization: Bearer eyJhbGci...
```

**成功响应** `200`

```json
{
  "code": 0,
  "data": {
    "theme": {
      "id": 13,
      "slug": "classic",
      "name_zh": "经典基石",
      "color_primary": "#C9A84C",
      "color_secondary": null,
      "portal_cocktail_id": null
    },
    "nodes": [
      {
        "id": 465,
        "node_key": "c_0",
        "display_name_zh": "自由古巴",
        "cocktail_id": 277,
        "is_entry_node": true,
        "is_boss": false,
        "complexity": 2,
        "gateway_spirit": "rum",
        "image_url": "https://cdn.example.com/cocktails/cuba-libre.jpg",
        "reward_xp": 10,
        "sort_order": 1,
        "pos_x": 370.0,
        "pos_y": 80.0,
        "status": "available",
        "path_role": "main",
        "unlock_by": null
      },
      {
        "id": 466,
        "node_key": "c_1",
        "display_name_zh": "莫吉托",
        "cocktail_id": 127,
        "is_entry_node": false,
        "is_boss": false,
        "complexity": 2,
        "gateway_spirit": "rum",
        "image_url": "https://cdn.example.com/cocktails/mojito.jpg",
        "reward_xp": 10,
        "sort_order": 2,
        "pos_x": 370.0,
        "pos_y": 230.0,
        "status": "locked",
        "path_role": "main",
        "unlock_by": null
      },
      {
        "id": 467,
        "node_key": "c_2",
        "display_name_zh": "代基里",
        "cocktail_id": 128,
        "is_entry_node": false,
        "is_boss": false,
        "complexity": 2,
        "gateway_spirit": "rum",
        "image_url": "https://cdn.example.com/cocktails/daiquiri.jpg",
        "reward_xp": 15,
        "sort_order": 3,
        "pos_x": 550.0,
        "pos_y": 150.0,
        "status": "locked",
        "path_role": "side",
        "unlock_by": 127
      }
    ],
    "progression_edges": [
      { "from": 465, "to": 466, "path_role": "main", "status": "unlocked" }
    ],
    "association_edges": [
      { "from": 465, "to": 470, "label": "风味相近", "path_role": "main", "status": "unlocked" }
    ],
    "variant_edges": [
      { "from": 466, "to": 467, "path_role": "side", "status": "locked" }
    ],
    "archetype_bridge_edges": [
      { "from": 465, "to": 501, "label": null, "path_role": "main", "status": "unlocked" }
    ]
  },
  "message": "ok"
}
```

**`theme` 字段说明**

| 字段 | 类型 | 说明 |
|------|------|------|
| `id` | int | 主题 ID |
| `slug` | string | 主题标识 |
| `name_zh` | string | 中文名 |
| `color_primary` | string \| null | 主色 |
| `color_secondary` | string \| null | 辅色 |
| `portal_cocktail_id` | int \| null | 星门配方 ID |

**`nodes` 元素字段说明**

| 字段 | 类型 | 说明 |
|------|------|------|
| `id` | int | 节点 ID |
| `node_key` | string \| null | 主题内唯一标识 |
| `display_name_zh` | string \| null | 鸡尾酒中文名（来自 `cocktails.name_zh`） |
| `cocktail_id` | int | 关联的鸡尾酒 ID |
| `is_entry_node` | bool | 是否为入口节点（无前置依赖） |
| `is_boss` | bool | 是否为 Boss 节点 |
| `complexity` | int \| null | 复杂度 1-5（来自 `cocktails.complexity_score`） |
| `gateway_spirit` | string \| null | 代表基酒大类，如 `"rum"`、`"gin"`（来自 `cocktails.gateway_spirit`） |
| `image_url` | string \| null | 鸡尾酒图片 URL |
| `reward_xp` | int | 完成本节点奖励经验值 |
| `sort_order` | int | 主题内排序 |
| `pos_x` | float \| null | 节点 X 坐标（由编辑器写入） |
| `pos_y` | float \| null | 节点 Y 坐标（由编辑器写入） |
| `status` | string | 节点状态：`locked` / `available` / `completed`，同一鸡尾酒在所有主题中共享该状态 |
| `unlocks_theme` | object \| null | 完成该节点后可解锁的子主题；`null` 表示无解锁效果（见下表） |

**`unlocks_theme` 对象结构**

| 字段 | 类型 | 说明 |
|------|------|------|
| `id` | int | 目标主题 ID |
| `name_zh` | string | 目标主题中文名，如 `"航海时代"` |
| `slug` | string | 目标主题标识，如 `"age_of_sail"` |
| `color_primary` | string \| null | 目标主题主色（十六进制或 CSS 变量） |

> **典型场景**：经典基石（主题 13）中的「得其利」完成后 `unlocks_theme` 为 `{ id: 15, name_zh: "航海时代", ... }`，前端可在节点卡片上展示"解锁 🌊 航海时代"的引导文案吸引用户继续探索。

**边字段说明**

| 字段 | 用途 | 结构 |
|------|------|------|
| `progression_edges` | 前置解锁关系（含 `prerequisite` 和 `progression` 类型），决定解锁顺序 | `[{ "from": int, "to": int }]` |
| `association_edges` | 风味/同源星座关联，仅供可视化展示 | `[{ "from": int, "to": int, "label": string\|null }]` |
| `variant_edges` | 配方变体关系，仅供可视化展示 | `[{ "from": int, "to": int }]` |
| `archetype_bridge_edges` | 跨原型桥接关系，仅供可视化展示 | `[{ "from": int, "to": int, "label": string\|null }]` |

> 只有 `progression_edges` 中的关系会影响节点状态计算，其余三类仅用于连线展示。

**错误**

| code | message | HTTP |
|------|---------|------|
| 4401 | 主题不存在 | 404 |

---

## 6. 节点详情（需登录）

### `GET /api/v1/map/nodes/:node_id`

获取节点的完整鸡尾酒信息：故事背景、食材清单（含酒柜拥有状态）、制作步骤，以及是否满足完成条件。  
用于点击节点后弹出的详情页。

**Path 参数**

| 参数 | 类型 | 说明 |
|------|------|------|
| `node_id` | int | 节点 ID |

**成功响应** `200`

```json
{
  "code": 0,
  "data": {
    "node": {
      "id": 465,
      "theme_id": 13,
      "cocktail_id": 277,
      "node_key": "c_1",
      "is_entry_node": true,
      "is_boss": false,
      "reward_xp": 10
    },
    "cocktail": {
      "id": 277,
      "name": "Cuba Libre",
      "name_zh": "自由古巴",
      "story_zh": "诞生于 20 世纪初的古巴，朗姆酒与可乐的经典碰撞象征着自由与独立...",
      "instructions_zh": "在装满冰块的高球杯中倒入朗姆酒，挤入半个青柠汁，缓缓注入可乐，轻搅，以青柠角装饰。",
      "image_url": "https://cdn.example.com/cocktails/cuba-libre.jpg",
      "difficulty": 1,
      "abv_level": "medium",
      "glass_type": "Highball glass",
      "flavor_tags": ["refreshing", "citrus"],
      "prep_time_minutes": 3,
      "complexity": 2,
      "gateway_spirit": "rum"
    },
    "ingredients": [
      {
        "sort_order": 1,
        "name": "Light Rum",
        "name_zh": "淡朗姆酒",
        "measure_raw": "1 1/2 oz",
        "measure_ml": 44.36,
        "family_id": 270,
        "family_name_zh": null,
        "is_base_spirit": true,
        "in_cabinet": false
      },
      {
        "sort_order": 2,
        "name": "Lime",
        "name_zh": "青柠",
        "measure_raw": "1/2",
        "measure_ml": null,
        "family_id": null,
        "family_name_zh": null,
        "is_base_spirit": false,
        "in_cabinet": false
      }
    ],
    "required_spirits": [
      {
        "id": 270,
        "name": "白朗姆酒",
        "name_zh": null,
        "base_spirit_family": "rum",
        "in_cabinet": false
      }
    ],
    "can_complete": false,
    "missing_ingredients": [
      {
        "family_id": 110,
        "name": "Tabasco",
        "name_zh": "塔巴斯科辣椒酱",
        "family_name_zh": "辣酱",
        "category": "other",
        "base_spirit_family": null,
        "is_base_spirit": false,
        "measure_raw": "Tabasco"
      },
      {
        "family_id": 522,
        "name": "To 3 Dashes Of Worcestershire Sauce",
        "name_zh": "伍斯特沙司 2-3 滴",
        "family_name_zh": "伍斯特酱",
        "category": "other",
        "base_spirit_family": null,
        "is_base_spirit": false,
        "measure_raw": "2 to 3 dashes of Worcestershire Sauce"
      }
    ]
  },
  "message": "ok"
}
```

**`node` 字段说明**

| 字段 | 类型 | 说明 |
|------|------|------|
| `id` | int | 节点 ID |
| `theme_id` | int | 所属主题 ID |
| `cocktail_id` | int | 关联鸡尾酒 ID |
| `node_key` | string \| null | 主题内唯一标识 |
| `is_entry_node` | bool | 是否为入口节点 |
| `is_boss` | bool | 是否为 Boss 节点 |
| `reward_xp` | int | 完成奖励经验值 |

**`cocktail` 字段说明**

| 字段 | 类型 | 说明 |
|------|------|------|
| `name` / `name_zh` | string | 英文名 / 中文名 |
| **故事与氛围** | | |
| `story_zh` | string \| null | 鸡尾酒完整背景故事 |
| `story_hook_zh` | string \| null | 一句话钩子文案（适合展示在卡片/标题区） |
| `cultural_icon` | string[] | 文化符号标签，如 `["cuba_libre_culture"]` |
| `occasion_vibe` | string \| null | 适合的场合氛围，如 `"tropical_escape"`、`"house_party"`、`"elegant_night_out"` |
| **制作** | | |
| `instructions_zh` | string \| null | 中文制作步骤（纯文本，传统格式） |
| `preparation_steps` | object[] | 结构化制作步骤（见下表），无数据时为 `[]` |
| `technique_primary` | string \| null | 主要技法：`"shake"`、`"stir"`、`"build"`、`"blend"` 等 |
| `cocktail_archetype` | string \| null | 调酒原型/风格，如 `"摇制"`、`"sour"`、`"highball"` |
| **展示** | | |
| `image_url` | string \| null | 封面图 |
| `video_url` | string \| null | 视频 URL |
| `glass_type` | string \| null | 杯型 |
| **口味 & 难度** | | |
| `difficulty` | int \| null | 难度 1-3 |
| `abv_level` | string \| null | `"low"` / `"medium"` / `"high"` |
| `complexity` | int \| null | 操作复杂度 1-5 |
| `mood_tags` | string[] | 情绪标签，如 `["relaxing", "adventurous"]` |
| `flavor_tags` | string[] | 风味标签，如 `["citrus", "sweet", "refreshing"]` |
| **基酒 & 关联** | | |
| `gateway_spirit` | string \| null | 代表基酒大类，如 `"rum"`、`"gin"` |
| `parent_cocktail_slug` | string \| null | 原型鸡尾酒 slug（变体溯源，如 `"french-75"`） |
| **营养 & 时间** | | |
| `prep_time_minutes` | int \| null | 制作时间（分钟） |
| `calories` | int \| null | 热量（kcal） |
| `carbs_g` | float \| null | 碳水化合物（克） |

**`preparation_steps` 元素结构**

| 字段 | 类型 | 说明 |
|------|------|------|
| `order` | int | 步骤序号，从 1 开始 |
| `text` | string | 步骤说明文字 |
| `duration_hint` | string \| null | 操作时长提示，如 `"15秒"`，无则为 null |

**`ingredients` 元素字段说明**

| 字段 | 类型 | 说明 |
|------|------|------|
| `sort_order` | int | 食材排序 |
| `name` / `name_zh` | string | 原料名称 |
| `measure_raw` | string \| null | 原始用量描述，如 `"1 1/2 oz"` |
| `measure_ml` | float \| null | 换算后毫升数（旧版） |
| 🆕 `measure` | string | **规范化用量**（推荐使用），如 `"45ml"`、`"2滴"`、`"适量"` |
| 🆕 `measure_value` | float \| null | 用量数值部分（用于计算和排序） |
| 🆕 `measure_unit` | string \| null | 用量单位（`"ml"`、`"滴"`、`"barspoon"`、`"适量"` 等） |
| 🆕 `measure_type` | string | 用量类型：`"precise"`（精确）、`"approximate"`（约量）、`"descriptive"`（描述性）、`"unclear"`（需确认） |
| `family_id` | int \| null | `ingredient_family` ID（无归类则为 null） |
| `family_name_zh` | string \| null | 品类中文名 |
| `is_base_spirit` | bool | 是否为基酒 |
| `in_cabinet` | bool | 用户酒柜是否已有（按品类匹配） |

> 💡 **v1.6 新增**：新增 4 个用量规范化字段，推荐前端优先使用 `measure` 字段显示用量。详见 `API_用量规范化更新.md`

**`required_spirits` 与 `can_complete` 说明**

- `required_spirits`：该鸡尾酒食材中 `is_base_spirit = true` 的品类列表，含用户是否持有
- `can_complete`：`true` 表示用户已拥有所有必需基酒，可调用完成节点接口；`false` 则不可完成

**`missing_ingredients` 说明**

`missing_ingredients` 返回用户当前**缺少且不容易在家随时取得**的材料（即 `is_easily_available = false` 且酒柜中没有）。

| 字段 | 类型 | 说明 |
|------|------|------|
| `family_id` | int | `ingredient_family` ID |
| `name` | string | 原料英文名 |
| `name_zh` | string | 原料中文名 |
| `family_name_zh` | string | 品类中文名（如"辣酱"、"伍斯特酱"） |
| `category` | string | 品类大类，如 `"base_spirit"`、`"liqueur"`、`"other"` |
| `base_spirit_family` | string \| null | 基酒家族标识，如 `"rum"`（非基酒则为 null） |
| `is_base_spirit` | bool | 是否为基酒 |
| `measure_raw` | string \| null | 原始用量描述 |

> **前端用途**：在节点详情页底部展示"还需购买"的材料列表，引导用户去购买后再回来完成节点。数组为空表示该鸡尾酒所需的特殊材料用户都已具备（或全部是 `is_easily_available=true` 的常见材料）。

**错误**

| code | message | HTTP |
|------|---------|------|
| 4402 | 节点不存在 | 404 |

---

## 7. 完成节点

### `POST /api/v1/map/nodes/:node_id/complete`

将节点标记为已完成。**前提：用户酒柜中须拥有鸡尾酒所需的全部基酒**（即 `can_complete: true`）。

> **幂等**：对已完成节点重复调用会更新 `completed_at`，不影响其他逻辑。

**Path 参数**

| 参数 | 类型 | 说明 |
|------|------|------|
| `node_id` | int | 节点 ID |

**Request Body**：无（空 body 或 `{}`）

**成功响应** `200`

```json
{
  "code": 0,
  "data": {
    "node_id": 465,
    "reward_xp": 10
  },
  "message": "ok"
}
```

> 完成后建议重新请求 `GET /api/v1/map/themes/:theme_id` 刷新星图，后继节点的 `status` 可能从 `locked` 变为 `available`。

**完成后制作纪念卡片**

完成节点后，前端可引导用户拍照并制作纪念卡片，复用现有卡片接口：

```
1. POST /api/card/upload-photo   上传用户调酒照片 → 获得 photo_url
2. POST /api/card/submit         提交卡片图片（multipart/form-data）
   必填字段：image（PNG/JPEG）、cocktail_id（= 节点的 cocktail_id）
   可选字段：mood_caption、template_id
   → 返回 card_id、image_url
```

**错误**

| code | message | HTTP |
|------|---------|------|
| 4402 | 节点不存在 | 404 |
| 4403 | 缺少必需基酒：{基酒名} | 403 |

```json
// 4403 示例
{
  "code": 4403,
  "data": null,
  "message": "缺少必需基酒：白朗姆酒"
}
```

---

## 8. 缺失基酒

### `GET /api/v1/map/nodes/:node_id/missing-spirits`

获取该节点关联鸡尾酒所需但用户尚未添加的基酒品类，用于购买引导弹窗。

**Path 参数**

| 参数 | 类型 | 说明 |
|------|------|------|
| `node_id` | int | 节点 ID |

**请求示例**

```bash
GET /api/v1/map/nodes/466/missing-spirits
Authorization: Bearer eyJhbGci...
```

**成功响应** `200`

```json
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

> 若用户已拥有所有所需基酒，`items` 为 `[]`，`count` 为 `0`。

**`items` 元素字段说明**

| 字段 | 类型 | 说明 |
|------|------|------|
| `id` | int | `ingredient_family` 品类 ID |
| `name` | string | 品类英文名 |
| `name_zh` | string \| null | 品类中文名 |
| `category` | string \| null | 原料类别 |
| `base_spirit_family` | string \| null | 基酒大类，如 `"rum"`、`"gin"`、`"whiskey"` |

---

## 9. 用户统计

### `GET /api/v1/map/stats` 或 `GET /api/v1/map/user/stats`

获取用户在所有主题的汇总进度，用于个人主页、成就页。

**请求示例**

```bash
GET /api/v1/map/user/stats
Authorization: Bearer eyJhbGci...
```

**成功响应** `200`

```json
{
  "code": 0,
  "data": {
    "total_xp": 75,
    "themes": [
      {
        "theme_id": 13,
        "name_zh": "经典基石",
        "total": 25,
        "completed": 8,
        "is_unlocked": true,
        "progress_pct": 32
      },
      {
        "theme_id": 14,
        "name_zh": "热带风情",
        "total": 27,
        "completed": 0,
        "is_unlocked": false,
        "progress_pct": 0
      }
    ]
  },
  "message": "ok"
}
```

**字段说明**

| 字段 | 类型 | 说明 |
|------|------|------|
| `total_xp` | int | 累计获得总经验值 |
| `themes[].theme_id` | int | 主题 ID |
| `themes[].name_zh` | string | 主题中文名 |
| `themes[].total` | int | 主题总节点数 |
| `themes[].completed` | int | 已完成节点数（跨主题共享，同一鸡尾酒在任意主题完成均计入） |
| `themes[].is_unlocked` | bool | 主题是否已解锁：入口节点无前置条件（如经典基石）始终为 `true`；子主题在对应门户节点完成后变为 `true` |
| `themes[].progress_pct` | int | 完成百分比（0-100） |

---

## 10. 公开接口（无需登录）

### `GET /api/v1/map/themes/list`

返回所有活跃主题的基本信息，不含用户进度，供编辑器或未登录页面使用。

**成功响应** `200`

```json
{
  "code": 0,
  "data": {
    "themes": [
      {
        "id": 13,
        "slug": "classic",
        "name_zh": "经典基石",
        "color_primary": "#C9A84C",
        "node_total": 25
      }
    ]
  },
  "message": "ok"
}
```

---

## 11. 编辑器接口

以下两个接口供星图可视化编辑器使用。

### `GET /api/v1/map/themes/:theme_id/layout`（无需登录）

返回主题节点 + 所有边，不含用户状态，供编辑器初始化布局。

**成功响应** `200`

```json
{
  "code": 0,
  "data": {
    "theme": {
      "id": 13,
      "slug": "classic",
      "name_zh": "经典基石",
      "color_primary": "#C9A84C"
    },
    "nodes": [
      {
        "id": 465,
        "node_key": "c_0",
        "display_name_zh": "自由古巴",
        "cocktail_id": 277,
        "is_entry_node": true,
        "is_boss": false,
        "complexity": 2,
        "gateway_spirit": "rum",
        "image_url": "https://cdn.example.com/cocktails/cuba-libre.jpg",
        "reward_xp": 10,
        "sort_order": 1,
        "pos_x": 370.0,
        "pos_y": 80.0
      }
    ],
    "edges": [
      { "from": 465, "to": 466, "type": "prerequisite", "label": null },
      { "from": 465, "to": 470, "type": "association",  "label": "风味相近" }
    ]
  },
  "message": "ok"
}
```

> `edges` 为扁平数组，通过 `type` 字段区分类型，取值：`prerequisite` / `progression` / `association` / `archetype_bridge` / `variant`。

**错误**

| code | message | HTTP |
|------|---------|------|
| 4401 | 主题不存在 | 404 |

---

### `PATCH /api/v1/map/nodes/positions`（需登录）

批量保存节点的 `pos_x` / `pos_y` 坐标，编辑器专用。

**Request Body**

```json
{
  "updates": [
    { "node_id": 465, "pos_x": 370.0, "pos_y": 80.0 },
    { "node_id": 466, "pos_x": 370.0, "pos_y": 230.0 }
  ]
}
```

| 字段 | 类型 | 必填 | 说明 |
|------|------|------|------|
| `updates` | array | ✅ | 位置更新列表 |
| `updates[].node_id` | int | ✅ | 节点 ID |
| `updates[].pos_x` | float \| null | ❌ | X 坐标 |
| `updates[].pos_y` | float \| null | ❌ | Y 坐标 |

**成功响应** `200`

```json
{
  "code": 0,
  "data": { "updated": 2 },
  "message": "位置已保存"
}
```

**错误**

| code | message | HTTP |
|------|---------|------|
| 4100 | updates 为必填数组 | 422 |

---

## 12. 数据模型

### 12.1 NodeStatus — 节点状态枚举

| 值 | 说明 |
|----|------|
| `locked` | 存在未完成的 prerequisite/progression 前置节点，或支线节点的 unlock_by 鸡尾酒未完成 |
| `available` | 入口节点，或所有前置节点均已完成，或支线节点的 unlock_by 鸡尾酒已完成 |
| `completed` | 用户已完成（调用过 complete 接口） |

### 12.2 EdgeType — 边类型枚举

| 值 | 影响解锁逻辑 | 说明 |
|----|-------------|------|
| `prerequisite` | ✅ 是 | 前置解锁关系（当前数据主要类型） |
| `progression` | ✅ 是 | 同上，早期数据使用，与 `prerequisite` 等价 |
| `association` | ❌ 否 | 风味/同源星座关联，仅供可视化展示 |
| `variant` | ❌ 否 | 配方变体关系，仅供可视化展示 |
| `archetype_bridge` | ❌ 否 | 跨原型桥接，仅供可视化展示 |

### 11.3 Node — 节点完整字段

| 字段 | 类型 | 说明 |
|------|------|------|
| `id` | int | 节点 ID |
| `node_key` | string \| null | 主题内唯一标识 |
| `cocktail_id` | int | 关联的鸡尾酒 ID |
| `is_entry_node` | bool | 是否为入口节点 |
| `is_boss` | bool | 是否为 Boss 节点 |
| `reward_xp` | int | 完成奖励经验值 |
| `sort_order` | int | 主题内排序 |
| `pos_x` / `pos_y` | float \| null | 编辑器写入的坐标 |
| `display_name_zh` | string \| null | 中文名（来自 `cocktails.name_zh`） |
| `complexity` | int \| null | 复杂度 1-5（来自 `cocktails.complexity_score`） |
| `gateway_spirit` | string \| null | 代表基酒（来自 `cocktails.gateway_spirit`） |
| `image_url` | string \| null | 图片（来自 `cocktails.image_url`） |
| `path_role` | string | 节点类型：`'main'`（主线）或 `'side'`（支线） |
| `unlock_by` | int \| null | 支线节点解锁所需的鸡尾酒ID（完成该酒即可解锁此节点） |

### 12.2 Edge — 边关系字段

| 字段 | 类型 | 说明 |
|------|------|------|
| `from` | int | 起始节点 ID |
| `to` | int | 目标节点 ID |
| `edge_type` | string | 边类型（`progression` / `association` / `prerequisite` / `archetype_bridge` / `variant`） |
| `label` | string \| null | 边标签（用于 `association` 和 `archetype_bridge`） |
| `path_role` | string | 边类型：`'main'`（主线关系）或 `'side'`（支线关系） |
| `status` | string | 边状态：`'locked'`（不可见）或 `'unlocked'`（可见），根据 from 节点状态计算 |

**边状态计算规则**：
- 当 from 节点的状态为 `available` 或 `completed` 时，边状态为 `unlocked`
- 当 from 节点的状态为 `locked` 时，边状态为 `locked`
- 前端可根据边的 `status` 控制连线的显示/隐藏或样式

### 12.5 Theme — 主题完整字段

| 字段 | 类型 | 说明 |
|------|------|------|
| `id` | int | 主题 ID |
| `slug` | string | 主题标识 |
| `name_zh` | string | 中文名 |
| `description_zh` | string \| null | 主题描述 |
| `color_primary` | string \| null | 主色 |
| `color_secondary` | string \| null | 辅色 |
| `icon_url` | string \| null | 图标 URL |
| `cover_url` | string \| null | 封面 URL |
| `sort_order` | int | 排列顺序 |
| `portal_cocktail_id` | int \| null | 星门配方 ID |

---

## 13. 错误码

| 错误码 | 说明 | HTTP 状态码 |
|--------|------|-------------|
| 4100 | 请求参数格式错误（如 updates 为空） | 422 |
| 4401 | 主题不存在 | 404 |
| 4402 | 节点不存在 | 404 |
| 4403 | 缺少完成节点所需的基酒（`message` 含具体基酒名） | 403 |
| 4001 | Token 无效 / 未携带 | 401 |
| 4003 | Token 已过期 | 401 |

---

## 14. 前端调用流程

### 14.1 首次进入星图页

```
1. GET /api/v1/map/themes
   → 获取主题列表及进度摘要
   → 渲染主题选择卡：name_zh、color_primary、node_completed/node_total

2. 用户点击主题
   → GET /api/v1/map/themes/:theme_id
   → 获取 nodes + 四类边
   → 渲染节点颜色：
       locked    → 灰色，不可点击
       available → 高亮，可点击查看配方
       completed → 打勾特效
   → 根据 path_role 区分渲染：
       main 节点 → 主线样式（明亮、突出）
       side 节点 → 支线样式（柔和、辅助）
   → 渲染 progression_edges 为主要导航连线
       根据 edge.status 控制连线显示：
       unlocked → 显示连线
       locked   → 隐藏或灰色虚线
   → 渲染 association_edges / variant_edges / archetype_bridge_edges 为辅助可视化连线
   → Boss 节点（is_boss=true）加特殊光效
```

### 14.2 点击节点 → 查看详情

```
GET /api/v1/map/nodes/:node_id
↓ 展示：cocktail.image_url、name_zh、story_zh
↓ 展示：ingredients 列表（is_base_spirit 标红、in_cabinet 标绿勾）
↓ 展示：制作步骤（instructions_zh）

根据 can_complete 分支：

├── can_complete: false（缺少基酒）
│   → 高亮显示 required_spirits 中 in_cabinet=false 的项
│   → 展示缺失基酒引导：
│       GET /api/v1/map/nodes/:id/missing-spirits（可选，获取更多信息）
│   → 「+ 添加到酒柜」→ POST /api/cabinet/items { "family_id": ... }
│   → 添加后重新请求节点详情，can_complete 变为 true 后解锁「完成」按钮

└── can_complete: true（基酒齐全，或无需基酒）
    → 「我做好了！完成节点」按钮可点击
    → POST /api/v1/map/nodes/:id/complete
        → 成功：reward_xp，触发升星动画
```

### 14.3 完成节点 → 制作纪念卡片

```
POST /api/v1/map/nodes/:id/complete 成功
    ↓
弹出卡片制作界面：
    1. 拍照 / 上传图片
       POST /api/card/upload-photo { file: <image> }
       → 返回 photo_url

    2. 前端 Canvas 渲染卡片预览
       （可调用 GET /api/card/templates 选择模板）

    3. 提交卡片
       POST /api/card/submit（multipart/form-data）
         image:        <Canvas 导出的 PNG>
         cocktail_id:  <节点的 cocktail_id>
         mood_caption: <用户输入心得>（可选）
         template_id:  <选中的模板 ID>（可选）
       → 返回 card_id、image_url
       → 分享 / 保存到相册
```

### 14.4 完成节点后刷新星图

```
POST /api/v1/map/nodes/:id/complete 成功后
    ↓
GET /api/v1/map/themes/:theme_id
    ↓ 后继节点的 status 可能从 locked → available
    ↓ 对新变为 available 的节点播放解锁动画
```

---

*VibeMix 星图探索 API v1.2 · 内部文档*
