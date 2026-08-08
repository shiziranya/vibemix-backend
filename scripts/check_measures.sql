-- 用量数据审计和检查脚本
-- 运行: psql "$SUPABASE_DATABASE_URL" -f scripts/check_measures.sql

\echo '========================================='
\echo '用量规范化 - 数据审计报告'
\echo '========================================='
\echo ''

-- 1. 总体统计
\echo '1. 总体统计'
\echo '-----------------------------------------'
SELECT 
    COUNT(*) AS total_records,
    COUNT(measure_raw) AS has_measure_raw,
    COUNT(measure_normalized) AS has_measure_normalized,
    COUNT(CASE WHEN measure_type = 'precise' THEN 1 END) AS precise_count,
    COUNT(CASE WHEN measure_type = 'approximate' THEN 1 END) AS approximate_count,
    COUNT(CASE WHEN measure_type = 'descriptive' THEN 1 END) AS descriptive_count,
    COUNT(CASE WHEN measure_type = 'unclear' THEN 1 END) AS unclear_count
FROM cocktail_ingredients;

\echo ''
\echo '2. 按用量类型分组统计'
\echo '-----------------------------------------'
SELECT 
    measure_type,
    COUNT(*) AS count,
    ROUND(COUNT(*) * 100.0 / SUM(COUNT(*)) OVER (), 2) AS percentage
FROM cocktail_ingredients
WHERE measure_raw IS NOT NULL
GROUP BY measure_type
ORDER BY count DESC;

\echo ''
\echo '3. 需要换算的单位（oz）- 前10条'
\echo '-----------------------------------------'
SELECT 
    id,
    measure_raw,
    measure_normalized,
    measure_value,
    measure_unit
FROM cocktail_ingredients
WHERE measure_raw ILIKE '%oz%'
LIMIT 10;

\echo ''
\echo '4. 保留单位（dash）- 前10条'
\echo '-----------------------------------------'
SELECT 
    id,
    measure_raw,
    measure_normalized,
    measure_type
FROM cocktail_ingredients
WHERE measure_raw ILIKE '%dash%'
LIMIT 10;

\echo ''
\echo '5. 描述性用量 - 前10条'
\echo '-----------------------------------------'
SELECT 
    id,
    measure_raw,
    measure_normalized
FROM cocktail_ingredients
WHERE measure_type = 'descriptive'
LIMIT 10;

\echo ''
\echo '6. 需要人工审核的记录（unclear）'
\echo '-----------------------------------------'
SELECT 
    id,
    measure_raw,
    measure_normalized,
    measure_type
FROM cocktail_ingredients
WHERE measure_type = 'unclear'
ORDER BY id
LIMIT 20;

\echo ''
\echo '7. 最常见的原始用量值（Top 20）'
\echo '-----------------------------------------'
SELECT 
    measure_raw,
    COUNT(*) AS count
FROM cocktail_ingredients
WHERE measure_raw IS NOT NULL
GROUP BY measure_raw
ORDER BY count DESC
LIMIT 20;

\echo ''
\echo '8. 规范化后的用量分布（Top 20）'
\echo '-----------------------------------------'
SELECT 
    measure_normalized,
    measure_type,
    COUNT(*) AS count
FROM cocktail_ingredients
WHERE measure_normalized IS NOT NULL
GROUP BY measure_normalized, measure_type
ORDER BY count DESC
LIMIT 20;

\echo ''
\echo '========================================='
\echo '审计完成'
\echo '========================================='
