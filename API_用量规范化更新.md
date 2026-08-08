# VibeMix - 用量规范化功能 API 更新文档

> 版本：v1.6  
> 更新时间：2026-07-19  
> 影响范围：所有返回原料列表的接口

---

## 📋 目录

- [1. 更新概览](#1-更新概览)
- [2. 向后兼容说明](#2-向后兼容说明)
- [3. 新增字段说明](#3-新增字段说明)
- [4. 受影响的接口](#4-受影响的接口)
- [5. 前端使用建议](#5-前端使用建议)
- [6. 完整示例](#6-完整示例)

---

## 1. 更新概览

### 1.1 更新背景

为更好地适配中国用户的调酒习惯，我们对所有原料用量进行了规范化处理：

- ✅ 英制单位（oz、pint等）统一换算为毫升（ml）
- ✅ 使用简化整数换算（oz 采用 1:30）
- ✅ 保留调酒专业术语（dash → "滴"、barspoon）
- ✅ 完全保留原始数据，支持回退

### 1.2 核心变化

**所有返回 `ingredients` 数组的接口**，每个原料对象都新增了 4 个字段：

| 新增字段 | 类型 | 说明 |
|---------|------|------|
| `measure` | string | 🆕 **规范化用量**（推荐使用），如 `"45ml"`, `"2滴"`, `"适量"` |
| `measure_value` | float \| null | 🆕 数值部分（用于计算和排序） |
| `measure_unit` | string \| null | 🆕 单位部分（`"ml"`, `"滴"`, `"barspoon"`, `"适量"` 等） |
| `measure_type` | string | 🆕 类型标记（见下文） |

**原有字段保持不变**：

| 原有字段 | 说明 | 变化 |
|---------|------|------|
| `measure_raw` | 原始用量描述 | ✅ 保持不变 |
| `measure_ml` | 毫升数（旧版换算） | ✅ 保持不变 |

---

## 2. 向后兼容说明

### ✅ 完全向后兼容

本次更新**不会破坏**现有客户端：

- ✅ 所有原有字段（`measure_raw`, `measure_ml`）保持不变
- ✅ 新增字段为可选字段，旧版客户端可忽略
- ✅ 接口路径、请求参数均无变化
- ✅ 认证方式不变

### 📱 升级建议

**新版客户端**：优先使用 `measure` 字段显示用量  
**旧版客户端**：继续使用 `measure_raw` 或 `measure_ml`

---

## 3. 新增字段说明

### 3.1 `measure` - 规范化用量（⭐ 推荐使用）

**类型**: `string`  
**说明**: 规范化后的中文用量，可直接展示给用户

**示例值**:
- `"45ml"` - 精确容量
- `"2滴"` - 约量（dash）
- `"1barspoon"` - 保留单位
- `"少许"` - 描述性用量
- `"适量"` - 默认值

**换算规则**:

| 原始值 | 规范化后 | 说明 |
|--------|---------|------|
| `"1 1/2 oz"` | `"45ml"` | oz → ml (1:30) |
| `"3 cl"` | `"30ml"` | cl → ml (1:10) |
| `"1 tsp"` | `"5ml"` | 茶匙 → ml |
| `"1 tbsp"` | `"15ml"` | 汤匙 → ml |
| `"2 dashes"` | `"2滴"` | 保留专业术语 |
| `"1 barspoon"` | `"1barspoon"` | 保留单位 |
| `"splash"` | `"少许"` | 描述性 |
| `"to taste"` | `"适量"` | 描述性 |

### 3.2 `measure_value` - 数值部分

**类型**: `float | null`  
**说明**: 用量的数值部分，用于计算和排序

**示例值**:
- `45.0` - 45ml
- `2.0` - 2滴
- `null` - 无数值（如"适量"）

**用途**:
- 计算鸡尾酒总用量
- 按用量排序原料
- 支持配方倍数调整

### 3.3 `measure_unit` - 单位部分

**类型**: `string | null`  
**说明**: 用量的单位部分

**可能的值**:
- `"ml"` - 毫升（最常见）
- `"滴"` - dash
- `"barspoon"` - barspoon
- `"个"` - 水果等（如"半个青柠"）
- `"适量"` - 描述性单位
- `"少许"` - 描述性单位
- `null` - 无单位

### 3.4 `measure_type` - 类型标记

**类型**: `string`  
**说明**: 标记用量的类型，用于前端展示优化

**可能的值**:

| 值 | 说明 | 示例 | 前端建议 |
|----|------|------|---------|
| `"precise"` | 精确用量 | `"45ml"`, `"1barspoon"` | 直接显示 |
| `"approximate"` | 约量 | `"2滴"` | 添加 "约" 标记 |
| `"descriptive"` | 描述性 | `"适量"`, `"少许"` | 可用灰色显示 |
| `"unclear"` | 需确认 | `"1/2"` (无单位) | 后端会逐步修正 |

---

## 4. 受影响的接口

### 4.1 鸡尾酒详情

**接口**: `GET /api/cocktails/:id`  
**文档**: 查看配方详情接口  
**变化**: `ingredients` 数组中每个原料对象新增 4 个字段

### 4.2 地图节点详情

**接口**: `GET /api/v1/map/nodes/:node_id`  
**文档**: [地图探索API文档 - 节点详情](#)  
**变化**: `ingredients` 数组中每个原料对象新增 4 个字段

### 4.3 推荐接口

**接口**: `POST /api/recommend`  
**文档**: 查看推荐功能文档  
**变化**: 返回的鸡尾酒配方中 `ingredient_list` 数组的每个原料对象新增 4 个字段

### 4.4 推荐历史

**接口**: `GET /api/recommend/history`  
**文档**: [推荐功能API文档](#)  
**变化**: 历史记录中的鸡尾酒配方 `ingredients` 数组新增 4 个字段

---

## 5. 前端使用建议

### 5.1 基础显示（推荐）

最简单的方式，直接使用 `measure` 字段：

```jsx
// React 示例
function IngredientItem({ ingredient }) {
  return (
    <div className="ingredient">
      <span className="name">{ingredient.name_zh}</span>
      <span className="measure">{ingredient.measure}</span>
    </div>
  );
}
```

```vue
<!-- Vue 示例 -->
<template>
  <div class="ingredient">
    <span class="name">{{ ingredient.name_zh }}</span>
    <span class="measure">{{ ingredient.measure }}</span>
  </div>
</template>
```

### 5.2 带类型标记（进阶）

根据 `measure_type` 添加视觉提示：

```jsx
function IngredientMeasure({ ingredient }) {
  const { measure, measure_type } = ingredient;
  
  return (
    <span className={`measure measure-${measure_type}`}>
      {measure}
      {measure_type === 'approximate' && (
        <span className="badge">约</span>
      )}
    </span>
  );
}
```

**CSS 建议**:
```css
.measure-precise {
  color: #333;
  font-weight: 500;
}

.measure-approximate {
  color: #666;
}

.measure-descriptive {
  color: #999;
  font-style: italic;
}
```

### 5.3 支持单位切换（高级）

如果需要支持用户偏好（ml / oz）：

```jsx
function IngredientMeasure({ ingredient, userPreference }) {
  const { measure, measure_raw } = ingredient;
  
  // 根据用户偏好显示不同单位
  if (userPreference === 'imperial' && measure_raw) {
    return <span>{measure_raw}</span>;
  }
  
  // 默认显示规范化用量（ml）
  return <span>{measure}</span>;
}
```

### 5.4 计算总用量

利用 `measure_value` 计算鸡尾酒总容量：

```javascript
function calculateTotalVolume(ingredients) {
  return ingredients
    .filter(ing => ing.measure_unit === 'ml')
    .reduce((sum, ing) => sum + (ing.measure_value || 0), 0);
}

// 使用示例
const totalMl = calculateTotalVolume(cocktail.ingredients);
console.log(`总容量: ${totalMl}ml`);
```

### 5.5 配方倍数调整

支持用户调整配方份数：

```javascript
function adjustRecipe(ingredients, multiplier) {
  return ingredients.map(ing => {
    // 只调整有数值的用量
    if (ing.measure_value && ing.measure_unit === 'ml') {
      const newValue = ing.measure_value * multiplier;
      return {
        ...ing,
        measure: `${Math.round(newValue)}ml`,
        measure_value: newValue
      };
    }
    // 描述性用量不变
    return ing;
  });
}

// 使用示例：制作 2 倍份量
const doubledRecipe = adjustRecipe(cocktail.ingredients, 2);
```

---

## 6. 完整示例

### 6.1 鸡尾酒详情接口响应

**请求**:
```bash
GET /api/cocktails/123
Authorization: Bearer <token>
```

**响应**:
```json
{
  "code": 0,
  "message": "ok",
  "data": {
    "id": 123,
    "name": "Margarita",
    "name_zh": "玛格丽特",
    "difficulty": 2,
    "abv_level": "medium",
    "image_url": "https://example.com/margarita.jpg",
    "ingredients": [
      {
        "ingredient_id": 45,
        "ingredient_family_id": 270,
        "name": "Tequila",
        "name_zh": "龙舌兰",
        "category": "spirit",
        
        // ===== 原有字段（保持不变）=====
        "measure_raw": "1 1/2 oz",
        "measure_ml": 44.36,
        
        // ===== 🆕 新增字段 =====
        "measure": "45ml",
        "measure_value": 45.0,
        "measure_unit": "ml",
        "measure_type": "precise",
        
        "status": "owned",
        "substitute": null,
        "is_easily_available": true
      },
      {
        "ingredient_id": 78,
        "ingredient_family_id": 145,
        "name": "Triple Sec",
        "name_zh": "橙皮利口酒",
        "category": "liqueur",
        
        "measure_raw": "1 oz",
        "measure_ml": 29.57,
        
        // 🆕 新字段
        "measure": "30ml",
        "measure_value": 30.0,
        "measure_unit": "ml",
        "measure_type": "precise",
        
        "status": "missing",
        "substitute": null,
        "is_easily_available": true
      },
      {
        "ingredient_id": 92,
        "ingredient_family_id": 89,
        "name": "Lime Juice",
        "name_zh": "青柠汁",
        "category": "juice",
        
        "measure_raw": "1 oz",
        "measure_ml": 29.57,
        
        // 🆕 新字段
        "measure": "30ml",
        "measure_value": 30.0,
        "measure_unit": "ml",
        "measure_type": "precise",
        
        "status": "owned",
        "substitute": null,
        "is_easily_available": true
      },
      {
        "ingredient_id": 156,
        "ingredient_family_id": null,
        "name": "Salt",
        "name_zh": "盐",
        "category": "other",
        
        "measure_raw": "for rim",
        "measure_ml": null,
        
        // 🆕 新字段
        "measure": "装饰用",
        "measure_value": null,
        "measure_unit": null,
        "measure_type": "descriptive",
        
        "status": "owned",
        "substitute": null,
        "is_easily_available": true
      }
    ],
    "preparation_steps": [
      {
        "order": 1,
        "text": "将杯口用青柠擦拭后蘸盐",
        "duration_hint": null
      },
      {
        "order": 2,
        "text": "在摇酒器中加入龙舌兰45ml、橙皮利口酒30ml、青柠汁30ml和冰块",
        "duration_hint": null
      },
      {
        "order": 3,
        "text": "充分摇匀约10秒",
        "duration_hint": "10秒"
      },
      {
        "order": 4,
        "text": "滤冰倒入准备好的杯中",
        "duration_hint": null
      }
    ]
  }
}
```

### 6.2 地图节点详情响应

**请求**:
```bash
GET /api/v1/map/nodes/42
Authorization: Bearer <token>
```

**响应**:
```json
{
  "code": 0,
  "message": "ok",
  "data": {
    "node": {
      "id": 42,
      "theme_id": 13,
      "cocktail_id": 89,
      "node_key": "negroni",
      "is_entry_node": false,
      "is_boss": false,
      "reward_xp": 50
    },
    "cocktail": {
      "id": 89,
      "name": "Negroni",
      "name_zh": "尼格罗尼",
      "story_zh": "1919年诞生于佛罗伦萨...",
      "story_hook_zh": "苦中带甜的意式经典",
      "difficulty": 1,
      "abv_level": "high",
      "glass_type": "Old Fashioned Glass",
      "image_url": "https://example.com/negroni.jpg"
    },
    "ingredients": [
      {
        "sort_order": 1,
        "name": "Gin",
        "name_zh": "金酒",
        
        // 原有字段
        "measure_raw": "1 oz",
        "measure_ml": 29.57,
        
        // 🆕 新增字段
        "measure": "30ml",
        "measure_value": 30.0,
        "measure_unit": "ml",
        "measure_type": "precise",
        
        "family_id": 265,
        "family_name_zh": "金酒",
        "is_base_spirit": true,
        "in_cabinet": true
      },
      {
        "sort_order": 2,
        "name": "Campari",
        "name_zh": "金巴利",
        
        "measure_raw": "1 oz",
        "measure_ml": 29.57,
        
        // 🆕 新字段
        "measure": "30ml",
        "measure_value": 30.0,
        "measure_unit": "ml",
        "measure_type": "precise",
        
        "family_id": 148,
        "family_name_zh": "金巴利",
        "is_base_spirit": false,
        "in_cabinet": false
      },
      {
        "sort_order": 3,
        "name": "Sweet Vermouth",
        "name_zh": "甜味美思",
        
        "measure_raw": "1 oz",
        "measure_ml": 29.57,
        
        // 🆕 新字段
        "measure": "30ml",
        "measure_value": 30.0,
        "measure_unit": "ml",
        "measure_type": "precise",
        
        "family_id": 312,
        "family_name_zh": "甜味美思",
        "is_base_spirit": false,
        "in_cabinet": true
      },
      {
        "sort_order": 4,
        "name": "Orange Peel",
        "name_zh": "橙皮",
        
        "measure_raw": "garnish",
        "measure_ml": null,
        
        // 🆕 新字段
        "measure": "装饰用",
        "measure_value": null,
        "measure_unit": null,
        "measure_type": "descriptive",
        
        "family_id": 98,
        "family_name_zh": "橙皮",
        "is_base_spirit": false,
        "in_cabinet": false
      }
    ],
    "required_spirits": [
      {
        "id": 265,
        "name": "Gin",
        "name_zh": "金酒",
        "base_spirit_family": "gin",
        "in_cabinet": true
      }
    ],
    "can_complete": false,
    "missing_ingredients": [
      {
        "family_id": 148,
        "name": "Campari",
        "name_zh": "金巴利",
        "family_name_zh": "金巴利",
        "category": "liqueur",
        "base_spirit_family": null,
        "is_base_spirit": false,
        "measure_raw": "1 oz"
      }
    ]
  }
}
```

### 6.3 约量示例（dash）

```json
{
  "ingredient_id": 234,
  "name_zh": "安格斯图拉苦精",
  
  "measure_raw": "2 dashes",
  "measure_ml": null,
  
  // 🆕 新字段
  "measure": "2滴",
  "measure_value": 2.0,
  "measure_unit": "滴",
  "measure_type": "approximate"  // 👈 注意：标记为约量
}
```

### 6.4 保留单位示例（barspoon）

```json
{
  "ingredient_id": 345,
  "name_zh": "糖浆",
  
  "measure_raw": "1 barspoon",
  "measure_ml": null,
  
  // 🆕 新字段
  "measure": "1barspoon",
  "measure_value": 1.0,
  "measure_unit": "barspoon",
  "measure_type": "precise"
}
```

---

## 附录：单位换算对照表

### 容量单位换算

| 原单位 | 换算比例 | 说明 |
|--------|---------|------|
| **1 oz** (盎司) | **30ml** | 简化整数换算（标准为29.57ml） |
| 1 cl (厘升) | 10ml | 标准换算 |
| 1 tsp (茶匙) | 5ml | 标准茶匙 |
| 1 tbsp (汤匙) | 15ml | 标准汤匙 |
| 1 shot | 45ml | 标准shot |
| 1 pint (品脱) | 473ml | 美制品脱 |
| 1 quart (夸脱) | 946ml | 美制夸脱 |
| 1 gallon (加仑) | 3785ml | 美制加仑 |

### 保留术语

| 术语 | 中文 | 换算 |
|------|------|------|
| dash | 滴 | 保留不换算（约0.9ml） |
| barspoon | barspoon | 保留不换算（约5ml） |

### 描述性关键词

| 英文 | 中文 |
|------|------|
| splash / pinch | 少许 |
| to taste | 适量 |
| garnish | 装饰用 |
| top up / fill | 补满 |

---

## 常见问题

### Q1: 为什么 `measure` 字段有时显示"适量"？

**A**: 当原始用量为描述性文本（如 "garnish", "splash"）或无法解析时，会使用"适量"作为默认值。这类原料通常是装饰或调味用，无需精确计量。

### Q2: 前端需要做什么改动？

**A**: 
- **最小改动**：直接使用 `ingredient.measure` 替代 `ingredient.measure_raw`
- **无需改动**：继续使用 `measure_raw` 或 `measure_ml` 也完全可以

### Q3: `measure_type` 为 "approximate" 时如何显示？

**A**: 建议在用量后添加 "约" 标记，例如：
```jsx
{measure_type === 'approximate' ? `${measure} (约)` : measure}
```

### Q4: 如何计算鸡尾酒总容量？

**A**: 筛选 `measure_unit === 'ml'` 的原料，累加 `measure_value`：
```javascript
const totalMl = ingredients
  .filter(ing => ing.measure_unit === 'ml')
  .reduce((sum, ing) => sum + (ing.measure_value || 0), 0);
```

### Q5: 旧版客户端会受影响吗？

**A**: 不会。所有新增字段都是额外添加的，原有字段完全保持不变。旧版客户端可以继续使用，不会报错。

---

## 技术支持

如有疑问，请联系后端团队或查阅以下文档：

- 📘 完整技术文档: `docs/measure_normalization.md`
- ⚡ 快速开始指南: `MEASURE_NORMALIZATION_QUICKSTART.md`
- 📋 实施总结: `MEASURE_NORMALIZATION_SUMMARY.md`

**更新日期**: 2026-07-19  
**文档版本**: v1.0
