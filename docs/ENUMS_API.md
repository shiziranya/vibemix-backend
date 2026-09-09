# 枚举值 API 文档

## 概述

提供鸡尾酒推荐系统中所有枚举值的中英文映射，方便前端使用。

## 基础信息

- **基础路径**: `/api/enums`
- **认证**: 不需要
- **响应格式**: JSON

---

## API 端点

### 1️⃣ 获取所有枚举值（推荐）

**端点**: `GET /api/enums/all`

**描述**: 一次性获取所有枚举值，减少请求次数，推荐前端初始化时使用。

**响应示例**:
```json
{
  "code": 200,
  "message": "success",
  "data": {
    "flavor_tags": [
      { "value": "sweet", "label": "甜" },
      { "value": "sour", "label": "酸" },
      { "value": "bitter", "label": "苦" }
    ],
    "mood_tags": [
      { "value": "romantic", "label": "浪漫" },
      { "value": "elegant", "label": "优雅" }
    ],
    "glass_types": [
      { "value": "cocktail glass", "label": "鸡尾酒杯" },
      { "value": "old fashioned", "label": "古典杯" }
    ],
    "abv_levels": [
      { "value": "low", "label": "低度" },
      { "value": "medium", "label": "中度" }
    ],
    "recipe_types": [
      { "value": "classic", "label": "经典" },
      { "value": "original", "label": "原创" }
    ],
    "categories": [
      { "value": "Classic", "label": "经典款" },
      { "value": "Craft", "label": "手工精调" }
    ]
  }
}
```

---

### 2️⃣ 获取口味标签

**端点**: `GET /api/enums/flavor-tags`

**描述**: 获取所有口味标签（用于推荐接口的 `flavor_tags` 参数）

**返回值**: 17个口味标签
- sweet (甜)
- sour (酸)
- bitter (苦)
- spicy (辛辣)
- fruity (果香)
- creamy (奶油)
- citrus (柑橘)
- dry (干爽)
- earthy (泥土气息)
- floral (花香)
- herbal (草本)
- nutty (坚果)
- refreshing (清爽)
- rich (浓郁)
- savory (咸鲜)
- smoky (烟熏)
- tropical (热带)

**响应示例**:
```json
{
  "code": 200,
  "message": "success",
  "data": {
    "tags": [
      { "value": "sweet", "label": "甜" },
      { "value": "sour", "label": "酸" }
    ]
  }
}
```

---

### 3️⃣ 获取心情标签

**端点**: `GET /api/enums/mood-tags`

**描述**: 获取所有心情标签（用于配方的 `mood_tags` 字段）

**返回值**: 18个心情标签
- romantic (浪漫)
- elegant (优雅)
- refreshing (清爽)
- relaxing (放松)
- mysterious (神秘)
- energetic (活力)
- sophisticated (精致)
- casual (随性)
- cozy (温馨)
- adventurous (冒险)
- nostalgic (怀旧)
- playful (俏皮)
- bold (大胆)
- mellow (柔和)
- festive (欢庆)
- contemplative (沉思)
- sensual (感性)
- vibrant (活泼)

---

### 4️⃣ 获取常用杯型

**端点**: `GET /api/enums/glass-types`

**描述**: 获取常用杯型列表（精选版本，适合下拉选择）

**返回值**: 精选的常用杯型
- cocktail glass (鸡尾酒杯)
- old fashioned (古典杯)
- highball (高球杯)
- collins (可林杯)
- martini (马天尼杯)
- coupe (碟形杯)
- nick & nora (尼克诺拉杯)
- margarita glass (玛格丽塔杯)
- hurricane (飓风杯)
- tiki (提基杯)
- champagne flute (香槟笛杯)
- wine glass (葡萄酒杯)
- snifter (球形杯)
- shot (子弹杯)
- copper mug (铜杯)
- irish coffee (爱尔兰咖啡杯)
- pint (品脱杯)

---

### 5️⃣ 获取所有杯型（完整版）

**端点**: `GET /api/enums/glass-types/all`

**描述**: 获取所有杯型的去重列表（包括所有变体的映射）

**说明**: 数据库中有多种英文名称对应同一个中文名的情况（如 "Old Fashioned Glass"、"Rocks Glass" 都对应 "古典杯"），此接口返回去重后的完整列表。

---

### 6️⃣ 获取酒精度级别

**端点**: `GET /api/enums/abv-levels`

**描述**: 获取所有酒精度级别（用于推荐接口的 `abv_pref` 参数）

**返回值**:
- non-alcoholic (无酒精)
- low (低度)
- medium (中度)
- high (高度)
- any (任意)

---

### 7️⃣ 获取配方类型

**端点**: `GET /api/enums/recipe-types`

**描述**: 获取所有配方类型（用于推荐接口的 `recipe_type` 参数）

**返回值**:
- classic (经典) - 严格按照数据库配方
- original (原创) - AI可以调整配方

---

### 8️⃣ 获取鸡尾酒分类

**端点**: `GET /api/enums/categories`

**描述**: 获取所有鸡尾酒分类（用于推荐接口的 `category` 参数）

**返回值**:
- Classic (经典款)
- Craft (手工精调)
- Shot (短饮)
- Other (其他)

---

## 前端使用示例

### React / TypeScript

```typescript
import { useEffect, useState } from 'react';

interface EnumOption {
  value: string;
  label: string;
}

interface AllEnums {
  flavor_tags: EnumOption[];
  mood_tags: EnumOption[];
  glass_types: EnumOption[];
  abv_levels: EnumOption[];
  recipe_types: EnumOption[];
  categories: EnumOption[];
}

// 1. 在应用初始化时获取所有枚举值
export function useEnums() {
  const [enums, setEnums] = useState<AllEnums | null>(null);
  
  useEffect(() => {
    fetch('/api/enums/all')
      .then(res => res.json())
      .then(data => setEnums(data.data));
  }, []);
  
  return enums;
}

// 2. 创建翻译映射
export function createTranslator(options: EnumOption[]) {
  return Object.fromEntries(options.map(opt => [opt.value, opt.label]));
}

// 3. 使用示例
function App() {
  const enums = useEnums();
  
  if (!enums) return <div>Loading...</div>;
  
  // 创建翻译器
  const translateFlavor = createTranslator(enums.flavor_tags);
  const translateMood = createTranslator(enums.mood_tags);
  const translateGlass = createTranslator(enums.glass_types);
  
  return (
    <div>
      <Select placeholder="选择口味">
        {enums.flavor_tags.map(tag => (
          <Option key={tag.value} value={tag.value}>
            {tag.label}
          </Option>
        ))}
      </Select>
      
      {/* 显示时使用翻译器 */}
      <div>
        口味: {translateFlavor['sweet']} {/* 显示: 甜 */}
      </div>
    </div>
  );
}
```

### JavaScript

```javascript
// 1. 获取所有枚举值
async function loadEnums() {
  const response = await fetch('/api/enums/all');
  const { data } = await response.json();
  
  // 存储到全局或状态管理中
  window.APP_ENUMS = data;
  
  return data;
}

// 2. 创建翻译函数
function createTranslator(enumOptions) {
  const map = {};
  enumOptions.forEach(opt => {
    map[opt.value] = opt.label;
  });
  return (value) => map[value] || value;
}

// 3. 使用示例
const enums = await loadEnums();
const translateFlavor = createTranslator(enums.flavor_tags);

console.log(translateFlavor('sweet'));  // "甜"
console.log(translateFlavor('bitter')); // "苦"
```

---

## 工具函数（Python 后端）

如果在 Python 后端需要翻译枚举值：

```python
from app.utils.enums import (
    translate_flavor_tags,
    translate_mood_tags,
    translate_glass_type,
    translate_abv_level,
    translate_recipe_type,
    translate_category,
)

# 翻译口味标签列表
flavor_tags_zh = translate_flavor_tags(['sweet', 'sour'])
# 返回: ['甜', '酸']

# 翻译杯型
glass_zh = translate_glass_type('cocktail glass')
# 返回: '鸡尾酒杯'

# 翻译酒精度
abv_zh = translate_abv_level('medium')
# 返回: '中度'
```

---

## 测试

运行测试脚本：

```bash
cd /opt/vibemix/vibemix-backend
python3 test_enums_api.py
```

或者手动测试：

```bash
curl http://localhost:5005/api/enums/all | jq
```

---

## 注意事项

1. **所有枚举值 API 不需要认证**，可以直接访问
2. **推荐使用 `/api/enums/all`** 一次性获取所有枚举值，减少网络请求
3. **枚举值相对稳定**，可以在前端做缓存（例如 localStorage）
4. 如需添加新的枚举值，修改 `/app/utils/enums.py` 文件
5. Glass types 有两个版本：
   - `/glass-types` - 精选常用杯型（推荐用于用户选择）
   - `/glass-types/all` - 完整杯型列表（用于显示/翻译）
