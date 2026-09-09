# API 变更文档：收藏功能关联推荐记录

## 📅 变更日期
2026-09-08

## 📋 变更概述
用户收藏鸡尾酒时，可以关联到 LLM 推荐记录。前端可以通过推荐 ID 查询完整的推荐详情（包含 AI 生成的理由、诗意描述等）。

**重要：`recommendation_id` 会在推荐接口的响应中自动返回，前端只需要保存并在收藏时传入即可。**

---

## 🔑 recommendation_id 的来源

### 1. SSE 流式推荐接口

```typescript
// POST /api/recommend/stream
const eventSource = new EventSource('/api/recommend/stream');

eventSource.addEventListener('message', (e) => {
    const data = JSON.parse(e.data);
    
    if (data.type === 'done') {
        // ✅ done 事件中包含 recommendation_id
        const recommendationId = data.recommendation_id;
        console.log('推荐ID:', recommendationId);
        
        // 保存到状态，供收藏时使用
        setRecommendationId(recommendationId);
    }
});
```

**SSE 事件流：**
```javascript
// 1. 会话ID
data: {"type":"session","session_id":"abc123"}

// 2. 第一批数据（鸡尾酒基本信息 + AI 文案）
data: {"type":"batch1","cocktail":{...},"ai":{...}}

// 3. 第二批数据（原料列表）
data: {"type":"batch2","ingredients":[...]}

// 4. 第三批数据（制作步骤）
data: {"type":"batch3","steps":[...]}

// 5. 完成 - 🆕 包含 recommendation_id
data: {"type":"done","recommendation_id":456}
```

### 2. 非流式推荐接口

```typescript
// POST /api/recommend
const response = await fetch('/api/recommend', {
    method: 'POST',
    body: JSON.stringify({
        mood_tags: ['relaxing'],
        abv_pref: 'medium'
    })
});

const { data } = await response.json();
// ✅ data 中包含 recommendation_id
console.log('推荐ID:', data.recommendation_id);
```

**响应示例：**
```json
{
    "code": 0,
    "data": {
        "session_id": "abc123",
        "recommendation_id": 456,  // 🆕 新增字段
        "cocktail": { /* ... */ },
        "ai": { /* ... */ },
        "ingredients": [ /* ... */ ],
        "steps": [ /* ... */ ]
    }
}
```

### 3. 刷新推荐接口

```typescript
// POST /api/recommend/refresh
const response = await fetch('/api/recommend/refresh', {
    method: 'POST',
    body: JSON.stringify({
        session_id: 'abc123'
    })
});

const { data } = await response.json();
// ✅ data 中包含 recommendation_id（新的推荐会有新的 ID）
console.log('新的推荐ID:', data.recommendation_id);
```

---

## 🔄 变更的 API 接口

### 1. POST /api/menu/favorites - 添加到收藏夹

#### 请求参数变更
在原有基础上新增**可选参数** `recommendation_id`：

```typescript
// 请求体类型
interface AddToFavoritesRequest {
    cocktail_id: number;              // 必填
    note?: string;                    // 可选，个人笔记
    add_to_today?: boolean;           // 可选，是否同时添加到今日酒单
    recommendation_id?: number;       // 🆕 可选，推荐记录ID
}
```

#### 请求示例

**场景 1：从推荐列表添加收藏**
```json
POST /api/menu/favorites
Content-Type: application/json
Authorization: Bearer <token>

{
    "cocktail_id": 123,
    "recommendation_id": 456,
    "note": "AI 推荐的，想试试"
}
```

**场景 2：普通收藏（不来自推荐）**
```json
POST /api/menu/favorites
{
    "cocktail_id": 789,
    "note": "自己找到的好酒"
}
```

#### 响应示例
```json
{
    "code": 0,
    "message": "success",
    "data": {
        "saved_id": 1,
        "cocktail_id": 123,
        "recommendation_id": 456,           // 🆕 返回推荐ID
        "is_in_today": false,
        "personal_note": "AI 推荐的，想试试",
        "added_at": "2026-09-08T15:30:00Z",
        "cocktail": {
            "id": 123,
            "name": "Mojito",
            "name_zh": "莫吉托"
            // ... 其他鸡尾酒信息
        }
    }
}
```

---

### 2. POST /api/menu/today - 添加到今日酒单

#### 请求参数变更
在原有基础上新增**可选参数** `recommendation_id`：

```typescript
interface AddToTodayRequest {
    cocktail_id: number;              // 必填
    note?: string;                    // 可选，个人笔记
    recommendation_id?: number;       // 🆕 可选，推荐记录ID
}
```

#### 请求示例
```json
POST /api/menu/today
Authorization: Bearer <token>

{
    "cocktail_id": 123,
    "recommendation_id": 456,
    "note": "今晚做这个推荐的酒"
}
```

#### 响应示例
```json
{
    "code": 0,
    "data": {
        "saved_id": 1,
        "cocktail_id": 123,
        "recommendation_id": 456,           // 🆕 返回推荐ID
        "is_in_today": true,
        "plan_date": "2026-09-08",
        "priority": 0,
        "personal_note": "今晚做这个推荐的酒",
        "cocktail": { /* ... */ }
    }
}
```

---

### 3. GET /api/menu/favorites - 获取收藏列表

#### 响应变更
每个收藏项中新增 `recommendation_id` 字段：

```typescript
interface SavedCocktail {
    saved_id: number;
    cocktail_id: number;
    recommendation_id: number | null;      // 🆕 推荐ID，可能为 null
    is_in_today: boolean;
    plan_date: string | null;
    priority: number;
    personal_note: string | null;
    added_at: string;
    cocktail: Cocktail;
}
```

#### 响应示例
```json
GET /api/menu/favorites?sort_by=added_at

{
    "code": 0,
    "data": {
        "total": 2,
        "cocktails": [
            {
                "saved_id": 1,
                "cocktail_id": 123,
                "recommendation_id": 456,       // 🆕 来自推荐的收藏
                "is_in_today": false,
                "personal_note": "AI 推荐的",
                "added_at": "2026-09-08T15:30:00Z",
                "cocktail": { /* ... */ }
            },
            {
                "saved_id": 2,
                "cocktail_id": 789,
                "recommendation_id": null,       // 🆕 普通收藏，无推荐ID
                "is_in_today": false,
                "personal_note": "自己找的",
                "added_at": "2026-09-07T10:00:00Z",
                "cocktail": { /* ... */ }
            }
        ]
    }
}
```

---

### 4. GET /api/menu/today - 获取今日酒单

#### 响应变更
每个酒单项中新增 `recommendation_id` 字段：

```json
GET /api/menu/today

{
    "code": 0,
    "data": {
        "date": "2026-09-08",
        "count": 1,
        "missing_ingredients_count": 2,
        "cocktails": [
            {
                "saved_id": 1,
                "recommendation_id": 456,       // 🆕 推荐ID
                "is_in_today": true,
                "plan_date": "2026-09-08",
                "priority": 10,
                "cocktail": { /* ... */ }
            }
        ]
    }
}
```

---

## 💡 前端使用指南

### 完整流程示例

```typescript
// 1️⃣ 发起推荐请求（SSE）
let currentRecommendationId: number | null = null;

const eventSource = new EventSource('/api/recommend/stream');

eventSource.addEventListener('message', (e) => {
    const data = JSON.parse(e.data);
    
    switch (data.type) {
        case 'session':
            console.log('会话ID:', data.session_id);
            break;
            
        case 'batch1':
            // 显示鸡尾酒信息和 AI 文案
            displayCocktail(data.cocktail, data.ai);
            break;
            
        case 'batch2':
            // 显示原料列表
            displayIngredients(data.ingredients);
            break;
            
        case 'batch3':
            // 显示制作步骤
            displaySteps(data.steps);
            break;
            
        case 'done':
            // ✅ 保存推荐ID，供后续收藏使用
            currentRecommendationId = data.recommendation_id;
            console.log('推荐完成，ID:', currentRecommendationId);
            eventSource.close();
            break;
            
        case 'error':
            console.error('推荐失败:', data.message);
            eventSource.close();
            break;
    }
});

// 2️⃣ 用户点击收藏按钮
async function handleFavorite(cocktailId: number) {
    if (!currentRecommendationId) {
        console.warn('没有推荐ID，可能是直接浏览的鸡尾酒');
    }
    
    await fetch('/api/menu/favorites', {
        method: 'POST',
        headers: {
            'Content-Type': 'application/json',
            'Authorization': `Bearer ${token}`
        },
        body: JSON.stringify({
            cocktail_id: cocktailId,
            recommendation_id: currentRecommendationId,  // 传入推荐ID
            note: '来自AI推荐'
        })
    });
    
    alert('收藏成功！');
}
```

### React Hooks 示例

```tsx
// useRecommendation.ts
import { useState, useEffect } from 'react';

interface RecommendationData {
    sessionId: string | null;
    recommendationId: number | null;
    cocktail: any | null;
    ai: any | null;
    ingredients: any[];
    steps: any[];
    loading: boolean;
    error: string | null;
}

export function useRecommendation(preferences: any) {
    const [data, setData] = useState<RecommendationData>({
        sessionId: null,
        recommendationId: null,
        cocktail: null,
        ai: null,
        ingredients: [],
        steps: [],
        loading: false,
        error: null
    });

    useEffect(() => {
        if (!preferences) return;

        setData(prev => ({ ...prev, loading: true, error: null }));

        const eventSource = new EventSource('/api/recommend/stream', {
            method: 'POST',
            body: JSON.stringify(preferences)
        });

        eventSource.addEventListener('message', (e) => {
            const event = JSON.parse(e.data);

            switch (event.type) {
                case 'session':
                    setData(prev => ({ ...prev, sessionId: event.session_id }));
                    break;

                case 'batch1':
                    setData(prev => ({
                        ...prev,
                        cocktail: event.cocktail,
                        ai: event.ai
                    }));
                    break;

                case 'batch2':
                    setData(prev => ({ ...prev, ingredients: event.ingredients }));
                    break;

                case 'batch3':
                    setData(prev => ({ ...prev, steps: event.steps }));
                    break;

                case 'done':
                    // ✅ 保存推荐ID
                    setData(prev => ({
                        ...prev,
                        recommendationId: event.recommendation_id,
                        loading: false
                    }));
                    eventSource.close();
                    break;

                case 'error':
                    setData(prev => ({
                        ...prev,
                        error: event.message,
                        loading: false
                    }));
                    eventSource.close();
                    break;
            }
        });

        return () => eventSource.close();
    }, [preferences]);

    return data;
}

// RecommendationPage.tsx
export function RecommendationPage() {
    const { recommendationId, cocktail, ai, ingredients, steps, loading } = 
        useRecommendation({ mood_tags: ['relaxing'] });

    async function handleFavorite() {
        await fetch('/api/menu/favorites', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({
                cocktail_id: cocktail.id,
                recommendation_id: recommendationId,  // ✅ 使用保存的ID
                note: '来自AI推荐'
            })
        });
    }

    return (
        <div>
            {loading && <Loading />}
            {cocktail && (
                <>
                    <CocktailCard cocktail={cocktail} ai={ai} />
                    <button onClick={handleFavorite}>
                        ⭐ 收藏
                    </button>
                </>
            )}
        </div>
    );
}
```

### 使用场景 1：用户从推荐列表收藏

```typescript
// 用户点击推荐列表中的"收藏"按钮
async function addRecommendationToFavorites(
    cocktailId: number, 
    recommendationId: number
) {
    const response = await fetch('/api/menu/favorites', {
        method: 'POST',
        headers: {
            'Content-Type': 'application/json',
            'Authorization': `Bearer ${token}`
        },
        body: JSON.stringify({
            cocktail_id: cocktailId,
            recommendation_id: recommendationId,  // 传入推荐ID
            note: '来自AI推荐'
        })
    });
    
    return response.json();
}
```

### 使用场景 2：显示收藏列表时展示推荐详情

```typescript
// 获取收藏列表
async function getFavoritesWithRecommendations() {
    const { data } = await fetch('/api/menu/favorites').then(r => r.json());
    
    // 对于有推荐ID的收藏，可以获取详细推荐信息
    const cocktailsWithDetails = await Promise.all(
        data.cocktails.map(async (saved) => {
            if (saved.recommendation_id) {
                // 获取推荐详情
                const recommendation = await fetch(
                    `/api/recommend/history/${saved.recommendation_id}`
                ).then(r => r.json());
                
                return {
                    ...saved,
                    recommendationDetails: {
                        ai_reason: recommendation.data.ai_reason,
                        ai_poetic: recommendation.data.ai_poetic,
                        ai_mood_caption: recommendation.data.ai_mood_caption,
                        mood_tags: recommendation.data.mood_tags,
                        flavor_tags: recommendation.data.flavor_tags
                    }
                };
            }
            return saved;
        })
    );
    
    return cocktailsWithDetails;
}
```

### 使用场景 3：UI 展示建议

```tsx
// React 组件示例
function CocktailCard({ saved }: { saved: SavedCocktail }) {
    return (
        <div className="cocktail-card">
            <h3>{saved.cocktail.name_zh}</h3>
            <p>{saved.personal_note}</p>
            
            {/* 如果来自推荐，显示特殊标记 */}
            {saved.recommendation_id && (
                <div className="recommendation-badge">
                    <span>✨ AI 推荐</span>
                    <button onClick={() => viewRecommendationDetails(saved.recommendation_id)}>
                        查看推荐理由
                    </button>
                </div>
            )}
        </div>
    );
}
```

---

## ✅ 向后兼容性

### 保证兼容的设计：
1. ✅ `recommendation_id` 是**可选参数**，不传不会报错
2. ✅ 现有的收藏功能完全不受影响
3. ✅ 旧版本前端可以正常使用，只是不会获得推荐关联功能
4. ✅ 新字段在响应中始终存在，值可能为 `null`

### 前端迁移建议：
```typescript
// ✅ 安全的类型定义
interface SavedCocktail {
    // ... 其他字段
    recommendation_id: number | null;  // 允许 null
}

// ✅ 安全的使用方式
if (saved.recommendation_id != null) {  // 注意：使用 != null，不是 !== null
    // 获取推荐详情
}

// ❌ 避免这样写
if (saved.recommendation_id) {  // 如果 ID 为 0 会误判
    // ...
}
```

---

## 📊 数据类型定义

```typescript
// TypeScript 类型定义文件

/** 添加到收藏夹请求 */
interface AddToFavoritesRequest {
    cocktail_id: number;
    note?: string;
    add_to_today?: boolean;
    recommendation_id?: number;  // 🆕 新增
}

/** 添加到今日酒单请求 */
interface AddToTodayRequest {
    cocktail_id: number;
    note?: string;
    recommendation_id?: number;  // 🆕 新增
}

/** 保存的鸡尾酒信息 */
interface SavedCocktail {
    saved_id: number;
    cocktail_id: number;
    recommendation_id: number | null;  // 🆕 新增
    is_in_today: boolean;
    plan_date: string | null;
    priority: number;
    personal_note: string | null;
    added_at: string;
    cocktail: Cocktail;
}

/** 收藏列表响应 */
interface FavoritesResponse {
    code: 0;
    data: {
        total: number;
        cocktails: SavedCocktail[];
    };
}

/** 今日酒单响应 */
interface TodayMenuResponse {
    code: 0;
    data: {
        date: string;
        count: number;
        missing_ingredients_count: number;
        cocktails: SavedCocktail[];
    };
}
```

---

## 🧪 测试建议

### 测试用例 1：收藏来自推荐的鸡尾酒
```bash
curl -X POST http://localhost:5000/api/menu/favorites \
  -H "Authorization: Bearer <token>" \
  -H "Content-Type: application/json" \
  -d '{
    "cocktail_id": 123,
    "recommendation_id": 456
  }'
```

### 测试用例 2：普通收藏（不带推荐ID）
```bash
curl -X POST http://localhost:5000/api/menu/favorites \
  -H "Authorization: Bearer <token>" \
  -H "Content-Type: application/json" \
  -d '{
    "cocktail_id": 789,
    "note": "自己找的"
  }'
```

### 测试用例 3：获取收藏列表并验证字段
```bash
curl -X GET http://localhost:5000/api/menu/favorites \
  -H "Authorization: Bearer <token>"

# 预期：每条记录都有 recommendation_id 字段（可能为 null）
```

---

## 🔗 相关 API 文档

- [GET /api/recommend/history/:id](./recommend_api.md) - 获取推荐详情
- [POST /api/menu/favorites](./menu_api.md#add-to-favorites) - 添加收藏
- [GET /api/menu/favorites](./menu_api.md#get-favorites) - 获取收藏列表

---

## ❓ FAQ

### Q1: 如果收藏时不传 `recommendation_id`，会怎么样？
A: 完全正常，字段值为 `null`，不影响任何功能。

### Q2: 如果推荐记录被删除了，收藏记录会怎么样？
A: 收藏记录保留，但 `recommendation_id` 会自动设为 `null`（数据库外键设置为 `ON DELETE SET NULL`）。

### Q3: 可以更新已有收藏的 `recommendation_id` 吗？
A: 当前版本不支持更新。如果需要此功能，请联系后端团队。

### Q4: 前端需要立即升级吗？
A: 不需要。此变更完全向后兼容，前端可以按自己的节奏升级。但建议尽快集成以提供更好的用户体验。

---

## 📞 联系方式

如有问题，请联系：
- 后端负责人：[您的联系方式]
- 技术文档：[文档链接]
