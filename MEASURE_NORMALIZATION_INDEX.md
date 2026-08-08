# 用量规范化 - 文档索引

本目录包含用量规范化功能的完整文档和工具。根据你的角色选择对应的文档：

---

## 👨‍💻 前端开发者

### 🚀 快速开始

**第一步**: 阅读 [前端速查手册](./API_用量规范化_前端速查.md)  
**用时**: 3 分钟  
**内容**: 快速接入代码示例、常见场景、组件模板

### 📖 详细文档

**完整 API 文档**: [API_用量规范化更新.md](./API_用量规范化更新.md)  
**内容**: 
- 新增字段说明
- 所有受影响的接口
- 完整请求/响应示例
- 单位换算对照表
- 常见问题解答

### 📚 相关接口文档

- [地图探索 API (v1.6)](./地图探索api.md) - 已更新原料字段说明
- [推荐功能 API (v1.1)](../API_我的卡片和推荐.md) - 已更新原料字段说明

---

## 👨‍💼 后端开发者

### ⚡ 快速实施

**快速指南**: [MEASURE_NORMALIZATION_QUICKSTART.md](./MEASURE_NORMALIZATION_QUICKSTART.md)  
**用时**: 10 分钟  
**步骤**: 
1. 执行数据库迁移
2. 运行测试脚本
3. 批量规范化数据

### 📘 技术文档

**完整技术文档**: [docs/measure_normalization.md](./docs/measure_normalization.md)  
**内容**:
- 设计方案和架构
- 单位换算规则详解
- 实施步骤指南
- 数据库结构说明
- 前端显示策略
- 常见问题和排错

**实施总结**: [MEASURE_NORMALIZATION_SUMMARY.md](./MEASURE_NORMALIZATION_SUMMARY.md)  
**内容**:
- 交付内容清单
- 核心特性说明
- API 响应对比
- 使用流程
- 回退方案

**变更日志**: [CHANGELOG_measure_normalization.md](./CHANGELOG_measure_normalization.md)  
**内容**:
- 数据库变更
- API 变更
- 服务层更新
- 部署步骤

---

## 🔧 工具和脚本

### 数据库相关

| 文件 | 说明 | 用法 |
|------|------|------|
| `migrations/010_add_measure_normalized_fields.sql` | 数据库迁移脚本 | `psql "$SUPABASE_DATABASE_URL" -f migrations/010_add_measure_normalized_fields.sql` |
| `scripts/normalize_measures.py` | 批量规范化脚本 | `python3 scripts/normalize_measures.py` |
| `scripts/check_measures.sql` | 数据审计脚本 | `psql "$SUPABASE_DATABASE_URL" -f scripts/check_measures.sql` |

### 测试工具

| 文件 | 说明 | 用法 |
|------|------|------|
| `scripts/test_normalize.py` | 单元测试脚本（24个测试用例） | `python3 scripts/test_normalize.py` |

---

## 📊 文档结构

```
vibemix-backend/
├── API_用量规范化更新.md              # API变更文档（前端必读）
├── API_用量规范化_前端速查.md         # 前端速查手册
├── MEASURE_NORMALIZATION_INDEX.md     # 本文件（文档索引）
├── MEASURE_NORMALIZATION_QUICKSTART.md # 后端快速指南
├── MEASURE_NORMALIZATION_SUMMARY.md   # 实施总结
├── CHANGELOG_measure_normalization.md # 完整变更日志
├── docs/
│   └── measure_normalization.md       # 完整技术文档
├── migrations/
│   └── 010_add_measure_normalized_fields.sql  # 数据库迁移
├── scripts/
│   ├── normalize_measures.py          # 规范化脚本
│   ├── test_normalize.py              # 测试脚本
│   └── check_measures.sql             # 审计脚本
└── app/services/
    ├── cocktail_service.py            # 已更新
    ├── map_service.py                 # 已更新
    └── recommend_service.py           # 已更新
```

---

## 🎯 角色导航

### 我是前端开发，要接入新字段

1. ✅ 阅读 [前端速查手册](./API_用量规范化_前端速查.md) (3分钟)
2. ✅ 查看 [API 完整文档](./API_用量规范化更新.md) 了解细节
3. ✅ 开始开发！最简单的改动：`measure_raw` → `measure`

### 我是后端开发，要执行迁移

1. ✅ 阅读 [快速指南](./MEASURE_NORMALIZATION_QUICKSTART.md) (5分钟)
2. ✅ 执行 3 步部署流程
3. ✅ 如需深入了解，阅读 [完整技术文档](./docs/measure_normalization.md)

### 我是产品经理，要了解改动

1. ✅ 阅读 [实施总结](./MEASURE_NORMALIZATION_SUMMARY.md) 了解核心特性
2. ✅ 查看 [变更日志](./CHANGELOG_measure_normalization.md) 了解影响范围
3. ✅ 参考 [API 文档](./API_用量规范化更新.md) 中的示例了解最终效果

### 我是测试工程师，要验证功能

1. ✅ 运行 `python3 scripts/test_normalize.py` 验证换算逻辑
2. ✅ 运行 `psql ... -f scripts/check_measures.sql` 审计数据
3. ✅ 参考 [API 文档](./API_用量规范化更新.md) 中的响应示例进行接口测试

---

## 🔍 快速查找

### 常见问题

| 问题 | 查看文档 | 章节 |
|------|---------|------|
| 如何快速接入？ | [前端速查](./API_用量规范化_前端速查.md) | 快速开始 |
| 有哪些接口变更？ | [API 文档](./API_用量规范化更新.md) | 第 4 章 |
| oz 换算成多少 ml？ | [API 文档](./API_用量规范化更新.md) | 附录 |
| 如何执行部署？ | [快速指南](./MEASURE_NORMALIZATION_QUICKSTART.md) | 全文 |
| 如何回退？ | [实施总结](./MEASURE_NORMALIZATION_SUMMARY.md) | 回退方案 |
| 为什么用 1:30 而不是 29.57？ | [技术文档](./docs/measure_normalization.md) | 常见问题 |
| 如何计算总容量？ | [前端速查](./API_用量规范化_前端速查.md) | 场景 3 |
| 数据库字段说明？ | [技术文档](./docs/measure_normalization.md) | 数据库结构 |

### 代码示例

| 需求 | 查看文档 | 位置 |
|------|---------|------|
| 显示原料列表 | [前端速查](./API_用量规范化_前端速查.md) | 场景 1 |
| 添加"约"标记 | [前端速查](./API_用量规范化_前端速查.md) | 场景 2 |
| 计算总容量 | [前端速查](./API_用量规范化_前端速查.md) | 场景 3 |
| 配方倍数调整 | [前端速查](./API_用量规范化_前端速查.md) | 场景 4 |
| 完整组件示例 | [前端速查](./API_用量规范化_前端速查.md) | 最后一节 |
| 响应示例 | [API 文档](./API_用量规范化更新.md) | 第 6 章 |

---

## 📞 获取帮助

- 🐛 发现 Bug？请联系后端团队
- 💡 有建议？欢迎提出改进意见
- ❓ 文档不清楚？请告诉我们需要补充的内容

---

**文档版本**: v1.0  
**最后更新**: 2026-07-19  
**维护者**: 后端团队
