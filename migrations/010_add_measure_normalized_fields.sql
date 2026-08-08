-- 010: 添加规范化用量字段到 cocktail_ingredients 表
-- 用于支持中国用户习惯的 ml 单位和中文用量描述

ALTER TABLE cocktail_ingredients
ADD COLUMN IF NOT EXISTS measure_normalized VARCHAR(100),  -- 规范化后的中文用量，如"45ml"、"2滴"、"适量"
ADD COLUMN IF NOT EXISTS measure_value NUMERIC(7,2),       -- 数值部分（可能为null，用于排序和计算）
ADD COLUMN IF NOT EXISTS measure_unit VARCHAR(20),         -- 单位部分：ml/滴/少许/适量/barspoon等
ADD COLUMN IF NOT EXISTS measure_type VARCHAR(20);         -- 类型：precise(精确)/approximate(约量)/descriptive(描述性)/unclear(需人工)

-- 添加索引以优化查询
CREATE INDEX IF NOT EXISTS idx_cocktail_ingredients_measure_type 
ON cocktail_ingredients(measure_type);

COMMENT ON COLUMN cocktail_ingredients.measure_normalized IS '规范化用量描述(中文)，如"45ml"、"2滴"、"少许"';
COMMENT ON COLUMN cocktail_ingredients.measure_value IS '用量数值(用于计算和排序)';
COMMENT ON COLUMN cocktail_ingredients.measure_unit IS '用量单位(ml/滴/barspoon等)';
COMMENT ON COLUMN cocktail_ingredients.measure_type IS '用量类型: precise/approximate/descriptive/unclear';
