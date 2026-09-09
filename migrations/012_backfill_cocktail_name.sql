-- 回填 share_cards 表中的 cocktail_name 字段
-- 将关联鸡尾酒的名称填充到历史卡片记录中
--
-- 执行前检查：
--   SELECT COUNT(*) FROM share_cards WHERE cocktail_name IS NULL;
--
-- 执行：
--   psql -d tipsy_inspirations -f 012_backfill_cocktail_name.sql

BEGIN;

-- 回填 cocktail_name 字段
UPDATE share_cards sc
SET cocktail_name = c.name
FROM cocktails c
WHERE sc.cocktail_id = c.id
  AND sc.cocktail_name IS NULL;

-- 显示回填结果
SELECT 
    COUNT(*) FILTER (WHERE cocktail_name IS NOT NULL) as filled,
    COUNT(*) FILTER (WHERE cocktail_name IS NULL) as still_null,
    COUNT(*) as total
FROM share_cards;

COMMIT;

-- 验证回填结果
-- 应该看到所有有 cocktail_id 的卡片都有 cocktail_name 了
SELECT 
    sc.id,
    sc.cocktail_id,
    sc.cocktail_name,
    sc.created_at
FROM share_cards sc
WHERE sc.cocktail_id IS NOT NULL
  AND sc.cocktail_name IS NULL
LIMIT 5;
