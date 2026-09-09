-- ============================================================
-- Migration 014: Add recommendation_id to user_saved_cocktails
-- ============================================================
-- 目的：将用户收藏的鸡尾酒关联到 LLM 推荐记录
-- 这样前端可以获取推荐ID并查询推荐详情

-- 添加 recommendation_id 字段（外键关联到 recommendation_history）
ALTER TABLE user_saved_cocktails
    ADD COLUMN IF NOT EXISTS recommendation_id INTEGER 
        REFERENCES recommendation_history(id) ON DELETE SET NULL;

-- 添加索引优化查询性能
-- 用于查询某个推荐的所有收藏记录
CREATE INDEX IF NOT EXISTS idx_saved_cocktails_recommendation_id
    ON user_saved_cocktails(recommendation_id)
    WHERE recommendation_id IS NOT NULL;

-- 注释
COMMENT ON COLUMN user_saved_cocktails.recommendation_id IS '关联的推荐记录ID（如果来自LLM推荐）';
