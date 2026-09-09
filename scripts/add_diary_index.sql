-- ============================================================
-- 调酒日记功能 - 数据库索引优化
-- ============================================================
-- 用途：优化日历查询性能，加速按用户和时间查询卡片

-- 按用户和创建时间的复合索引（如果尚未存在）
-- 用于加速日历视图和日期详情查询
CREATE INDEX IF NOT EXISTS idx_share_cards_user_created 
ON share_cards(user_id, created_at DESC);

-- 验证索引创建
SELECT 
    indexname,
    indexdef
FROM pg_indexes
WHERE tablename = 'share_cards'
AND indexname = 'idx_share_cards_user_created';

-- 查询性能说明：
-- 1. 日历查询：WHERE user_id = ? AND created_at >= ? AND created_at < ?
--    该索引能够快速定位用户的时间范围内的卡片
-- 2. 统计查询：按用户ID聚合时能用到该索引
-- 3. 日期详情：精确日期查询也能利用该索引

-- 预期性能提升：
-- - 对于有 100+ 张卡片的用户，查询时间从 ~50ms 降至 <5ms
-- - 月历视图加载速度提升 80-90%
