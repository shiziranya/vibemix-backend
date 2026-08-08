# 用量规范化 - 前端速查手册

> 快速参考指南，帮助前端快速接入新的用量字段

---

## 🚀 快速开始（3 分钟接入）

### 最简单的方式

**只需要改一行代码**：把 `measure_raw` 换成 `measure`

```jsx
// 之前
<span>{ingredient.measure_raw}</span>

// 现在（推荐）
<span>{ingredient.measure}</span>
```

就是这么简单！✨

---

## 📋 新增字段速查

| 字段 | 示例值 | 说明 | 推荐使用 |
|------|--------|------|---------|
| `measure` | `"45ml"`, `"2滴"`, `"适量"` | 规范化用量，可直接显示 | ⭐⭐⭐⭐⭐ |
| `measure_value` | `45.0`, `2.0`, `null` | 数值部分（用于计算） | ⭐⭐⭐ |
| `measure_unit` | `"ml"`, `"滴"`, `"适量"` | 单位部分 | ⭐⭐ |
| `measure_type` | `"precise"`, `"approximate"` | 类型标记 | ⭐⭐ |

---

## 💡 常用场景

### 场景 1：显示原料列表

```jsx
function IngredientList({ ingredients }) {
  return (
    <ul>
      {ingredients.map(ing => (
        <li key={ing.id}>
          <span className="name">{ing.name_zh}</span>
          <span className="measure">{ing.measure}</span>
        </li>
      ))}
    </ul>
  );
}
```

### 场景 2：带 "约" 标记

```jsx
function MeasureDisplay({ measure, measure_type }) {
  return (
    <span>
      {measure}
      {measure_type === 'approximate' && <span className="badge">约</span>}
    </span>
  );
}
```

### 场景 3：计算总容量

```javascript
const totalMl = ingredients
  .filter(ing => ing.measure_unit === 'ml')
  .reduce((sum, ing) => sum + (ing.measure_value || 0), 0);
```

### 场景 4：配方倍数调整

```javascript
function multiplyRecipe(ingredients, multiplier) {
  return ingredients.map(ing => {
    if (ing.measure_value && ing.measure_unit === 'ml') {
      return {
        ...ing,
        measure: `${Math.round(ing.measure_value * multiplier)}ml`
      };
    }
    return ing; // 描述性用量不变
  });
}
```

---

## 📖 换算对照表

### 常见单位换算

| 原始值 | 规范化后 |
|--------|---------|
| `"1 oz"` | `"30ml"` |
| `"1 1/2 oz"` | `"45ml"` |
| `"2 oz"` | `"60ml"` |
| `"3 cl"` | `"30ml"` |
| `"1 tsp"` | `"5ml"` |
| `"1 tbsp"` | `"15ml"` |
| `"2 dashes"` | `"2滴"` |
| `"1 barspoon"` | `"1barspoon"` |
| `"splash"` | `"少许"` |
| `"to taste"` | `"适量"` |
| `"garnish"` | `"装饰用"` |

---

## 🎨 样式建议

```css
/* 基础样式 */
.measure {
  font-weight: 500;
  color: #333;
}

/* 精确用量 */
.measure-precise {
  color: #2c3e50;
}

/* 约量 - 略灰 */
.measure-approximate {
  color: #666;
}

.measure-approximate .badge {
  font-size: 0.75em;
  color: #999;
  margin-left: 2px;
}

/* 描述性用量 - 更灰、斜体 */
.measure-descriptive {
  color: #999;
  font-style: italic;
}
```

---

## ⚠️ 常见问题

### Q: 旧版客户端会报错吗？

**A**: 不会。新字段是额外添加的，旧版继续用 `measure_raw` 完全没问题。

### Q: 为什么有些显示"适量"？

**A**: 原始数据是描述性的（如 "garnish", "splash"），这类原料通常无需精确计量。

### Q: measure_type 有什么用？

**A**: 可以用来添加视觉提示：
- `precise` - 正常显示
- `approximate` - 添加 "约" 标记
- `descriptive` - 用灰色/斜体显示

### Q: 需要支持单位切换吗（ml ↔ oz）？

**A**: 看产品需求。如果需要，可以根据用户设置切换显示 `measure`（ml）或 `measure_raw`（oz）。

---

## 📦 受影响的接口

| 接口 | 影响 |
|------|------|
| `GET /api/cocktails/:id` | ✅ 已更新 |
| `GET /api/v1/map/nodes/:id` | ✅ 已更新 |
| `POST /api/recommend` | ✅ 已更新 |
| `GET /api/recommend/history` | ✅ 已更新 |

所有返回 `ingredients` 数组的接口都已包含新字段。

---

## 📱 完整示例：原料卡片组件

```jsx
import React from 'react';
import './IngredientCard.css';

function IngredientCard({ ingredient }) {
  const {
    name_zh,
    measure,
    measure_type,
    in_cabinet,
    category
  } = ingredient;

  return (
    <div className={`ingredient-card ${in_cabinet ? 'owned' : 'missing'}`}>
      <div className="ingredient-header">
        <span className="name">{name_zh}</span>
        {in_cabinet && <span className="badge-owned">已拥有</span>}
      </div>
      
      <div className="ingredient-measure">
        <span className={`measure measure-${measure_type}`}>
          {measure}
        </span>
        {measure_type === 'approximate' && (
          <span className="badge-approximate">约</span>
        )}
      </div>
      
      <div className="ingredient-category">{category}</div>
    </div>
  );
}

export default IngredientCard;
```

```css
/* IngredientCard.css */
.ingredient-card {
  padding: 12px;
  border-radius: 8px;
  border: 1px solid #e0e0e0;
  background: #fff;
}

.ingredient-card.missing {
  background: #f9f9f9;
}

.ingredient-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
  margin-bottom: 8px;
}

.name {
  font-weight: 600;
  font-size: 16px;
}

.badge-owned {
  font-size: 12px;
  padding: 2px 8px;
  background: #4caf50;
  color: white;
  border-radius: 12px;
}

.ingredient-measure {
  display: flex;
  align-items: center;
  gap: 4px;
  margin-bottom: 4px;
}

.measure {
  font-size: 18px;
  font-weight: 500;
}

.measure-precise {
  color: #2c3e50;
}

.measure-approximate {
  color: #666;
}

.measure-descriptive {
  color: #999;
  font-style: italic;
}

.badge-approximate {
  font-size: 12px;
  color: #999;
}

.ingredient-category {
  font-size: 12px;
  color: #999;
}
```

---

## 🔗 更多资源

- 📘 完整 API 文档: `API_用量规范化更新.md`
- 🗺️ 地图探索接口: `地图探索api.md` (已更新 v1.6)
- 💡 推荐功能接口: `API_我的卡片和推荐.md` (已更新 v1.1)

---

**最后更新**: 2026-07-19  
**版本**: v1.0  
**状态**: ✅ 生产就绪
