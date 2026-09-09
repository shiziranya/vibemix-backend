-- 创建用户收藏鸡尾酒表
CREATE TABLE IF NOT EXISTS user_saved_cocktails (
    id SERIAL PRIMARY KEY,
    user_id UUID NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    cocktail_id INTEGER NOT NULL REFERENCES cocktails(id) ON DELETE CASCADE,
    is_in_today BOOLEAN NOT NULL DEFAULT FALSE,
    plan_date DATE,
    priority SMALLINT NOT NULL DEFAULT 0,
    personal_note TEXT,
    added_at TIMESTAMP WITH TIME ZONE NOT NULL DEFAULT NOW(),
    updated_at TIMESTAMP WITH TIME ZONE NOT NULL DEFAULT NOW(),
    CONSTRAINT uq_user_cocktail UNIQUE (user_id, cocktail_id)
);

-- 创建索引优化查询性能
-- 查询用户的所有收藏
CREATE INDEX IF NOT EXISTS idx_saved_cocktails_user 
ON user_saved_cocktails(user_id, added_at DESC);

-- 查询今日酒单
CREATE INDEX IF NOT EXISTS idx_saved_cocktails_today 
ON user_saved_cocktails(user_id, is_in_today, plan_date DESC) 
WHERE is_in_today = TRUE;

-- 自动清理过期今日酒单（用于定时任务查询）
CREATE INDEX IF NOT EXISTS idx_saved_cocktails_plan_date 
ON user_saved_cocktails(plan_date) 
WHERE is_in_today = TRUE AND plan_date IS NOT NULL;

-- 更新 updated_at 触发器
CREATE OR REPLACE FUNCTION update_saved_cocktails_updated_at()
RETURNS TRIGGER AS $$
BEGIN
    NEW.updated_at = NOW();
    RETURN NEW;
END;
$$ LANGUAGE plpgsql;

CREATE TRIGGER trigger_update_saved_cocktails_updated_at
    BEFORE UPDATE ON user_saved_cocktails
    FOR EACH ROW
    EXECUTE FUNCTION update_saved_cocktails_updated_at();

-- 注释
COMMENT ON TABLE user_saved_cocktails IS '用户收藏的鸡尾酒（收藏夹 + 今日酒单）';
COMMENT ON COLUMN user_saved_cocktails.is_in_today IS '是否在今日酒单中';
COMMENT ON COLUMN user_saved_cocktails.plan_date IS '今日酒单的日期（用于自动清理）';
COMMENT ON COLUMN user_saved_cocktails.priority IS '今日酒单中的优先级排序';
