-- 添加 ingredient_family 表的 image_url 字段
-- Migration: 014_add_ingredient_family_image
-- Date: 2026-08-30

ALTER TABLE ingredient_family 
ADD COLUMN image_url VARCHAR(255);

-- 添加索引以提高查询性能
CREATE INDEX idx_ingredient_family_image_url ON ingredient_family(image_url);

COMMENT ON COLUMN ingredient_family.image_url IS '食材品类图片URL路径';
