#!/usr/bin/env python3
"""
计算各主题节点的 pos_x / pos_y，并写入 map_nodes 表。

布局规则：
  - 3 行（row 0/1/2），纵向均匀分布（上/中/下）
  - x 轴 = BFS 深度 × x_step（节点越"深"越靠右）
  - 同深度多节点按 3 行分配，相邻深度行号错开，实现纵向错落
  - 奇数深度的非中行节点额外偏移 ±30px，增加星图感

用法：
    python scripts/compute_positions.py [--theme foundation]
"""

from __future__ import annotations

import argparse
import os
from collections import defaultdict, deque

import psycopg2
import psycopg2.extras

# ── 布局常量（3列 × N行，纵向深度，横向三轨）────────────────────────────────
COL_SPACING = 300      # 列间距（px）
PAD_X       = 180      # 左右留白
PAD_Y       = 150      # 上下留白
Y_STEP      = 180      # 深度间距（px）
STAGGER     = 22       # 奇数深度非中列水平偏移量
CANVAS_W    = PAD_X * 2 + 2 * COL_SPACING   # ≈ 960px 固定宽度
COL_X       = [PAD_X, PAD_X + COL_SPACING, PAD_X + 2 * COL_SPACING]


def load_db_url() -> str:
    env_path = os.path.join(os.path.dirname(__file__), "..", ".env")
    for line in open(env_path, encoding="utf-8"):
        k, _, v = line.strip().partition("=")
        if k == "SUPABASE_DATABASE_URL":
            return v
    raise RuntimeError(".env 中找不到 SUPABASE_DATABASE_URL")


def bfs_depth(
    node_ids: list[int],
    prog_edges: list[tuple[int, int]],
) -> dict[int, int]:
    """
    Multi-source BFS：从「主题内无入边」的节点出发，
    计算每个节点的 BFS 深度。
    未可达节点追加在末尾。
    """
    node_set = set(node_ids)
    children: dict[int, list[int]] = defaultdict(list)
    has_incoming: set[int] = set()

    for f, t in prog_edges:
        if f in node_set and t in node_set:
            children[f].append(t)
            has_incoming.add(t)

    # 主题内入口（无主题内入边）
    entries = [n for n in node_ids if n not in has_incoming]

    depth: dict[int, int] = {}
    q = deque()
    for e in entries:
        depth[e] = 0
        q.append(e)

    while q:
        nid = q.popleft()
        for child in children[nid]:
            if child not in depth:
                depth[child] = depth[nid] + 1
                q.append(child)

    # 未可达节点（孤立）放在最深处
    max_d = max(depth.values(), default=0)
    for nid in node_ids:
        if nid not in depth:
            max_d += 1
            depth[nid] = max_d

    return depth


def assign_rows(
    node_ids: list[int],
    depth: dict[int, int],
    prog_edges: list[tuple[int, int]],
) -> dict[int, int]:
    """
    为每个节点分配行号 0/1/2，规则：
      - 入口（depth=0）放中行（1）
      - 同深度各节点占不同行（≤3 节点时严格不重复）
      - 优先选择父节点不在的行
      - 深度奇偶交错：奇数深度从上/下行起，偶数从下/上行起，产生视觉错落
    """
    node_set = set(node_ids)
    parents: dict[int, list[int]] = defaultdict(list)
    for f, t in prog_edges:
        if f in node_set and t in node_set:
            parents[t].append(f)

    by_depth: dict[int, list[int]] = defaultdict(list)
    for nid in node_ids:
        by_depth[depth[nid]].append(nid)

    row: dict[int, int] = {}
    # 每个深度已分配的行（避免同深度行重复）
    depth_taken: dict[int, set[int]] = defaultdict(set)

    # 深度奇偶决定行偏好顺序（制造交错感）
    PREF_ODD  = [0, 2, 1]   # 奇数深度：上→下→中
    PREF_EVEN = [2, 0, 1]   # 偶数深度：下→上→中

    for d in sorted(by_depth):
        nids = by_depth[d]
        pref = [1] if d == 0 else (PREF_ODD if d % 2 == 1 else PREF_EVEN)

        for nid in nids:
            taken = depth_taken[d]                           # 本深度已用行
            par_rows = {row[p] for p in parents[nid] if p in row}  # 父节点行

            # 优选：符合深度偏好 & 未被本深度占用 & 与父节点不同行
            candidate = None
            for r in pref:
                if r not in taken and r not in par_rows:
                    candidate = r; break
            # 次选：未被本深度占用（允许与父同行）
            if candidate is None:
                for r in pref:
                    if r not in taken:
                        candidate = r; break
            # 兜底：全部占满时循环（> 3 节点时才会到这里）
            if candidate is None:
                candidate = len(taken) % 3

            row[nid] = candidate
            depth_taken[d].add(candidate)

    return row


def compute_positions(
    node_ids: list[int],
    prog_edges: list[tuple[int, int]],
) -> tuple[dict[int, tuple[float, float]], int, int]:
    """
    3列纵向布局：
      x = 列（左/中/右）  ←→ 原来的"行"
      y = BFS 深度         ↓ 从上往下
    返回 {node_id: (x, y)}, canvas_w, canvas_h
    """
    depth = bfs_depth(node_ids, prog_edges)
    col   = assign_rows(node_ids, depth, prog_edges)  # 0=左, 1=中, 2=右

    max_depth = max(depth.values(), default=0)
    canvas_h  = max(900, PAD_Y * 2 + max_depth * Y_STEP + 100)

    positions: dict[int, tuple[float, float]] = {}
    for nid in node_ids:
        d = depth[nid]
        c = col[nid]

        x = COL_X[c]
        y = PAD_Y + d * Y_STEP

        # 奇数深度的非中列水平错落
        if d % 2 == 1 and c != 1:
            x += STAGGER if c == 2 else -STAGGER

        positions[nid] = (round(x, 1), round(y, 1))

    return positions, CANVAS_W, canvas_h


def run(target_slug: str | None = None) -> None:
    conn = psycopg2.connect(load_db_url())
    cur  = conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor)

    # 查所有主题
    if target_slug:
        cur.execute("SELECT id, slug, name_zh FROM map_themes WHERE slug = %s", (target_slug,))
    else:
        cur.execute("SELECT id, slug, name_zh FROM map_themes WHERE is_active ORDER BY sort_order")
    themes = cur.fetchall()

    for theme in themes:
        tid   = theme["id"]
        slug  = theme["slug"]
        label = theme["name_zh"]

        # 主题内节点
        cur.execute("SELECT id FROM map_nodes WHERE theme_id = %s ORDER BY sort_order, id", (tid,))
        node_ids = [r["id"] for r in cur.fetchall()]

        # 主题内 progression 边
        cur.execute(
            """
            SELECT e.from_node_id, e.to_node_id
            FROM map_edges e
            JOIN map_nodes a ON a.id = e.from_node_id AND a.theme_id = %s
            JOIN map_nodes b ON b.id = e.to_node_id   AND b.theme_id = %s
            WHERE e.edge_type = 'progression'
            """,
            (tid, tid),
        )
        prog_edges = [(r["from_node_id"], r["to_node_id"]) for r in cur.fetchall()]

        positions, canvas_w, canvas_h = compute_positions(node_ids, prog_edges)

        # 批量写入 pos_x / pos_y
        for nid, (x, y) in positions.items():
            cur.execute(
                "UPDATE map_nodes SET pos_x = %s, pos_y = %s WHERE id = %s",
                (x, y, nid),
            )

        conn.commit()

        # 统计
        depths = {}
        for nid in node_ids:
            d = bfs_depth(node_ids, prog_edges)[nid]
            depths[d] = depths.get(d, 0) + 1
        max_d = max(depths.keys(), default=0)
        print(
            f"  [{label}] {len(node_ids)} 节点  "
            f"最大深度={max_d}  画布={canvas_w}×{canvas_h}px"
        )
        for d in sorted(depths):
            bar = "█" * depths[d]
            print(f"    depth {d:>2}: {bar} ({depths[d]})")

    cur.close()
    conn.close()
    print("\n✓ 所有主题位置已写入数据库")


def main() -> None:
    parser = argparse.ArgumentParser(description="计算星图节点位置")
    parser.add_argument("--theme", help="仅计算指定 slug 的主题")
    args = parser.parse_args()
    run(target_slug=args.theme)


if __name__ == "__main__":
    main()
