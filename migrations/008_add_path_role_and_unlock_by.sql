-- Migration: 添加主线/支线功能字段
-- Date: 2026-07-19
-- Description: 为 map_nodes 添加 path_role 和 unlock_by 字段，为 map_edges 添加 path_role 字段

-- 为 map_nodes 添加 path_role 字段
ALTER TABLE map_nodes
ADD COLUMN path_role VARCHAR(10) NOT NULL DEFAULT 'main';

-- 为 map_nodes 添加 unlock_by 字段（外键指向 cocktails）
ALTER TABLE map_nodes
ADD COLUMN unlock_by INTEGER REFERENCES cocktails(id);

-- 为 map_nodes 添加约束检查
ALTER TABLE map_nodes
ADD CONSTRAINT map_nodes_path_role_check CHECK (path_role IN ('main', 'side'));

-- 为 map_edges 添加 path_role 字段
ALTER TABLE map_edges
ADD COLUMN path_role VARCHAR(10) NOT NULL DEFAULT 'main';

-- 为 map_edges 添加约束检查
ALTER TABLE map_edges
ADD CONSTRAINT map_edges_path_role_check CHECK (path_role IN ('main', 'side'));

-- 创建索引以优化查询
CREATE INDEX idx_map_nodes_path_role ON map_nodes(path_role);
CREATE INDEX idx_map_nodes_unlock_by ON map_nodes(unlock_by);
CREATE INDEX idx_map_edges_path_role ON map_edges(path_role);

-- 添加注释
COMMENT ON COLUMN map_nodes.path_role IS '节点类型：main=主线节点, side=支线节点';
COMMENT ON COLUMN map_nodes.unlock_by IS '支线节点解锁所需的鸡尾酒ID（购买该酒即可解锁）';
COMMENT ON COLUMN map_edges.path_role IS '边类型：main=主线关系, side=支线关系';
