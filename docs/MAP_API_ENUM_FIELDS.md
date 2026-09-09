# 地图节点 API 枚举字段映射文档

## 📋 概述

地图节点 API 现在**同时返回英文和中文枚举字段**，与推荐 API 保持一致。

---

## 🎯 受影响的 API 端点

### 1. 获取节点详情
**端点**: `GET /api/v1/map/nodes/<node_id>`

返回单个节点的完整信息，包括配方详情、配料列表等。

---

## 📦 返回字段示例

### 完整返回结构

```json
{
  "code": 200,
  "message": "success",
  "data": {
    "node": {
      "id": 432,
      "theme_id": 13,
      "cocktail_id": 229,
      "node_key": "long_island_iced_tea",
      "is_entry_node": true,
      "is_boss": false,
      "reward_xp": 50
    },
    "cocktail": {
      "id": 229,
      "name": "Long Island Iced Tea",
      "name_zh": "长岛冰茶",
      
      // ── 枚举字段：酒精度 ──
      "abv_level": "high",           // 英文（用于逻辑）
      "abv_level_zh": "高度",        // 中文（用于显示）
      
      // ── 枚举字段：杯型 ──
      "glass_type": "Highball glass",
      "glass_type_zh": "高球杯",
      
      // ── 枚举字段：口味标签 ──
      "flavor_tags": [
        "sweet",
        "citrus",
        "refreshing"
      ],
      "flavor_tags_zh": [
        "甜",
        "柑橘",
        "清爽"
      ],
      
      // ── 枚举字段：心情标签 ──
      "mood_tags": [],
      "mood_tags_zh": [],
      
      // ── 其他字段 ──
      "difficulty": 3,
      "complexity": 4,
      "image_url": "http://...",
      "story_zh": "配方故事...",
      "instructions_zh": "制作说明...",
      "preparation_steps": [
        {
          "order": 1,
          "text": "在高球杯中加入冰块",
          "duration_hint": null
        }
      ],
      "technique_primary": "build",
      "cultural_icon": ["美国"],
      "gateway_spirit": "vodka",
      "prep_time_minutes": 5,
      "calories": 220
    },
    "ingredients": [
      {
        "sort_order": 1,
        "name": "Vodka",
        "name_zh": "伏特加",
        "measure": "15ml",
        "measure_ml": 15.0,
        "family_id": 1,
        "family_name_zh": "伏特加",
        "is_base_spirit": true,
        "in_cabinet": true
      }
    ],
    "required_spirits": [
      {
        "id": 1,
        "name": "Vodka",
        "name_zh": "伏特加",
        "base_spirit_family": "vodka",
        "in_cabinet": true
      }
    ],
    "can_complete": true,
    "missing_ingredients": []
  }
}
```

---

## 📊 枚举字段对照表

| 字段名称     | 英文字段      | 中文字段        | 值类型 | 示例                           |
|--------------|---------------|-----------------|--------|--------------------------------|
| 酒精度级别   | `abv_level`   | `abv_level_zh`  | string | `"high"` → `"高度"`            |
| 杯型         | `glass_type`  | `glass_type_zh` | string | `"Highball glass"` → `"高球杯"` |
| 口味标签     | `flavor_tags` | `flavor_tags_zh`| array  | `["sweet"]` → `["甜"]`         |
| 心情标签     | `mood_tags`   | `mood_tags_zh`  | array  | `["romantic"]` → `["浪漫"]`    |

---

## 💻 前端使用示例

### React / TypeScript

```typescript
interface MapNodeDetail {
  node: {
    id: number;
    theme_id: number;
    cocktail_id: number;
    reward_xp: number;
  };
  cocktail: {
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
    
    difficulty: number;
    image_url: string;
  };
  ingredients: Array<{
    name_zh: string;
    measure: string;
    in_cabinet: boolean;
  }>;
  can_complete: boolean;
}

function NodeDetailCard({ nodeId }: { nodeId: number }) {
  const [data, setData] = useState<MapNodeDetail | null>(null);
  
  useEffect(() => {
    fetch(`/api/v1/map/nodes/${nodeId}`, {
      headers: { Authorization: `Bearer ${token}` }
    })
      .then(res => res.json())
      .then(result => setData(result.data));
  }, [nodeId]);
  
  if (!data) return <div>Loading...</div>;
  
  const { cocktail } = data;
  
  return (
    <div className="node-detail">
      {/* ✅ 显示用中文 */}
      <h2>{cocktail.name_zh}</h2>
      
      <div className="info">
        <span>酒精度: {cocktail.abv_level_zh}</span>
        <span>杯型: {cocktail.glass_type_zh}</span>
        <span>难度: {cocktail.difficulty}/5</span>
      </div>
      
      <div className="tags">
        {cocktail.flavor_tags_zh.map(tag => (
          <Tag key={tag}>{tag}</Tag>
        ))}
      </div>
      
      {/* ✅ 逻辑判断用英文 */}
      {cocktail.abv_level === 'high' && (
        <Alert type="warning">
          高度酒精，请适量饮用
        </Alert>
      )}
      
      {data.can_complete && (
        <Button onClick={handleComplete}>
          完成此节点
        </Button>
      )}
    </div>
  );
}
```

### JavaScript

```javascript
// 获取节点详情
async function loadNodeDetail(nodeId) {
  const response = await fetch(`/api/v1/map/nodes/${nodeId}`, {
    headers: { Authorization: `Bearer ${token}` }
  });
  
  const { data } = await response.json();
  const { cocktail } = data;
  
  // ✅ 显示用中文字段
  document.getElementById('name').textContent = cocktail.name_zh;
  document.getElementById('abv').textContent = cocktail.abv_level_zh;
  document.getElementById('glass').textContent = cocktail.glass_type_zh;
  
  // 渲染口味标签（中文）
  const tagsHTML = cocktail.flavor_tags_zh
    .map(tag => `<span class="tag">${tag}</span>`)
    .join('');
  document.getElementById('flavor-tags').innerHTML = tagsHTML;
  
  // ✅ 逻辑判断用英文字段
  if (cocktail.abv_level === 'high') {
    showWarningBadge('高度酒精');
  }
  
  // 检查是否包含特定口味
  const hasCitrus = cocktail.flavor_tags.includes('citrus');
  const hasSweet = cocktail.flavor_tags.includes('sweet');
  
  return data;
}

// 完成节点
async function completeNode(nodeId) {
  const response = await fetch(`/api/v1/map/nodes/${nodeId}/complete`, {
    method: 'POST',
    headers: { 
      'Authorization': `Bearer ${token}`,
      'Content-Type': 'application/json'
    }
  });
  
  return response.json();
}
```

### Vue 3

```vue
<template>
  <div class="node-detail" v-if="nodeData">
    <!-- 显示用中文 -->
    <h2>{{ cocktail.name_zh }}</h2>
    
    <div class="stats">
      <div class="stat">
        <label>酒精度</label>
        <span>{{ cocktail.abv_level_zh }}</span>
      </div>
      <div class="stat">
        <label>杯型</label>
        <span>{{ cocktail.glass_type_zh }}</span>
      </div>
      <div class="stat">
        <label>难度</label>
        <span>{{ cocktail.difficulty }}/5</span>
      </div>
    </div>
    
    <div class="flavor-tags">
      <span 
        v-for="tag in cocktail.flavor_tags_zh" 
        :key="tag"
        class="tag"
      >
        {{ tag }}
      </span>
    </div>
    
    <!-- 逻辑判断用英文 -->
    <Alert v-if="isHighAlcohol" type="warning">
      高度酒精，请适量饮用
    </Alert>
    
    <Button 
      v-if="nodeData.can_complete"
      @click="handleComplete"
    >
      完成此节点（+{{ nodeData.node.reward_xp }} XP）
    </Button>
  </div>
</template>

<script setup>
import { ref, computed, onMounted } from 'vue';

const props = defineProps({
  nodeId: Number
});

const nodeData = ref(null);

const cocktail = computed(() => nodeData.value?.cocktail || {});

// 逻辑判断用英文字段
const isHighAlcohol = computed(() => {
  return cocktail.value.abv_level === 'high';
});

const loadNodeDetail = async () => {
  const response = await fetch(`/api/v1/map/nodes/${props.nodeId}`, {
    headers: { Authorization: `Bearer ${token}` }
  });
  const result = await response.json();
  nodeData.value = result.data;
};

const handleComplete = async () => {
  await fetch(`/api/v1/map/nodes/${props.nodeId}/complete`, {
    method: 'POST',
    headers: { 
      Authorization: `Bearer ${token}`,
      'Content-Type': 'application/json'
    }
  });
  // 刷新数据
  await loadNodeDetail();
};

onMounted(loadNodeDetail);
</script>
```

---

## 🎯 最佳实践

### 1. **显示优先使用中文字段**
```javascript
// ✅ 推荐
<span>{cocktail.abv_level_zh}</span>
<span>{cocktail.glass_type_zh}</span>
{cocktail.flavor_tags_zh.map(tag => <Tag>{tag}</Tag>)}

// ❌ 不推荐
<span>{translateAbv(cocktail.abv_level)}</span>
```

### 2. **逻辑判断优先使用英文字段**
```javascript
// ✅ 推荐（清晰、稳定）
if (cocktail.abv_level === 'high') { ... }
if (cocktail.flavor_tags.includes('sweet')) { ... }

// ❌ 不推荐
if (cocktail.abv_level_zh === '高度') { ... }
```

### 3. **数据过滤/搜索用英文字段**
```javascript
// ✅ 推荐
const sweetCocktails = nodes.filter(node => 
  node.cocktail.flavor_tags.includes('sweet')
);

const highAbvNodes = nodes.filter(node => 
  node.cocktail.abv_level === 'high'
);
```

### 4. **警告提示基于英文值判断**
```javascript
// ✅ 推荐
function getCocktailWarnings(cocktail) {
  const warnings = [];
  
  if (cocktail.abv_level === 'high') {
    warnings.push('高度酒精，请适量饮用');
  }
  
  if (cocktail.difficulty >= 4) {
    warnings.push('复杂配方，建议有经验后尝试');
  }
  
  return warnings;
}
```

---

## 📝 相关 API

| 端点 | 说明 | 枚举字段映射 |
|------|------|-------------|
| `GET /api/v1/map/nodes/<node_id>` | 获取节点详情 | ✅ 已支持 |
| `GET /api/v1/map/themes/<theme_id>` | 获取主题图谱 | ❌ 无枚举字段 |
| `POST /api/v1/map/nodes/<node_id>/complete` | 完成节点 | ✅ 返回包含映射 |
| `GET /api/v1/map/user/stats` | 用户统计 | ❌ 无枚举字段 |
| `GET /api/enums/all` | 获取所有枚举值 | - |
| `POST /api/recommend` | 推荐配方 | ✅ 已支持 |

---

## 🔄 与推荐 API 的一致性

地图节点 API 和推荐 API 现在使用**相同的字段命名规范**：

| 特性 | 地图节点 API | 推荐 API |
|------|-------------|----------|
| 返回英文字段 | ✅ | ✅ |
| 返回中文字段 | ✅ | ✅ |
| 字段命名规范 | `*_zh` | `*_zh` |
| 支持的枚举 | abv, glass, flavor, mood | abv, glass, flavor, mood |

---

## ✅ 测试示例

```bash
# 获取节点详情
curl -H "Authorization: Bearer YOUR_TOKEN" \
  http://localhost:5005/api/v1/map/nodes/432 | jq '.data.cocktail | {
    abv: .abv_level,
    abv_zh: .abv_level_zh,
    glass: .glass_type,
    glass_zh: .glass_type_zh,
    flavors: .flavor_tags,
    flavors_zh: .flavor_tags_zh
  }'
```

**预期输出**:
```json
{
  "abv": "high",
  "abv_zh": "高度",
  "glass": "Highball glass",
  "glass_zh": "高球杯",
  "flavors": ["sweet", "citrus", "refreshing"],
  "flavors_zh": ["甜", "柑橘", "清爽"]
}
```

---

## 📚 完整文档

- `/docs/RECOMMEND_API_FIELDS.md` - 推荐 API 完整字段文档
- `/docs/ENUMS_API.md` - 枚举值 API 文档
- 本文档 - 地图节点 API 枚举字段映射

---

更新时间: 2026-09-06
