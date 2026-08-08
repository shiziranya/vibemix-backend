-- Migration: 修正主线/支线功能字段
-- Date: 2026-07-19
-- Description: 修正 map_nodes 表的 path_role 和 unlock_by 字段类型和约束

-- 步骤1：先更新现有数据，将旧的 path_role 值映射到新的值
-- 映射规则：gateway -> main, boss -> main, branch -> side, main -> main
UPDATE map_nodes 
SET path_role = CASE 
    WHEN path_role = 'gateway' THEN 'main'
    WHEN path_role = 'boss' THEN 'main'
    WHEN path_role = 'branch' THEN 'side'
    WHEN path_role = 'main' THEN 'main'
    ELSE 'main'  -- 其他情况默认为 main
END
WHERE path_role IS NOT NULL;

-- 步骤2：为 NULL 值设置默认值
UPDATE map_nodes SET path_role = 'main' WHERE path_role IS NULL;

-- 步骤3：修改 path_role 字段类型和约束
ALTER TABLE map_nodes 
    ALTER COLUMN path_role TYPE VARCHAR(10),
    ALTER COLUMN path_role SET NOT NULL,
    ALTER COLUMN path_role SET DEFAULT 'main';

-- 步骤4：添加约束（如果不存在）
DO $$ 
BEGIN
    IF NOT EXISTS (
        SELECT 1 FROM pg_constraint WHERE conname = 'map_nodes_path_role_check'
    ) THEN
        ALTER TABLE map_nodes
        ADD CONSTRAINT map_nodes_path_role_check CHECK (path_role IN ('main', 'side'));
    END IF;
END $$;

-- 步骤5：处理 unlock_by 字段
-- 先清空 unlock_by（因为当前是 VARCHAR，需要转换为 INTEGER）
UPDATE map_nodes SET unlock_by = NULL;

-- 修改 unlock_by 字段类型为 INTEGER，并添加外键约束
ALTER TABLE map_nodes 
    ALTER COLUMN unlock_by TYPE INTEGER USING unlock_by::INTEGER;

-- 删除旧的外键（如果存在）
DO $$ 
BEGIN
    IF EXISTS (
        SELECT 1 FROM pg_constraint WHERE conname = 'map_nodes_unlock_by_fkey'
    ) THEN
        ALTER TABLE map_nodes DROP CONSTRAINT map_nodes_unlock_by_fkey;
    END IF;
END $$;

-- 添加新的外键约束
ALTER TABLE map_nodes
    ADD CONSTRAINT map_nodes_unlock_by_fkey 
    FOREIGN KEY (unlock_by) REFERENCES cocktails(id);

-- 更新注释
COMMENT ON COLUMN map_nodes.path_role IS '节点类型：main=主线节点, side=支线节点';
COMMENT ON COLUMN map_nodes.unlock_by IS '支线节点解锁所需的鸡尾酒ID（购买该酒即可解锁）';
COMMENT ON COLUMN map_edges.path_role IS '边类型：main=主线关系, side=支线关系';

-- 验证数据
SELECT 'map_nodes path_role 分布:' AS info;
SELECT path_role, COUNT(*) FROM map_nodes GROUP BY path_role;

SELECT 'map_edges path_role 分布:' AS info;
SELECT path_role, COUNT(*) FROM map_edges GROUP BY path_role;
