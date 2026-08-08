# 用量规范化方案实施指南

## 📋 概述

为了更好地适配中国用户的调酒习惯，我们对 `cocktail_ingredients` 表的用量字段进行了规范化改造，将英制单位（oz、pint等）统一换算为毫升（ml），同时保留调酒专业术语（dash、barspoon）。

## 🎯 设计目标

1. **用户友好**：优先展示 ml 单位，符合中国用户习惯
2. **保留原始数据**：`measure_raw` 字段不变，可回退
3. **专业性**：保留 dash、barspoon 等调酒术语
4. **简化计算**：使用整数换算比例，便于记忆和计算

## 📊 数据库结构

### 新增字段

```sql
-- cocktail_ingredients 表新增字段
measure_normalized  VARCHAR(100)   -- 规范化后的中文用量，如"45ml"、"2滴"、"适量"
measure_value       NUMERIC(7,2)   -- 数值部分（用于计算和排序）
measure_unit        VARCHAR(20)    -- 单位部分：ml/滴/barspoon/适量等
measure_type        VARCHAR(20)    -- 类型：precise/approximate/descriptive/unclear
```

### 字段说明

| 字段 | 说明 | 示例 |
|------|------|------|
| `measure_raw` | 原始用量（保留不变） | `"1 1/2 oz"`, `"2 dashes"` |
| `measure_normalized` | 规范化后的中文用量 | `"45ml"`, `"2滴"`, `"适量"` |
| `measure_value` | 数值部分 | `45.0`, `2.0`, `null` |
| `measure_unit` | 单位 | `"ml"`, `"滴"`, `"barspoon"`, `"适量"` |
| `measure_type` | 类型标记 | `"precise"`, `"approximate"`, `"descriptive"`, `"unclear"` |

### measure_type 类型说明

- **precise** (精确)：可精确测量的用量，如 `45ml`, `10ml`, `1 barspoon`
- **approximate** (约量)：近似用量，如 `2滴` (dash)
- **descriptive** (描述性)：非数值描述，如 `适量`, `少许`, `补满`
- **unclear** (需确认)：无法自动解析，需人工审核的用量

## 🔄 单位换算规则

### 需要换算的单位（→ ml）

| 原单位 | 换算比例 | 说明 |
|--------|---------|------|
| oz (盎司) | 1:30 | 简化整数换算（标准为29.57） |
| cl (厘升) | 1:10 | 1cl = 10ml |
| pint (品脱) | 1:473 | 美制品脱 |
| quart (夸脱) | 1:946 | 美制夸脱 |
| gallon (加仑) | 1:3785 | 美制加仑 |
| tsp (茶匙) | 1:5 | 标准茶匙 |
| tbsp (汤匙) | 1:15 | 标准汤匙 |
| shot | 1:45 | 标准shot = 45ml |

### 保留不换算的单位

| 单位 | 中文 | 类型 | 说明 |
|------|------|------|------|
| dash | 滴 | approximate | 约0.9ml/滴，但不换算 |
| barspoon | barspoon | precise | 保留原样 |

### 描述性关键词映射

| 原文 | 规范化 |
|------|--------|
| top up / fill | 补满 |
| garnish | 装饰用 |
| to taste | 适量 |
| splash / pinch | 少许 |

## 🚀 实施步骤

### 1. 执行数据库迁移

```bash
cd /opt/vibemix/vibemix-backend

# 方式A：使用 psql
psql "$SUPABASE_DATABASE_URL" -f migrations/010_add_measure_normalized_fields.sql

# 方式B：使用 Python 脚本
python3 -c "
from sqlalchemy import create_engine
import os
engine = create_engine(os.getenv('SUPABASE_DATABASE_URL'))
with open('migrations/010_add_measure_normalized_fields.sql') as f:
    with engine.begin() as conn:
        conn.execute(f.read())
print('✅ 迁移完成')
"
```

### 2. 执行规范化脚本

```bash
# 运行规范化脚本
python3 scripts/normalize_measures.py
```

预期输出：
```
开始规范化 1234 条记录...

  处理进度: 100/1234 (8%)
  处理进度: 200/1234 (16%)
  ...
  处理进度: 1234/1234 (100%)

✅ 规范化完成！

统计结果:
  精确用量 (precise): 850
  约量 (approximate): 120
  描述性 (descriptive): 200
  需人工确认 (unclear): 64
```

### 3. 人工审核不明确的记录

```sql
-- 查看需要人工确认的记录
SELECT 
    id, 
    measure_raw, 
    measure_normalized, 
    measure_type
FROM cocktail_ingredients
WHERE measure_type = 'unclear'
ORDER BY id;

-- 手动修正示例
UPDATE cocktail_ingredients
SET 
    measure_normalized = '半个',
    measure_value = 0.5,
    measure_unit = '个',
    measure_type = 'precise'
WHERE id = 123 AND measure_raw = '1/2';  -- 假设这是 "半个青柠"
```

### 4. 验证数据

```sql
-- 统计各类型数量
SELECT measure_type, COUNT(*) as count
FROM cocktail_ingredients
WHERE measure_raw IS NOT NULL
GROUP BY measure_type
ORDER BY count DESC;

-- 抽样检查换算结果
SELECT 
    measure_raw,
    measure_normalized,
    measure_value,
    measure_unit,
    measure_type
FROM cocktail_ingredients
WHERE measure_raw LIKE '%oz%'
LIMIT 20;
```

## 📱 前端展示

### API 响应示例

```json
{
  "ingredients": [
    {
      "name_zh": "金酒",
      "measure_raw": "1 1/2 oz",
      "measure": "45ml",
      "measure_value": 45.0,
      "measure_unit": "ml",
      "measure_type": "precise"
    },
    {
      "name_zh": "苦精",
      "measure_raw": "2 dashes",
      "measure": "2滴",
      "measure_value": 2.0,
      "measure_unit": "滴",
      "measure_type": "approximate"
    },
    {
      "name_zh": "青柠汁",
      "measure_raw": "splash",
      "measure": "少许",
      "measure_value": null,
      "measure_unit": null,
      "measure_type": "descriptive"
    }
  ]
}
```

### 前端显示建议

```javascript
// 获取显示用量的函数
function getDisplayMeasure(ingredient) {
  const { measure, measure_type } = ingredient;
  
  // 优先使用 measure 字段
  if (measure) {
    // 如果是约量，添加 "约" 标记
    if (measure_type === 'approximate') {
      return `${measure} (约)`;
    }
    return measure;
  }
  
  // 降级到原始值
  return ingredient.measure_raw || '适量';
}

// 示例
getDisplayMeasure({ measure: "45ml", measure_type: "precise" })
// → "45ml"

getDisplayMeasure({ measure: "2滴", measure_type: "approximate" })
// → "2滴 (约)"

getDisplayMeasure({ measure: "适量", measure_type: "descriptive" })
// → "适量"
```

## 🔍 常见问题

### Q1: 为什么 oz 换算用 1:30 而不是标准的 1:29.5735？

**A:** 为了简化计算，便于用户记忆。在调酒场景中，1-2ml的差异对最终口感影响很小，而整数换算更容易理解和应用。

### Q2: dash 为什么不换算成 ml？

**A:** dash (摇滴) 是调酒中的专业术语，其精确值因工具和手法而异（约0.9ml），在专业语境中保留原术语更准确。对于需要精确计量的场景，我们会标记其 `measure_type` 为 `approximate`。

### Q3: 如果以后想恢复原始数据怎么办？

**A:** `measure_raw` 字段完全保留原始数据，可随时回退。规范化数据存储在新增字段中，不会覆盖原始值。

### Q4: 规范化脚本可以重复运行吗？

**A:** 可以。脚本会覆盖现有的规范化数据，但不会修改 `measure_raw`。如果调整了换算规则，重新运行脚本即可更新。

## 📝 后续优化建议

1. **用户偏好设置**：允许用户选择显示单位（ml / oz）
2. **智能建议**：当用户没有量酒器时，提供"家用工具替代"（如"约3汤匙"）
3. **配比可视化**：在详情页展示各原料用量的比例图
4. **批量换算工具**：提供计算器，支持按倍数调整配方用量

## 🔗 相关文件

- 迁移脚本: `/migrations/010_add_measure_normalized_fields.sql`
- 规范化脚本: `/scripts/normalize_measures.py`
- 服务更新:
  - `/app/services/cocktail_service.py`
  - `/app/services/map_service.py`
  - `/app/services/recommend_service.py`
- API 文档: `/地图探索api.md`, `/API_我的卡片和推荐.md`

## 📞 技术支持

如有问题或需要调整换算规则，请联系开发团队。
