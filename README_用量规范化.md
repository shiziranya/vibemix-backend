# 用量规范化功能 v1.6

> 将英制单位（oz、pint等）统一换算为毫升（ml），适配中国用户调酒习惯

---

## 🎯 核心特性

✅ **自动换算** - oz、cl、tsp 等单位自动转换为 ml  
✅ **简化整数** - oz 采用 1:30 简化换算，便于记忆  
✅ **保留专业术语** - dash → "滴"、barspoon 保持原样  
✅ **完全兼容** - 原有字段不变，新增字段可选  
✅ **类型标记** - 区分精确/约量/描述性用量

---

## 📚 快速导航

### 👨‍💻 我是前端开发

**最快 3 分钟接入** → [前端速查手册](./API_用量规范化_前端速查.md)

核心改动：
```jsx
// 之前
<span>{ingredient.measure_raw}</span>

// 现在（推荐）
<span>{ingredient.measure}</span>
```

完整 API 说明 → [API 变更文档](./API_用量规范化更新.md)

### 👨‍💼 我是后端开发

**快速部署（3步）** → [快速指南](./MEASURE_NORMALIZATION_QUICKSTART.md)

```bash
# 1. 数据库迁移
psql "$SUPABASE_DATABASE_URL" -f migrations/010_add_measure_normalized_fields.sql

# 2. 测试逻辑
python3 scripts/test_normalize.py

# 3. 批量规范化
python3 scripts/normalize_measures.py
```

完整技术文档 → [技术文档](./docs/measure_normalization.md)

### 📊 我要查看所有文档

完整文档索引 → [文档索引](./MEASURE_NORMALIZATION_INDEX.md)

---

## 📱 效果预览

### 之前
```json
{
  "name_zh": "金酒",
  "measure_raw": "1 1/2 oz"
}
```

### 之后
```json
{
  "name_zh": "金酒",
  "measure_raw": "1 1/2 oz",       // 保留
  "measure": "45ml",              // 🆕 推荐使用
  "measure_value": 45.0,          // 🆕 用于计算
  "measure_unit": "ml",           // 🆕 单位
  "measure_type": "precise"       // 🆕 类型
}
```

---

## 🔄 换算规则

| 原单位 | 换算为 | 示例 |
|--------|--------|------|
| **1 oz** | **30ml** | `"1 1/2 oz"` → `"45ml"` |
| 1 cl | 10ml | `"3 cl"` → `"30ml"` |
| 1 tsp | 5ml | `"1 tsp"` → `"5ml"` |
| 1 tbsp | 15ml | `"1 tbsp"` → `"15ml"` |
| dash | 保留 "滴" | `"2 dashes"` → `"2滴"` |
| barspoon | 保留 | `"1 barspoon"` → `"1barspoon"` |

---

## 📦 受影响的接口

✅ `GET /api/cocktails/:id` - 鸡尾酒详情  
✅ `GET /api/v1/map/nodes/:id` - 地图节点详情  
✅ `POST /api/recommend` - 推荐接口  
✅ `GET /api/recommend/history` - 推荐历史

所有返回 `ingredients` 数组的接口都已更新。

---

## 📂 文档清单

### 前端文档
- 📱 [前端速查手册](./API_用量规范化_前端速查.md) - 3分钟快速接入
- 📖 [API 变更文档](./API_用量规范化更新.md) - 完整 API 说明

### 后端文档
- ⚡ [快速指南](./MEASURE_NORMALIZATION_QUICKSTART.md) - 10分钟部署
- 📘 [技术文档](./docs/measure_normalization.md) - 完整技术方案
- 📋 [实施总结](./MEASURE_NORMALIZATION_SUMMARY.md) - 交付内容清单
- 📝 [变更日志](./CHANGELOG_measure_normalization.md) - 详细变更记录

### 工具脚本
- 🔧 [数据库迁移](./migrations/010_add_measure_normalized_fields.sql)
- 🔄 [规范化脚本](./scripts/normalize_measures.py)
- 🧪 [测试脚本](./scripts/test_normalize.py)
- 📊 [审计脚本](./scripts/check_measures.sql)

### 索引导航
- 📚 [文档索引](./MEASURE_NORMALIZATION_INDEX.md) - 完整文档导航

---

## ❓ 常见问题

### Q: 旧版客户端会受影响吗？
**A**: 不会。新字段是额外添加的，原有字段完全保持不变。

### Q: 为什么 oz 用 1:30 而不是 29.57？
**A**: 简化换算，便于用户记忆。在调酒场景中，1-2ml 的差异对口感影响很小。

### Q: dash 为什么不换算成 ml？
**A**: dash 是专业调酒术语，其精确值因工具而异，保留原术语更准确。

### Q: 前端需要做什么改动？
**A**: 最小改动：直接使用 `ingredient.measure` 替代 `ingredient.measure_raw`。无需改动也完全可以继续使用旧字段。

### Q: 如何计算鸡尾酒总容量？
**A**: 筛选 `measure_unit === 'ml'` 的原料，累加 `measure_value`。详见[前端速查](./API_用量规范化_前端速查.md)。

---

## 📞 技术支持

- 📧 后端团队: [联系方式]
- 📁 文档仓库: `/opt/vibemix/vibemix-backend/`
- 🔗 完整文档: [文档索引](./MEASURE_NORMALIZATION_INDEX.md)

---

**版本**: v1.6  
**发布日期**: 2026-07-19  
**状态**: ✅ 生产就绪
