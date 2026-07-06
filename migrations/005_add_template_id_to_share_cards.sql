-- Migration 005: share_cards 新增 template_id 与 text_overrides 列
--
-- 变更内容：
--   1. share_cards 新增 template_id（卡片模板 ID）
--   2. share_cards 新增 text_overrides（用户自定义文字层位置，JSON）
--
-- psql -d tipsy_inspirations -f 005_add_template_id_to_share_cards.sql

BEGIN;

ALTER TABLE share_cards
    ADD COLUMN IF NOT EXISTS template_id    VARCHAR(64),
    ADD COLUMN IF NOT EXISTS text_overrides JSON;

COMMIT;
