# Changelog - 用量规范化功能

## [Unreleased] - 2026-07-19

### 🎉 新增功能

#### 用量规范化系统

为更好地适配中国用户习惯，新增了完整的用量规范化系统。

**核心特性**:
- ✅ 英制单位（oz、pint等）自动换算为毫升（ml）
- ✅ 保留调酒专业术语（dash → "滴"、barspoon）
- ✅ 简化整数换算（oz 使用 1:30 而非 29.57）
- ✅ 完全保留原始数据，支持回退

### 📊 数据库变更

#### 新增字段 - `cocktail_ingredients` 表

| 字段名 | 类型 | 说明 |
|--------|------|------|
| `measure_normalized` | VARCHAR(100) | 规范化后的中文用量（如"45ml"、"2滴"） |
| `measure_value` | NUMERIC(7,2) | 数值部分（用于排序和计算） |
| `measure_unit` | VARCHAR(20) | 单位（ml/滴/barspoon/适量等） |
| `measure_type` | VARCHAR(20) | 类型：precise/approximate/descriptive/unclear |

**迁移文件**: `migrations/010_add_measure_normalized_fields.sql`

### 🔧 API 变更

#### 影响的端点

所有返回原料列表的接口都新增了规范化用量字段：

- `GET /api/cocktails/:id` - 鸡尾酒详情
- `GET /api/map/nodes/:id` - 地图节点详情
- `POST /api/recommend` - 推荐接口

#### 响应变更（向后兼容）

**新增字段**（不影响现有客户端）:

```json
{
  "ingredients": [
    {
      "measure_raw": "1 1/2 oz",      // 保留原始值
      "measure_ml": 44.36,            // 保留原始值
      "measure": "45ml",              // 🆕 规范化用量（推荐使用）
      "measure_value": 45.0,          // 🆕 数值部分
      "measure_unit": "ml",           // 🆕 单位
      "measure_type": "precise"       // 🆕 类型标记
    }
  ]
}
```

### 📝 换算规则

#### 需要换算的单位 → ml

| 原单位 | 换算比例 | 示例 |
|--------|---------|------|
| oz | 1:30 | "1.5 oz" → "45ml" |
| cl | 1:10 | "3 cl" → "30ml" |
| tsp | 1:5 | "1 tsp" → "5ml" |
| tbsp | 1:15 | "1 tbsp" → "15ml" |
| pint | 1:473 | "1 pint" → "473ml" |
| quart | 1:946 | "1 quart" → "946ml" |
| gallon | 1:3785 | "1 gallon" → "3785ml" |

#### 保留的单位（不换算）

| 原单位 | 规范化为 | 类型 |
|--------|---------|------|
| dash | "滴" | approximate |
| barspoon | "barspoon" | precise |

#### 描述性关键词

| 原文 | 规范化为 |
|------|---------|
| splash / pinch | "少许" |
| to taste | "适量" |
| garnish | "装饰用" |
| top up / fill | "补满" |

### 🛠️ 新增工具和脚本

#### 规范化工具

**文件**: `scripts/normalize_measures.py`

批量规范化所有 `cocktail_ingredients` 记录：
```bash
python3 scripts/normalize_measures.py
```

#### 测试工具

**文件**: `scripts/test_normalize.py`

验证规范化逻辑的正确性（24个测试用例）：
```bash
python3 scripts/test_normalize.py
```

#### 数据审计

**文件**: `scripts/check_measures.sql`

生成详细的数据审计报告：
```bash
psql "$SUPABASE_DATABASE_URL" -f scripts/check_measures.sql
```

### 📚 文档更新

- 🆕 `docs/measure_normalization.md` - 完整的技术文档
- 🆕 `MEASURE_NORMALIZATION_QUICKSTART.md` - 快速开始指南
- 🆕 `MEASURE_NORMALIZATION_SUMMARY.md` - 实施总结

### 🔄 服务层更新

#### 修改的文件

- `app/services/cocktail_service.py`
  - 更新 `_get_ingredients()` 方法
  - 新增 `measure` 字段返回规范化用量

- `app/services/map_service.py`
  - 更新 `get_node_detail()` 方法
  - 查询新增规范化字段

- `app/services/recommend_service.py`
  - 更新原料查询逻辑
  - 保持与其他服务一致

### ⚠️ 破坏性变更

**无** - 本次更新完全向后兼容。

所有新增字段为可选字段，现有客户端可继续使用 `measure_raw` 和 `measure_ml`。

### 🚀 部署步骤

#### 1. 执行数据库迁移

```bash
cd /opt/vibemix/vibemix-backend
psql "$SUPABASE_DATABASE_URL" -f migrations/010_add_measure_normalized_fields.sql
```

#### 2. 测试规范化逻辑（可选）

```bash
python3 scripts/test_normalize.py
```

#### 3. 批量规范化现有数据

```bash
python3 scripts/normalize_measures.py
```

#### 4. 验证结果

```bash
psql "$SUPABASE_DATABASE_URL" -f scripts/check_measures.sql
```

#### 5. 清理缓存

```bash
redis-cli FLUSHDB
```

#### 6. 重启服务

```bash
systemctl restart vibemix-backend
# 或
pm2 restart vibemix-backend
```

### 📊 预期影响

- **数据库**: 增加约 4 个字段，预计额外存储 < 1MB
- **查询性能**: 无明显影响（已加索引）
- **API 响应**: 每个原料多返回 ~50 bytes
- **用户体验**: ✨ 显著提升（ml 单位更直观）

### 🧪 测试覆盖

- ✅ 单位换算逻辑（24个测试用例）
- ✅ 分数解析（"1 1/2", "1/2"）
- ✅ 描述性关键词映射
- ✅ 边缘情况处理
- ✅ 数据库批量更新

### 📝 后续优化计划

- [ ] 用户偏好设置（支持 ml/oz 切换）
- [ ] 家用工具替代建议（"约3汤匙"）
- [ ] 配比可视化图表
- [ ] 批量换算计算器

---

**变更类型**: Feature (功能增强)  
**影响范围**: Backend, Database  
**向后兼容**: ✅ 是  
**需要迁移**: ✅ 是  
**测试状态**: ✅ 通过
