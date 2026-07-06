-- Migration 003: 将酒柜从基于 ingredients（细分品牌）切换到基于 ingredient_family（品类）
--
-- 变更内容：
--   1. user_cabinet 新增 family_id 列（FK → ingredient_family.id）
--   2. 按 ingredients.ingredient_family_id 自动迁移已有数据
--   3. 删除旧的 ingredient_id 列及相关约束/索引
--   4. 重建唯一约束和索引
--
-- 执行前请先备份数据！
-- psql -d <db_name> -f 003_cabinet_family_migration.sql

BEGIN;

-- 1. 新增 family_id 列（允许 NULL，迁移后再设置 NOT NULL）
ALTER TABLE user_cabinet
    ADD COLUMN IF NOT EXISTS family_id integer
        REFERENCES ingredient_family(id) ON DELETE RESTRICT;

-- 2. 将已有记录按 ingredients.ingredient_family_id 迁移
UPDATE user_cabinet uc
SET family_id = i.ingredient_family_id
FROM ingredients i
WHERE uc.ingredient_id = i.id
  AND i.ingredient_family_id IS NOT NULL;

-- 3. 如果有原料没有关联品类，先删除这些孤立记录（否则 NOT NULL 会报错）
--    若不想丢失数据，可手动处理后再删 NULL 行。
DELETE FROM user_cabinet WHERE family_id IS NULL;

-- 4. 对同一用户+品类去重（可能多个 ingredient 映射到同一 family）
--    保留最早添加的那条记录
DELETE FROM user_cabinet
WHERE id NOT IN (
    SELECT DISTINCT ON (user_id, family_id) id
    FROM user_cabinet
    ORDER BY user_id, family_id, added_at ASC
);

-- 5. 设置 family_id NOT NULL
ALTER TABLE user_cabinet
    ALTER COLUMN family_id SET NOT NULL;

-- 6. 删除旧的唯一约束（(user_id, ingredient_id)）
ALTER TABLE user_cabinet
    DROP CONSTRAINT IF EXISTS user_cabinet_user_id_ingredient_id_key;

-- 7. 添加新的唯一约束（(user_id, family_id)）
ALTER TABLE user_cabinet
    ADD CONSTRAINT user_cabinet_user_id_family_id_key UNIQUE (user_id, family_id);

-- 8. 删除旧的 ingredient_id FK 约束
ALTER TABLE user_cabinet
    DROP CONSTRAINT IF EXISTS user_cabinet_ingredient_id_fkey;

-- 9. 删除旧的 ingredient_id 索引
DROP INDEX IF EXISTS idx_cabinet_ingredient_id;

-- 10. 删除旧的 ingredient_id 列
ALTER TABLE user_cabinet
    DROP COLUMN IF EXISTS ingredient_id;

-- 11. 创建新的 family_id 索引
CREATE INDEX IF NOT EXISTS idx_cabinet_family_id ON user_cabinet USING btree (family_id);

COMMIT;
