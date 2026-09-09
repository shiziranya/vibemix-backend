-- Migration 012: share_cards 新增 cocktail_name 与 ai_poetic 列
--
-- 变更内容：
--   1. share_cards 新增 cocktail_name（鸡尾酒名称）
--   2. share_cards 新增 ai_poetic（AI 诗意描述）
--
-- 用途：
--   在分享卡片中存储鸡尾酒名称和 AI 生成的诗意描述，
--   即使关联的鸡尾酒被修改或删除，卡片仍保留原始信息
--
-- 执行：
--   psql -d vibemix -f 012_add_cocktail_name_and_ai_poetic.sql

BEGIN;

ALTER TABLE share_cards
    ADD COLUMN IF NOT EXISTS cocktail_name VARCHAR(200),
    ADD COLUMN IF NOT EXISTS ai_poetic TEXT;

COMMENT ON COLUMN share_cards.cocktail_name IS '鸡尾酒名称，创建卡片时保存快照';
COMMENT ON COLUMN share_cards.ai_poetic IS 'AI生成的诗意描述，用于展示在卡片上';

COMMIT;
