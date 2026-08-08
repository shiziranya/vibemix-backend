# 用量规范化快速开始指南

## ⚡ 快速实施（3步完成）

### 步骤 1: 数据库迁移（添加新字段）

```bash
cd /opt/vibemix/vibemix-backend

# 使用 psql 执行迁移
psql "$SUPABASE_DATABASE_URL" -f migrations/010_add_measure_normalized_fields.sql
```

### 步骤 2: 测试规范化逻辑（可选）

```bash
# 运行测试验证逻辑正确性
python3 scripts/test_normalize.py
```

预期看到：
```
✅ PASS  '1 oz'
       期望: 30ml (value=30.0, unit=ml, type=precise)
       实际: 30ml (value=30.0, unit=ml, type=precise)

✅ PASS  '2 dashes'
       期望: 2滴 (value=2.0, unit=滴, type=approximate)
       实际: 2滴 (value=2.0, unit=滴, type=approximate)

...

测试结果: 24 通过, 0 失败
```

### 步骤 3: 执行批量规范化

```bash
# 规范化所有现有数据
python3 scripts/normalize_measures.py
```

完成！现在所有 API 都会返回规范化的用量数据。

## 📋 核心换算规则

| 原单位 | 换算为 | 说明 |
|--------|--------|------|
| **1 oz** | **30ml** | 简化整数换算 |
| 1 cl | 10ml | 厘升 → 毫升 |
| 1 tsp | 5ml | 茶匙 |
| 1 tbsp | 15ml | 汤匙 |
| **dash** | **保留 "滴"** | 不换算，标记为约量 |
| **barspoon** | **保留** | 不换算 |

## 🔍 验证结果

```sql
-- 查看规范化后的数据
SELECT 
    measure_raw,
    measure_normalized AS "规范化用量",
    measure_type AS "类型"
FROM cocktail_ingredients
WHERE measure_raw LIKE '%oz%'
LIMIT 10;
```

示例输出：
```
 measure_raw | 规范化用量 | 类型
-------------+-----------+----------
 1 oz        | 30ml      | precise
 1 1/2 oz    | 45ml      | precise
 2 oz        | 60ml      | precise
```

## 📱 前端展示

新增的 `measure` 字段会自动返回规范化的中文用量：

```json
{
  "name_zh": "金酒",
  "measure_raw": "1 1/2 oz",
  "measure": "45ml",        // 👈 新字段，优先使用
  "measure_type": "precise"
}
```

前端只需显示 `measure` 字段即可，降级逻辑已在后端处理。

## ⚠️ 注意事项

1. ✅ **原始数据已保留**：`measure_raw` 不会被修改
2. ✅ **可重复运行**：规范化脚本支持多次执行
3. ⚠️ **人工审核**：执行后检查 `measure_type = 'unclear'` 的记录

## 📚 完整文档

详细说明请查看：`docs/measure_normalization.md`

## 🐛 问题排查

### 问题：规范化脚本报错找不到模块

```bash
# 确保在正确的目录
cd /opt/vibemix/vibemix-backend

# 检查 Python 路径
python3 -c "import sys; print('\n'.join(sys.path))"

# 安装依赖
pip install sqlalchemy psycopg2-binary
```

### 问题：数据库连接失败

```bash
# 检查环境变量
echo $SUPABASE_DATABASE_URL

# 或者在 .env 文件中设置
cat .env | grep SUPABASE_DATABASE_URL
```

### 问题：部分记录显示 "unclear"

这是正常的，表示需要人工审核。通常是：
- 只有数字没有单位（如 "1/2"）
- 无法解析的特殊格式

使用 SQL 手动修正：
```sql
UPDATE cocktail_ingredients
SET 
    measure_normalized = '半个',
    measure_type = 'precise'
WHERE id = <记录ID>;
```

## 📞 获取帮助

- 技术文档: `docs/measure_normalization.md`
- 测试脚本: `scripts/test_normalize.py`
- 迁移脚本: `migrations/010_add_measure_normalized_fields.sql`
