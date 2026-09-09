# 推荐 API 完整字段文档（含中文映射）

## 📋 完整返回字段

推荐 API (`POST /api/recommend` 和 `POST /api/recommend/refresh`) 现在**同时返回英文和中文字段**：

### 字段设计原则
- **英文字段**: 用于前端逻辑判断、条件过滤（如 `if (abv_level === 'high')`）
- **中文字段**: 用于界面展示，字段名添加 `_zh` 后缀

---

## 🔥 完整返回结构

```json
{
  "session_id": "sess_abc123",
  
  "cocktail": {
    // ── 基本信息 ──
    "id": 1001,
    "name": "Jammie Dodger Fizz",
    "name_zh": "果酱夹心饼干菲兹",
    "difficulty": 2,
    "image_url": "http://115.191.50.177:5005/static/cocktail/images/1001.jpg",
    
    // ── 枚举字段：酒精度 ──
    "abv_level": "medium",          // 英文值: low/medium/high/non-alcoholic
    "abv_level_zh": "中度",         // 中文值: 低度/中度/高度/无酒精
    
    // ── 枚举字段：杯型 ──
    "glass_type": "Collins",        // 英文值
    "glass_type_zh": "可林杯",      // 中文值
    
    // ── 枚举字段：口味标签 ──
    "flavor_tags": [                // 英文值数组
      "sweet",
      "creamy", 
      "nutty",
      "citrus"
    ],
    "flavor_tags_zh": [             // 中文值数组
      "甜",
      "奶油",
      "坚果",
      "柑橘"
    ],
    
    // ── 枚举字段：心情标签 ──
    "mood_tags": [],                // 英文值数组（当前数据库中为空）
    "mood_tags_zh": []              // 中文值数组
  },
  
  "ai": {
    "reason": "这款酒融合了金酒的清爽和玫瑰的优雅...",
    "poetic_copy": "优雅的玫瑰色调，伴随着清新的果香...",
    "mood_caption": "浪漫优雅",
    "tweaks": null                   // 原创模式下有值
  },
  
  "ingredients": [
    {
      "ingredient_family_id": 1,
      "ingredient_id": 10,
      "name": "Gin",
      "name_zh": "金酒",
      "measure": "45ml",
      "measure_raw": "45ml",
      "measure_ml": 45.0,
      "is_easily_available": false,
      "category": "spirits",
      "status": "owned",             // owned/available/missing
      "substitute": null
    }
  ],
  
  "steps": [
    {
      "order": 1,
      "text": "在调酒杯中加入冰块",
      "duration_hint": "10秒"
    }
  ]
}
```

---

## 📊 枚举字段对照表

| 字段名称     | 英文字段      | 中文字段        | 值类型 | 示例                        |
|--------------|---------------|-----------------|--------|------------------------------|
| 酒精度级别   | `abv_level`   | `abv_level_zh`  | string | `"medium"` → `"中度"`        |
| 杯型         | `glass_type`  | `glass_type_zh` | string | `"Collins"` → `"可林杯"`     |
| 口味标签     | `flavor_tags` | `flavor_tags_zh`| array  | `["sweet"]` → `["甜"]`       |
| 心情标签     | `mood_tags`   | `mood_tags_zh`  | array  | `["romantic"]` → `["浪漫"]`  |

---

## 💻 前端使用示例

### React / TypeScript

```typescript
interface CocktailData {
  id: number;
  name: string;
  name_zh: string;
  
  // 英文字段（用于逻辑）
  abv_level: 'low' | 'medium' | 'high' | 'non-alcoholic';
  glass_type: string;
  flavor_tags: string[];
  mood_tags: string[];
  
  // 中文字段（用于显示）
  abv_level_zh: string;
  glass_type_zh: string;
  flavor_tags_zh: string[];
  mood_tags_zh: string[];
}

function CocktailCard({ cocktail }: { cocktail: CocktailData }) {
  return (
    <div>
      {/* ✅ 显示用中文 */}
      <h3>{cocktail.name_zh}</h3>
      <p>酒精度: {cocktail.abv_level_zh}</p>
      <p>杯型: {cocktail.glass_type_zh}</p>
      
      <div className="tags">
        {cocktail.flavor_tags_zh.map(tag => (
          <Tag key={tag}>{tag}</Tag>
        ))}
      </div>
      
      {/* ✅ 逻辑判断用英文 */}
      {cocktail.abv_level === 'high' && (
        <Warning>高度酒精，请适量饮用</Warning>
      )}
      
      {cocktail.flavor_tags.includes('sweet') && (
        <Badge>甜味</Badge>
      )}
    </div>
  );
}
```

### JavaScript

```javascript
// 获取推荐
const response = await fetch('/api/recommend', {
  method: 'POST',
  headers: { 'Content-Type': 'application/json' },
  body: JSON.stringify({
    flavor_tags: ['sweet', 'fruity'],  // 请求参数用英文
    abv_pref: 'medium',
    recipe_type: 'classic'
  })
});

const { data } = await response.json();
const { cocktail } = data;

// ✅ 显示用中文字段
document.getElementById('abv').textContent = cocktail.abv_level_zh;
document.getElementById('glass').textContent = cocktail.glass_type_zh;

// 渲染口味标签（中文）
const tagsHTML = cocktail.flavor_tags_zh
  .map(tag => `<span class="tag">${tag}</span>`)
  .join('');
document.getElementById('tags').innerHTML = tagsHTML;

// ✅ 逻辑判断用英文字段
if (cocktail.abv_level === 'high') {
  showWarning('高度酒精');
}

// 过滤包含特定口味的配方
const hasSweet = cocktail.flavor_tags.includes('sweet');
const hasSour = cocktail.flavor_tags.includes('sour');
```

### Vue 3

```vue
<template>
  <div class="cocktail-card">
    <!-- 显示用中文 -->
    <h3>{{ cocktail.name_zh }}</h3>
    
    <div class="info">
      <span>酒精度: {{ cocktail.abv_level_zh }}</span>
      <span>杯型: {{ cocktail.glass_type_zh }}</span>
    </div>
    
    <div class="tags">
      <span 
        v-for="tag in cocktail.flavor_tags_zh" 
        :key="tag"
        class="tag"
      >
        {{ tag }}
      </span>
    </div>
    
    <!-- 逻辑判断用英文 -->
    <div v-if="isHighAlcohol" class="warning">
      高度酒精，请适量饮用
    </div>
  </div>
</template>

<script setup>
import { computed } from 'vue';

const props = defineProps({
  cocktail: Object
});

// 逻辑判断用英文字段
const isHighAlcohol = computed(() => {
  return props.cocktail.abv_level === 'high';
});
</script>
```

---

## 🎯 最佳实践

### 1. **显示优先使用中文字段**
```javascript
// ✅ 推荐
<span>{cocktail.abv_level_zh}</span>
<span>{cocktail.glass_type_zh}</span>

// ❌ 不推荐（需要自己映射）
<span>{translateAbv(cocktail.abv_level)}</span>
```

### 2. **逻辑判断优先使用英文字段**
```javascript
// ✅ 推荐（清晰、稳定）
if (cocktail.abv_level === 'high') { ... }
if (cocktail.flavor_tags.includes('sweet')) { ... }

// ❌ 不推荐（容易出错）
if (cocktail.abv_level_zh === '高度') { ... }
```

### 3. **数据过滤/搜索用英文字段**
```javascript
// ✅ 推荐
const sweetCocktails = cocktails.filter(c => 
  c.flavor_tags.includes('sweet')
);

const highAbvCocktails = cocktails.filter(c => 
  c.abv_level === 'high'
);
```

### 4. **向后端发送参数用英文值**
```javascript
// ✅ 推荐
fetch('/api/recommend', {
  body: JSON.stringify({
    flavor_tags: ['sweet', 'sour'],  // 英文
    abv_pref: 'medium'               // 英文
  })
});
```

---

## 📝 枚举值完整列表

### 酒精度级别 (abv_level)
| 英文值         | 中文值   |
|----------------|----------|
| non-alcoholic  | 无酒精   |
| low            | 低度     |
| medium         | 中度     |
| high           | 高度     |

### 口味标签 (flavor_tags)
| 英文值      | 中文值   |
|-------------|----------|
| sweet       | 甜       |
| sour        | 酸       |
| bitter      | 苦       |
| spicy       | 辛辣     |
| fruity      | 果香     |
| creamy      | 奶油     |
| citrus      | 柑橘     |
| dry         | 干爽     |
| earthy      | 泥土气息 |
| floral      | 花香     |
| herbal      | 草本     |
| nutty       | 坚果     |
| refreshing  | 清爽     |
| rich        | 浓郁     |
| savory      | 咸鲜     |
| smoky       | 烟熏     |
| tropical    | 热带     |

### 常用杯型 (glass_type)
| 英文值           | 中文值       |
|------------------|--------------|
| cocktail glass   | 鸡尾酒杯     |
| old fashioned    | 古典杯       |
| highball         | 高球杯       |
| collins          | 可林杯       |
| martini          | 马天尼杯     |
| coupe            | 碟形杯       |
| nick & nora      | 尼克诺拉杯   |
| margarita glass  | 玛格丽塔杯   |
| hurricane        | 飓风杯       |
| shot             | 子弹杯       |
| copper mug       | 铜杯         |

完整列表请访问：`GET /api/enums/all`

---

## 🔗 相关 API

- `GET /api/enums/all` - 获取所有枚举值及中文映射
- `POST /api/recommend` - 推荐配方（含中文字段）
- `POST /api/recommend/refresh` - 换一杯（含中文字段）
- `GET /api/recommend/history` - 推荐历史

---

## ✅ 总结

1. **所有枚举字段都已完全映射为中文** ✓
2. **同时保留英文和中文字段**，满足不同场景需求 ✓
3. **命名规范统一**：中文字段 = 英文字段 + `_zh` 后缀 ✓
4. **向后兼容**：保留原有英文字段，不影响现有代码 ✓

---

更新时间: 2026-09-06
