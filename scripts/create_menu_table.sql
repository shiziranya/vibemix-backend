-- 酒单功能数据表和索引
-- 用于手动执行或参考

-- 创建 user_saved_cocktails 表
CREATE TABLE IF NOT EXISTS user_saved_cocktails (
    id SERIAL PRIMARY KEY,
    user_id UUID NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    cocktail_id INTEGER NOT NULL REFERENCES cocktails(id) ON DELETE CASCADE,
    is_in_today BOOLEAN NOT NULL DEFAULT FALSE,
    plan_date DATE,
    priority SMALLINT NOT NULL DEFAULT 0,
    personal_note TEXT,
    added_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    CONSTRAINT uq_user_cocktail UNIQUE (user_id, cocktail_id)
);

-- 用户收藏查询索引
CREATE INDEX IF NOT EXISTS idx_saved_cocktails_user 
ON user_saved_cocktails(user_id, added_at DESC);

-- 今日酒单查询索引（部分索引，只索引今日酒单）
CREATE INDEX IF NOT EXISTS idx_saved_cocktails_today 
ON user_saved_cocktails(user_id, is_in_today, plan_date) 
WHERE is_in_today = TRUE;

-- 过期酒单清理索引（部分索引）
CREATE INDEX IF NOT EXISTS idx_saved_cocktails_plan_date 
ON user_saved_cocktails(plan_date) 
WHERE is_in_today = TRUE AND plan_date IS NOT NULL;

-- 更新 share_cards 表，添加关联字段（可选，用于关联酒单计划）
ALTER TABLE share_cards 
ADD COLUMN IF NOT EXISTS from_saved_cocktail_id INTEGER 
REFERENCES user_saved_cocktails(id) ON DELETE SET NULL;

-- 为新增字段创建索引
CREATE INDEX IF NOT EXISTS idx_share_cards_from_saved 
ON share_cards(from_saved_cocktail_id) 
WHERE from_saved_cocktail_id IS NOT NULL;

-- 注释
COMMENT ON TABLE user_saved_cocktails IS '用户收藏的鸡尾酒（收藏夹+今日酒单）';
COMMENT ON COLUMN user_saved_cocktails.is_in_today IS '是否在今日酒单中';
COMMENT ON COLUMN user_saved_cocktails.plan_date IS '计划日期，用于自动清理过期今日酒单';
COMMENT ON COLUMN user_saved_cocktails.priority IS '优先级，用于今日酒单排序';
