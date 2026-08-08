#!/usr/bin/env python3
"""
为 cocktails 表的 preparation_steps 列批量生成调制步骤。

优先处理 map_nodes 中的鸡尾酒，再处理其余尚无步骤的记录。
使用 DeepSeek API（deepseek-v4-pro + thinking）生成高质量步骤。

用法：
    # 仅处理 map 节点（默认）
    python scripts/generate_preparation_steps.py

    # 处理全部鸡尾酒（map 节点优先）
    python scripts/generate_preparation_steps.py --all

    # 强制重新生成（覆盖已有步骤）
    python scripts/generate_preparation_steps.py --force

    # 测试模式：只跑前 N 条
    python scripts/generate_preparation_steps.py --limit 5

    # 并发数（默认 3）
    python scripts/generate_preparation_steps.py --workers 5
"""
from __future__ import annotations

import argparse
import json
import logging
import os
import sys
import time
from concurrent.futures import ThreadPoolExecutor, as_completed
from typing import Optional

# ── 路径设置：从 scripts/ 找到项目根 ──────────────────────────────── #
SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
PROJECT_ROOT = os.path.dirname(SCRIPT_DIR)
sys.path.insert(0, PROJECT_ROOT)

from openai import OpenAI

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
    datefmt="%H:%M:%S",
)
logger = logging.getLogger(__name__)

# ── DeepSeek 客户端（独立于 Flask，便于脚本单独运行）─────────────────── #
DEEPSEEK_API_KEY = os.environ.get("DEEPSEEK_API_KEY")
if not DEEPSEEK_API_KEY:
    raise SystemExit("请设置环境变量 DEEPSEEK_API_KEY")
DEEPSEEK_BASE_URL = "https://api.deepseek.com"
DEEPSEEK_MODEL = "deepseek-v4-pro"

deepseek_client = OpenAI(
    api_key=DEEPSEEK_API_KEY,
    base_url=DEEPSEEK_BASE_URL,
    timeout=120,
)

# ── System Prompt ─────────────────────────────────────────────────── #
# ── 杯型英文→中文映射（不区分大小写匹配） ────────────────────────── #
GLASS_TYPE_ZH: dict[str, str] = {
    # Old Fashioned / Rocks 系列
    "old fashioned glass": "古典杯",
    "old-fashioned glass": "古典杯",
    "old fashioned": "古典杯",
    "old-fashioned": "古典杯",
    "rocks glass": "古典杯",
    "rocks": "古典杯",
    "double old fashioned glass": "双料古典杯",
    "double rocks glass": "双料古典杯",
    "lowball glass": "古典杯",
    "footed rocks glass": "脚古典杯",
    "etched rocks glass": "蚀刻古典杯",
    "v-shaped rocks glass": "V形古典杯",
    "crystal rocks": "水晶古典杯",
    # Highball / Collins / Tall
    "highball glass": "高球杯",
    "highball": "高球杯",
    "collins glass": "可林杯",
    "collins": "可林杯",
    "tall glass": "高杯",
    "fizz glass": "菲士杯",
    "bamboo highball glass": "竹制高球杯",
    # Martini / Cocktail / Coupe / Nick & Nora
    "martini glass": "马天尼杯",
    "martini": "马天尼杯",
    "cocktail glass": "鸡尾酒杯",
    "coupe glass": "碟形杯",
    "coupe": "碟形杯",
    "egg coupe": "蛋形碟形杯",
    "royal coupette": "皇家碟形杯",
    "nick & nora": "尼克诺拉杯",
    "nick and nora glass": "尼克诺拉杯",
    "nick and nora": "尼克诺拉杯",
    # Margarita / Hurricane / Tiki
    "margarita glass": "玛格丽塔杯",
    "margarita/coupette glass": "玛格丽塔杯",
    "hurricane glass": "飓风杯",
    "tiki glass": "提基杯",
    "tiki cat glass": "提基杯",
    # Champagne / Wine / Port
    "champagne flute": "香槟笛杯",
    "wine glass": "葡萄酒杯",
    "stemless wine glass": "无脚葡萄酒杯",
    "white wine glass": "白葡萄酒杯",
    "port glass": "波特酒杯",
    "copita glass": "科皮塔杯",
    "balloon glass": "气球杯",
    "large balloon glass": "大气球杯",
    # Brandy / Snifter
    "brandy snifter": "白兰地球形杯",
    "snifter": "球形杯",
    "canadian glencairn glass": "格兰凯恩杯",
    # Beer
    "beer glass": "啤酒杯",
    "beer mug": "啤酒马克杯",
    "beer pilsner": "皮尔森啤酒杯",
    "pilsner glass": "皮尔森杯",
    "pint glass": "品脱杯",
    "lager": "拉格杯",
    "shorty beer": "短身啤酒杯",
    # Mug / Cup
    "copper mug": "铜杯",
    "coffee mug": "咖啡马克杯",
    "glass mug": "玻璃马克杯",
    "mug": "马克杯",
    "irish coffee mug": "爱尔兰咖啡杯",
    "irish coffee glass": "爱尔兰咖啡杯",
    "irish coffee cup": "爱尔兰咖啡杯",
    "julep cup": "薄荷朱莉普杯",
    "tin cup": "锡杯",
    "espresso cup": "浓缩咖啡杯",
    "demitasse glass": "小咖啡杯",
    # Shot / Cordial
    "shot glass": "子弹杯",
    "shot": "子弹杯",
    "cordial glass": "利口酒杯",
    "stemmed cordial glass": "高脚利口酒杯",
    "pousse cafe glass": "彩虹酒杯",
    "flip glass": "蛋酒杯",
    # Punch / Goblet / Other
    "punch bowl": "潘趣碗",
    "punch glass": "潘趣杯",
    "goblet": "高脚大杯",
    "tumbler": "平底杯",
    "small tumbler": "小平底杯",
    "pitcher": "壶",
    "jar": "梅森罐",
    "mason jar": "梅森罐",
    "bucket": "冰桶杯",
    "handled glass": "带柄杯",
    "chilled glass": "冰镇杯",
    "smoked glass": "烟熏杯",
    "vintage glass": "复古杯",
    "whiskey glass": "威士忌杯",
    "whiskey sour glass": "威士忌酸杯",
    "8 oz glass": "8盎司杯",
    "pint": "品脱杯",
    "large antique vintage shaker": "古董摇酒壶",
}


def glass_to_zh(glass: str | None) -> str:
    """将英文杯型名转换为中文；未能匹配时返回原值或默认值。"""
    if not glass:
        return "鸡尾酒杯"
    zh = GLASS_TYPE_ZH.get(glass.lower().strip())
    return zh if zh else glass


SYSTEM_PROMPT = """你是专业调酒师助手，专注生成精准的鸡尾酒调制步骤。根据提供的配方信息输出分步指引。严格按以下 JSON Schema 输出，不输出额外文字。

JSON Schema:
{"steps":[{"order":<int,从1开始>,"text":<string,精确操作描述>,"duration_hint":<string|null,如"15秒"，无时间要求填null>}]}

步骤规则：
- 3-7步，每步只做一件事
- 覆盖完整流程：器具准备 → 量取原料 → 混合/注入 → 摇匀/搅拌 → 过滤倒杯 → 装饰/上桌
- 有时间要求的操作必须量化（例如"用力摇晃15秒"、"轻柔搅拌30圈约20秒"）
- 用量数字要与配方一致（直接引用 measure_raw）
- 根据调制手法（摇制/调和/兑制/分层等）选择合适步骤
- 装饰步骤按实际配方决定是否包含（若无装饰原料则省略）"""


def _build_prompt(cocktail: dict, ingredients: list[dict]) -> str:
    """构建传给 LLM 的用户 Prompt，包含足够信息以避免幻觉。"""
    ing_lines = []
    for ing in ingredients:
        name = ing.get("name_zh") or ing.get("name", "")
        measure = ing.get("measure_raw") or "适量"
        abv = ing.get("abv_approx")
        cat = ing.get("category", "")
        is_base = ing.get("is_base_spirit", False)
        abv_str = f" ABV≈{abv}%" if abv else ""
        role_str = "（基酒）" if is_base else f"（{cat}）" if cat else ""
        ing_lines.append(f"  - {name}：{measure}{abv_str}{role_str}")

    name_zh = cocktail.get("name_zh") or cocktail.get("name", "")
    name_en = cocktail.get("name", "")
    glass = glass_to_zh(cocktail.get("glass_type"))
    technique = cocktail.get("technique_primary") or ""
    flavor = cocktail.get("flavor_tags") or []
    abv_level = cocktail.get("abv_level") or "medium"
    difficulty = cocktail.get("difficulty") or 2

    technique_line = f"\n调制手法：{technique}" if technique else ""
    flavor_line = f"风味标签：{', '.join(flavor)}" if flavor else ""

    instructions_ref = ""
    instr_en = cocktail.get("instructions_en") or ""
    if instr_en and len(instr_en) < 500:
        instructions_ref = f"\n原始英文说明（参考，不要直接翻译，用于理解调制逻辑）：{instr_en}"

    return f"""鸡尾酒：{name_zh}（{name_en}）
酒杯：{glass}
酒精度：{abv_level}  难度：{difficulty}/5
{flavor_line}{technique_line}{instructions_ref}

配方原料：
{chr(10).join(ing_lines)}

请根据以上配方信息，生成精确的分步调制指引，按 JSON Schema 输出。"""


def _extract_steps_from_content(content: str) -> Optional[list[dict]]:
    """从模型输出中解析 steps 列表。"""
    text = content.strip()
    if text.startswith("```"):
        lines = text.splitlines()
        text = "\n".join(lines[1:-1] if lines[-1].strip() == "```" else lines[1:])
    start, end = text.find("{"), text.rfind("}")
    if start == -1 or end == -1:
        return None
    raw = json.loads(text[start:end + 1])
    steps = []
    for i, s in enumerate(raw.get("steps") or [], 1):
        if isinstance(s, dict) and s.get("text"):
            steps.append({
                "order": int(s.get("order", i)),
                "text": str(s["text"]),
                "duration_hint": s.get("duration_hint") or None,
            })
    return steps or None


def _call_deepseek(prompt: str, retries: int = 3) -> Optional[list[dict]]:
    """调用 DeepSeek API，返回 steps 列表；失败返回 None。
    前两次使用 thinking 模式，若内容为空则降级为不带 thinking 的调用。
    """
    for attempt in range(retries):
        use_thinking = (attempt < 2)
        try:
            kwargs: dict = {
                "model": DEEPSEEK_MODEL,
                "messages": [
                    {"role": "system", "content": SYSTEM_PROMPT},
                    {"role": "user", "content": prompt},
                ],
                "stream": False,
                "max_tokens": 800,
                "temperature": 0.3,
            }
            if use_thinking:
                kwargs["extra_body"] = {
                    "reasoning_effort": "high",
                    "thinking": {"type": "enabled"},
                }
            response = deepseek_client.chat.completions.create(**kwargs)
            content = response.choices[0].message.content or ""
            if not content.strip():
                logger.warning("Empty content on attempt %d (thinking=%s), retrying…",
                               attempt + 1, use_thinking)
                continue
            steps = _extract_steps_from_content(content)
            if steps:
                return steps
            logger.warning("LLM returned empty steps for attempt %d", attempt + 1)
        except json.JSONDecodeError as e:
            logger.warning("JSON parse error attempt %d: %s", attempt + 1, e)
        except Exception as e:
            logger.warning("API error attempt %d: %s", attempt + 1, e)
            if attempt < retries - 1:
                time.sleep(2 ** attempt)
    return None


def process_cocktail(row: dict) -> tuple[int, bool, str]:
    """
    处理单个鸡尾酒，返回 (cocktail_id, success, message)。
    在独立 Flask app context 中执行，适合多线程。
    """
    from app import create_app
    from app.extensions import db
    from app.models.cocktail import Cocktail

    app = create_app()
    cocktail_id = row["id"]

    with app.app_context():
        cocktail = db.session.get(Cocktail, cocktail_id)
        if not cocktail:
            return cocktail_id, False, "not found"

        prompt = _build_prompt(row, row.get("ingredients", []))
        steps = _call_deepseek(prompt)

        if not steps:
            return cocktail_id, False, "LLM returned no steps"

        cocktail.preparation_steps = steps
        db.session.commit()
        return cocktail_id, True, f"{len(steps)} steps"


def fetch_cocktail_data(app, cocktail_ids: list[int]) -> list[dict]:
    """在 app context 中批量拉取鸡尾酒及原料数据，返回包含 ingredients 的 dict 列表。"""
    from app.extensions import db
    from app.models.cocktail import Cocktail, CocktailIngredient
    from app.models.ingredient import Ingredient

    rows = []
    with app.app_context():
        cocktails = db.session.query(Cocktail).filter(Cocktail.id.in_(cocktail_ids)).all()
        cocktail_map = {c.id: c for c in cocktails}

        for cid in cocktail_ids:
            c = cocktail_map.get(cid)
            if not c:
                continue
            ings_q = (
                db.session.query(CocktailIngredient, Ingredient)
                .join(Ingredient, CocktailIngredient.ingredient_id == Ingredient.id)
                .filter(CocktailIngredient.cocktail_id == cid)
                .order_by(CocktailIngredient.sort_order)
                .all()
            )
            ingredients = []
            for ci, ing in ings_q:
                ingredients.append({
                    "name": ing.name,
                    "name_zh": ing.name_zh,
                    "measure_raw": ci.measure_raw,
                    "category": ing.category,
                    "is_base_spirit": ing.is_base_spirit,
                    "abv_approx": float(ing.abv_approx) if ing.abv_approx else None,
                })
            rows.append({
                "id": c.id,
                "name": c.name,
                "name_zh": c.name_zh,
                "glass_type": c.glass_type,
                "flavor_tags": c.flavor_tags or [],
                "abv_level": c.abv_level,
                "difficulty": c.difficulty,
                "instructions_en": c.instructions_en,
                "technique_primary": getattr(c, "technique_primary", None),
                "ingredients": ingredients,
            })
    return rows


def fix_glass_terms_in_steps():
    """将已生成步骤中残留的英文杯型名替换为中文，并清理替换后产生的冗余。"""
    import re

    # 按英文词长度降序匹配，避免短词覆盖长词（如 "Old Fashioned" 先于 "Old"）
    sorted_keys = sorted(GLASS_TYPE_ZH.keys(), key=len, reverse=True)
    # 构建正则：单词边界匹配，不区分大小写
    patterns = [
        (re.compile(r'(?<![a-zA-Z])' + re.escape(k) + r'(?![a-zA-Z])', re.IGNORECASE), v)
        for k, v in ((k, GLASS_TYPE_ZH[k]) for k in sorted_keys)
    ]

    def _clean(text: str) -> str:
        # 替换英文杯型
        for pat, zh in patterns:
            text = pat.sub(zh, text)
        # 清理替换后产生的重复：
        # "马天尼杯杯" / "马天尼杯 杯" → "马天尼杯"，"高球杯杯" → "高球杯" 等
        text = re.sub(r'([\u4e00-\u9fff]{2,}杯)\s*杯', r'\1', text)
        # "XX杯（XX杯）" → "XX杯"（括号里与外面相同）
        text = re.sub(r'([\u4e00-\u9fff]{2,}杯)\s*（\1）', r'\1', text)
        # "（古典杯）" 独立括注（前面已是中文杯型）保留，但如重复则去掉
        # 清理 "老式杯（古典杯）" → "古典杯"（保留括号内更标准的名称）
        text = re.sub(r'[\u4e00-\u9fff]{1,3}式杯（([\u4e00-\u9fff]+杯)）', r'\1', text)
        return text

    from app import create_app
    app = create_app()
    with app.app_context():
        from app.extensions import db
        from app.models.cocktail import Cocktail

        cocktails = db.session.query(Cocktail).filter(
            Cocktail.preparation_steps.isnot(None)
        ).all()

        updated = 0
        for c in cocktails:
            changed = False
            new_steps = []
            for step in (c.preparation_steps or []):
                text = step.get("text", "")
                new_text = _clean(text)
                if new_text != text:
                    changed = True
                new_steps.append({**step, "text": new_text})
            if changed:
                c.preparation_steps = new_steps
                updated += 1

        db.session.commit()
        logger.info("修复完成：共更新 %d 条鸡尾酒的步骤中的英文杯型名", updated)


def main():
    parser = argparse.ArgumentParser(description="批量生成鸡尾酒调制步骤")
    parser.add_argument("--all", action="store_true", help="处理全部鸡尾酒（map 节点优先）")
    parser.add_argument("--force", action="store_true", help="强制重新生成（覆盖已有步骤）")
    parser.add_argument("--limit", type=int, default=0, help="限制处理数量（0=无限制）")
    parser.add_argument("--workers", type=int, default=3, help="并发线程数（默认3）")
    parser.add_argument("--fix-glass", action="store_true",
                        help="仅修复已有步骤中的英文杯型名，不重新生成")
    args = parser.parse_args()

    if args.fix_glass:
        fix_glass_terms_in_steps()
        return

    from app import create_app
    from app.extensions import db
    from app.models.cocktail import Cocktail
    from app.models.map import MapNode

    app = create_app()
    with app.app_context():
        # 获取 map 节点鸡尾酒 ID（优先处理）
        map_ids = list({
            n.cocktail_id
            for n in db.session.query(MapNode).all()
        })

        if args.all:
            all_ids = [c.id for c in db.session.query(Cocktail.id).all()]
            non_map_ids = [i for i in all_ids if i not in set(map_ids)]
            target_ids = map_ids + non_map_ids
        else:
            target_ids = map_ids

        # 过滤掉已有步骤的（除非 --force）
        if not args.force:
            have_steps = {
                row[0] for row in
                db.session.query(Cocktail.id).filter(
                    Cocktail.id.in_(target_ids),
                    Cocktail.preparation_steps.isnot(None),
                ).all()
            }
            target_ids = [i for i in target_ids if i not in have_steps]
            logger.info("已有步骤跳过 %d 条，剩余待处理 %d 条", len(have_steps), len(target_ids))
        else:
            logger.info("强制模式：处理 %d 条", len(target_ids))

        if args.limit:
            target_ids = target_ids[:args.limit]
            logger.info("Limit 模式：只处理前 %d 条", len(target_ids))

    if not target_ids:
        logger.info("没有需要处理的鸡尾酒，退出。")
        return

    logger.info("开始批量拉取原料数据 (%d 条)…", len(target_ids))
    rows = fetch_cocktail_data(app, target_ids)
    logger.info("数据准备完成，开始调用 DeepSeek（workers=%d）…", args.workers)

    success_count = 0
    fail_count = 0
    total = len(rows)

    # 将 steps 写入 DB 的操作在主线程串行执行（避免 session 冲突）
    # 但 LLM 调用在线程池并发执行
    def call_llm(row: dict) -> tuple[int, Optional[list], str]:
        cid = row["id"]
        name = row.get("name_zh") or row.get("name", "")
        prompt = _build_prompt(row, row.get("ingredients", []))
        steps = _call_deepseek(prompt)
        status = f"{len(steps)} steps" if steps else "FAILED"
        logger.info("[%s] id=%d → %s", name, cid, status)
        return cid, steps, status

    results: list[tuple[int, Optional[list]]] = []
    with ThreadPoolExecutor(max_workers=args.workers) as pool:
        futures = {pool.submit(call_llm, row): row for row in rows}
        done_count = 0
        for future in as_completed(futures):
            cid, steps, status = future.result()
            results.append((cid, steps))
            done_count += 1
            if done_count % 10 == 0:
                logger.info("进度 %d/%d…", done_count, total)

    # 串行写库
    logger.info("LLM 调用完成，开始写入数据库…")
    from app import create_app as _ca
    _app = _ca()
    with _app.app_context():
        from app.extensions import db as _db
        from app.models.cocktail import Cocktail as _C
        for cid, steps in results:
            if not steps:
                fail_count += 1
                continue
            c = _db.session.get(_C, cid)
            if c:
                c.preparation_steps = steps
                success_count += 1
        _db.session.commit()
        logger.info("写库完成。成功=%d 失败=%d 共=%d", success_count, fail_count, total)


if __name__ == "__main__":
    main()
