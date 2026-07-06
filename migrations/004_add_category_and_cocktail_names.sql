-- Migration 004: 推荐偏好新增 category 筛选，历史记录新增酒名与原型配方字段
--
-- 变更内容：
--   1. recommendation_history 新增 category 列（鸡尾酒类型筛选：Craft/Classic/Other/Shot）
--   2. recommendation_history 新增 cocktail_name / cocktail_name_zh（AI 填充或生成的酒名）
--   3. recommendation_history 新增 prototype_name / prototype_name_zh（original 模式的原型配方名）
--
-- psql -d <db_name> -f 004_add_category_and_cocktail_names.sql

BEGIN;

ALTER TABLE recommendation_history
    ADD COLUMN IF NOT EXISTS category          VARCHAR(20),
    ADD COLUMN IF NOT EXISTS cocktail_name     VARCHAR(200),
    ADD COLUMN IF NOT EXISTS cocktail_name_zh  VARCHAR(200),
    ADD COLUMN IF NOT EXISTS prototype_name    VARCHAR(200),
    ADD COLUMN IF NOT EXISTS prototype_name_zh VARCHAR(200);

COMMIT;
