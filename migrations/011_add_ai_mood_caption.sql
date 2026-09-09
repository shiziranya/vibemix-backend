-- 011: 添加 ai_mood_caption 字段到 recommendation_history 表
-- 用于存储 AI 生成的心情文案，与推荐接口返回格式保持一致

ALTER TABLE recommendation_history
ADD COLUMN IF NOT EXISTS ai_mood_caption TEXT;

COMMENT ON COLUMN recommendation_history.ai_mood_caption IS 'AI生成的心情文案，用于分享卡片（如："今晚的心情是微醺放松，所以调了这杯 Aperol Spritz"）';
