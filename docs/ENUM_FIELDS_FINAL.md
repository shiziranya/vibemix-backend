# 枚举字段中文映射 - 最终版本

## 📋 返回字段说明

根据用户需求，**酒精度 (abv_level) 不进行中文翻译**，保持英文原值。

---

## ✅ 包含中文映射的字段

| 字段名称 | 英文字段 | 中文字段 | 说明 |
|---------|---------|---------|------|
| 杯型 | `glass_type` | `glass_type_zh` | ✅ 翻译为中文 |
| 口味标签 | `flavor_tags` | `flavor_tags_zh` | ✅ 翻译为中文 |
| 心情标签 | `mood_tags` | `mood_tags_zh` | ✅ 翻译为中文 |

---

## ❌ 不翻译的字段

| 字段名称 | 字段 | 原因 |
|---------|------|------|
| 酒精度级别 | `abv_level` | 保持英文原值 (low/medium/high/non-alcoholic) |

---

## 📦 API 返回示例

```json
{
  "cocktail": {
    "id": 1001,
    "name_zh": "果酱夹心饼干菲兹",
    
    // ❌ 酒精度：只有英文字段
    "abv_level": "medium",
    
    // ✅ 杯型：英文 + 中文
    "glass_type": "Collins",
    "glass_type_zh": "可林杯",
    
    // ✅ 口味标签：英文 + 中文
    "flavor_tags": ["sweet", "creamy", "nutty", "citrus"],
    "flavor_tags_zh": ["甜", "奶油", "坚果", "柑橘"],
    
    // ✅ 心情标签：英文 + 中文
    "mood_tags": [],
    "mood_tags_zh": []
  }
}
```

---

## 💻 前端使用示例

### 酒精度（使用英文值）

```javascript
const { cocktail } = data;

// ✅ 直接使用英文值
<div className="abv-badge">
  <span>{cocktail.abv_level}</span>
</div>

// ✅ 自定义显示
const abvDisplay = {
  'low': '低度',
  'medium': '中度',
  'high': '高度',
  'non-alcoholic': '无酒精'
};
<span>{abvDisplay[cocktail.abv_level]}</span>

// ✅ 逻辑判断
if (cocktail.abv_level === 'high') {
  showWarning('高度酒精，请适量饮用');
}
```

### 杯型和口味（使用中文字段）

```javascript
// ✅ 显示用中文
<span>杯型: {cocktail.glass_type_zh}</span>

<div className="tags">
  {cocktail.flavor_tags_zh.map(tag => (
    <Tag key={tag}>{tag}</Tag>
  ))}
</div>

// ✅ 逻辑判断用英文
if (cocktail.flavor_tags.includes('sweet')) {
  // ...
}
```

---

## 🔄 受影响的 API

所有返回配方信息的 API 都遵循此规范：

| API 端点 | 状态 |
|----------|------|
| `POST /api/recommend` | ✅ |
| `POST /api/recommend/refresh` | ✅ |
| `POST /api/recommend/stream` | ✅ |
| `GET /api/recommend/history` | ✅ |
| `GET /api/v1/map/nodes/<id>` | ✅ |
| `GET /api/cocktails/<id>` | ✅ |
| `GET /api/cocktails/search` | ✅ |
| `GET /api/menu/*` | ✅ |

---

## 🧪 测试结果

```bash
✅ 配方详情 API
  abv_level: medium (❌ 无 abv_level_zh)
  glass_type_zh: ✓ 可林杯
  flavor_tags_zh: ✓ ['甜', '奶油', '坚果', '柑橘']

✅ 配方搜索 API
  abv_level: high (❌ 无 abv_level_zh)
  glass_type_zh: ✓ 鸡尾酒杯

✅ 地图节点 API
  abv_level: high (❌ 无 abv_level_zh)
  glass_type_zh: ✓ 高球杯
```

---

## 📝 字段总结

### 返回的字段
- `abv_level` - 英文值（low/medium/high/non-alcoholic）
- `glass_type` + `glass_type_zh` - 英文 + 中文
- `flavor_tags` + `flavor_tags_zh` - 英文 + 中文数组
- `mood_tags` + `mood_tags_zh` - 英文 + 中文数组

### 不返回的字段
- ❌ `abv_level_zh` - 已移除

---

## 📚 相关文档

- `/docs/ENUMS_API.md` - 枚举值 API 文档
- `/docs/RECOMMEND_API_FIELDS.md` - 推荐 API 字段文档（需更新）
- `/docs/MAP_API_ENUM_FIELDS.md` - 地图 API 字段文档（需更新）
- 本文档 - 最终版本说明

---

更新时间: 2026-09-06 21:52  
版本: v2.0 - 移除 abv_level 翻译
