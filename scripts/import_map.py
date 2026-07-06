#!/usr/bin/env python3
"""Standalone importer for cocktail_map.json (no Flask dependency)."""

from __future__ import annotations

import argparse
import json
import os
import re
import sys

import psycopg2
import psycopg2.extras

THEME_COLORS = {
    "foundation": ("#F4A261", "#E76F51"),
    "tropical": ("#2A9D8F", "#57CC99"),
    "prohibition": ("#6D2B3D", "#C77DFF"),
    "european": ("#264653", "#4FC3F7"),
    "modern": ("#1D3557", "#A8DADC"),
}


def load_db_url() -> str:
    env_path = os.path.join(os.path.dirname(__file__), "..", ".env")
    if os.path.exists(env_path):
        for line in open(env_path, encoding="utf-8"):
            line = line.strip()
            if line.startswith("SUPABASE_DATABASE_URL="):
                return line.split("=", 1)[1].strip()
    return os.environ.get(
        "SUPABASE_DATABASE_URL",
        "postgresql://postgres:postgres123@localhost:5432/tipsy_inspirations",
    )


def slug_from_name(name_en: str) -> str:
    return re.sub(r"[^a-z0-9]+", "_", name_en.lower()).strip("_")


def run_import(filepath: str, replace: bool = False) -> None:
    with open(filepath, encoding="utf-8") as f:
        data = json.load(f)

    conn = psycopg2.connect(load_db_url())
    conn.autocommit = False
    cur = conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor)

    try:
        if replace:
            print("[0] 清空旧数据...")
            cur.execute(
                "TRUNCATE user_theme_progress, user_map_progress, "
                "map_edges, map_nodes, map_themes RESTART IDENTITY CASCADE"
            )

        print("\n[1/4] 导入主题...")
        theme_key_to_id: dict[str, int] = {}
        for i, td in enumerate(data["themes"]):
            key = td["key"]
            colors = THEME_COLORS.get(key, ("#888888", "#AAAAAA"))
            cur.execute(
                """
                INSERT INTO map_themes
                    (slug, name, name_zh, description_zh,
                     color_primary, color_secondary, sort_order,
                     is_active, portal_cocktail_id)
                VALUES (%s, %s, %s, %s, %s, %s, %s, TRUE, %s)
                ON CONFLICT (slug) DO UPDATE SET
                    name = EXCLUDED.name,
                    name_zh = EXCLUDED.name_zh,
                    description_zh = EXCLUDED.description_zh,
                    color_primary = EXCLUDED.color_primary,
                    color_secondary = EXCLUDED.color_secondary,
                    sort_order = EXCLUDED.sort_order,
                    portal_cocktail_id = EXCLUDED.portal_cocktail_id
                RETURNING id
                """,
                (
                    key,
                    td.get("name", key),
                    td.get("name", key),
                    td.get("description"),
                    colors[0],
                    colors[1],
                    i,
                    td.get("portal_cocktail_id"),
                ),
            )
            theme_key_to_id[key] = cur.fetchone()["id"]
            print(f"  ✓ {key} → {td.get('name')}")

        print("\n[2/4] 导入节点...")
        cocktail_id_to_node_id: dict[int, int] = {}
        skipped: list[int] = []
        theme_sort_counter: dict[str, int] = {}

        nodes_data = sorted(
            data["nodes"],
            key=lambda n: (n["theme"], n.get("complexity", 1)),
        )

        for nd in nodes_data:
            theme_id = theme_key_to_id.get(nd["theme"])
            if theme_id is None:
                skipped.append(nd["id"])
                continue

            cur.execute("SELECT id FROM cocktails WHERE id = %s", (nd["id"],))
            if not cur.fetchone():
                print(f"  [WARN] 配方 id={nd['id']} ({nd.get('name_en','')}) 不存在，跳过")
                skipped.append(nd["id"])
                continue

            sort_order = theme_sort_counter.get(nd["theme"], 0)
            theme_sort_counter[nd["theme"]] = sort_order + 1
            node_key = slug_from_name(nd.get("name_en") or nd.get("name") or str(nd["id"]))
            reward_xp = 20 if nd.get("is_boss") else max(5, nd.get("complexity", 1) * 5)

            cur.execute(
                """
                INSERT INTO map_nodes
                    (theme_id, cocktail_id, node_key, display_name_zh,
                     is_entry_node, is_boss, complexity, base_spirits,
                     reward_xp, sort_order)
                VALUES (%s, %s, %s, %s, FALSE, %s, %s, %s, %s, %s)
                ON CONFLICT (cocktail_id) DO UPDATE SET
                    theme_id = EXCLUDED.theme_id,
                    node_key = EXCLUDED.node_key,
                    display_name_zh = EXCLUDED.display_name_zh,
                    is_boss = EXCLUDED.is_boss,
                    complexity = EXCLUDED.complexity,
                    base_spirits = EXCLUDED.base_spirits,
                    reward_xp = EXCLUDED.reward_xp,
                    sort_order = EXCLUDED.sort_order
                RETURNING id
                """,
                (
                    theme_id,
                    nd["id"],
                    node_key,
                    nd.get("name"),
                    nd.get("is_boss", False),
                    nd.get("complexity", 1),
                    nd.get("base_spirits") or [],
                    reward_xp,
                    sort_order,
                ),
            )
            cocktail_id_to_node_id[nd["id"]] = cur.fetchone()["id"]

        print(f"  写入 {len(cocktail_id_to_node_id)} 个节点，跳过 {len(skipped)} 个")

        has_incoming = {rel["to"] for rel in data["relations"]["progression"]}
        entry_ids = [cid for cid in cocktail_id_to_node_id if cid not in has_incoming]
        if entry_ids:
            cur.execute(
                "UPDATE map_nodes SET is_entry_node = TRUE WHERE id = ANY(%s)",
                ([cocktail_id_to_node_id[cid] for cid in entry_ids],),
            )

        print(f"\n[3/4] 入口节点：{len(entry_ids)} 个")
        for cid in entry_ids:
            nd = next(n for n in data["nodes"] if n["id"] == cid)
            print(f"  ★ {nd.get('name_en')} ({nd.get('name')})")

        if replace:
            cur.execute("DELETE FROM map_edges")

        print("\n[4/4] 导入边关系...")
        prog_ok = prog_skip = assoc_ok = assoc_skip = 0

        for rel in data["relations"]["progression"]:
            from_nid = cocktail_id_to_node_id.get(rel["from"])
            to_nid = cocktail_id_to_node_id.get(rel["to"])
            if not from_nid or not to_nid:
                prog_skip += 1
                continue
            cur.execute(
                """
                INSERT INTO map_edges (from_node_id, to_node_id, edge_type, edge_label)
                VALUES (%s, %s, 'progression', NULL)
                ON CONFLICT (from_node_id, to_node_id) DO NOTHING
                """,
                (from_nid, to_nid),
            )
            prog_ok += 1

        for rel in data["relations"]["associations"]:
            src = cocktail_id_to_node_id.get(rel["source"])
            tgt = cocktail_id_to_node_id.get(rel["target"])
            if not src or not tgt:
                assoc_skip += 1
                continue
            label = rel.get("type_name")
            for a, b in [(src, tgt), (tgt, src)]:
                cur.execute(
                    """
                    INSERT INTO map_edges (from_node_id, to_node_id, edge_type, edge_label)
                    VALUES (%s, %s, 'association', %s)
                    ON CONFLICT (from_node_id, to_node_id) DO NOTHING
                    """,
                    (a, b, label),
                )
            assoc_ok += 1

        print(f"  progression 边：{prog_ok} 写入，{prog_skip} 跳过")
        print(f"  association 边：{assoc_ok} 写入（×2 双向），{assoc_skip} 跳过")

        conn.commit()
        print("\n[OK] 导入完成")

        cur.execute(
            """
            SELECT
                (SELECT COUNT(*) FROM map_themes) AS themes,
                (SELECT COUNT(*) FROM map_nodes) AS nodes,
                (SELECT COUNT(*) FROM map_nodes WHERE is_entry_node) AS entry_nodes,
                (SELECT COUNT(*) FROM map_nodes WHERE is_boss) AS boss_nodes,
                (SELECT COUNT(*) FROM map_edges WHERE edge_type='progression') AS prog_edges,
                (SELECT COUNT(*) FROM map_edges WHERE edge_type='association') AS assoc_edges
            """
        )
        row = cur.fetchone()
        print(f"""
  map_themes  : {row['themes']}
  map_nodes   : {row['nodes']}
  入口节点    : {row['entry_nodes']}
  Boss 节点   : {row['boss_nodes']}
  progression : {row['prog_edges']}
  association : {row['assoc_edges']}
""")

    except Exception:
        conn.rollback()
        raise
    finally:
        cur.close()
        conn.close()


def main():
    parser = argparse.ArgumentParser(description="导入 cocktail_map.json")
    parser.add_argument("--file", required=True)
    parser.add_argument(
        "--replace",
        action="store_true",
        help="清空旧地图数据后全量导入",
    )
    args = parser.parse_args()
    if not os.path.exists(args.file):
        print(f"[ERROR] 文件不存在: {args.file}")
        sys.exit(1)
    run_import(args.file, replace=args.replace)


if __name__ == "__main__":
    main()
