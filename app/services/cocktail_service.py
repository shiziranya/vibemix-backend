from __future__ import annotations
"""
配方详情服务：联表查询原料状态，生成分步骤调制引导。
原料状态基于 ingredient_family（品类）判断：酒柜存储品类 ID，
配方原料通过 cocktail_ingredients.ingredient_family_id 关联品类。
"""
import json
import re
import uuid

from sqlalchemy import text

from ..extensions import db, get_redis
from ..models.cocktail import Cocktail
from ..utils.errors import CocktailNotFound

_DETAIL_TTL = 3600  # 1 hour


class CocktailService:
    def get_detail(self, cocktail_id: int, user_id: str | None = None) -> dict:
        cache_key = f"cocktail:detail:{cocktail_id}"
        try:
            r = get_redis()
            cached = r.get(cache_key)
            if cached:
                base = json.loads(cached)
                if user_id:
                    base["ingredients"] = self._annotate_ingredient_status(
                        cocktail_id, user_id, base["ingredients"]
                    )
                return base
        except Exception:
            pass

        cocktail = db.session.get(Cocktail, cocktail_id)
        if not cocktail:
            raise CocktailNotFound()

        ingredients = self._get_ingredients(cocktail_id)
        steps = self._parse_steps(cocktail.instructions_zh or cocktail.instructions_en or "")

        result = {
            **cocktail.to_dict(),
            "ingredients": ingredients,
            "steps": steps,
        }

        try:
            r = get_redis()
            r.setex(cache_key, _DETAIL_TTL, json.dumps(result, ensure_ascii=False))
        except Exception:
            pass

        if user_id:
            result["ingredients"] = self._annotate_ingredient_status(
                cocktail_id, user_id, ingredients
            )
        return result

    def get_steps(self, cocktail_id: int) -> list[dict]:
        cocktail = db.session.get(Cocktail, cocktail_id)
        if not cocktail:
            raise CocktailNotFound()
        return self._parse_steps(cocktail.instructions_zh or cocktail.instructions_en or "")

    def search(
        self,
        q: str | None = None,
        category: str | None = None,
        limit: int = 20,
        offset: int = 0,
    ) -> list[dict]:
        query = db.session.query(Cocktail)
        if q:
            like = f"%{q}%"
            query = query.filter(
                db.or_(
                    Cocktail.name.ilike(like),
                    Cocktail.name_zh.ilike(like),
                )
            )
        if category:
            query = query.filter(Cocktail.category == category)

        items = query.order_by(Cocktail.name).offset(offset).limit(limit).all()
        return [c.to_summary() for c in items]

    # ------------------------------------------------------------------ #
    # Internal helpers
    # ------------------------------------------------------------------ #

    def _get_ingredients(self, cocktail_id: int) -> list[dict]:
        """获取配方原料列表，名称优先使用 ingredient_family，状态判断也基于品类。"""
        rows = db.session.execute(
            text(
                """
                SELECT
                    ci.ingredient_id,
                    ci.ingredient_family_id,
                    COALESCE(f.name, i.name)                               AS name,
                    COALESCE(f.name_zh, f.name, i.name_zh, i.name)        AS name_zh,
                    ci.measure_raw,
                    ci.measure_ml,
                    ci.measure_normalized,
                    ci.measure_value,
                    ci.measure_unit,
                    ci.measure_type,
                    COALESCE(f.is_easily_available, i.is_easily_available) AS is_easily_available,
                    COALESCE(f.category, i.category)                       AS category
                FROM cocktail_ingredients ci
                JOIN ingredients i ON i.id = ci.ingredient_id
                LEFT JOIN ingredient_family f ON f.id = ci.ingredient_family_id
                WHERE ci.cocktail_id = :cid
                ORDER BY ci.sort_order
                """
            ),
            {"cid": cocktail_id},
        ).all()

        return [
            {
                "ingredient_id": row.ingredient_id,
                "ingredient_family_id": row.ingredient_family_id,
                "name": row.name,
                "name_zh": row.name_zh,
                "measure_raw": row.measure_raw,
                "measure_ml": float(row.measure_ml) if row.measure_ml else None,
                "measure": row.measure_normalized or row.measure_raw or "适量",  # 优先使用规范化用量
                "measure_value": float(row.measure_value) if row.measure_value else None,
                "measure_unit": row.measure_unit,
                "measure_type": row.measure_type,
                "is_easily_available": row.is_easily_available,
                "category": row.category,
                "status": "unknown",
                "substitute": None,
            }
            for row in rows
        ]

    def _annotate_ingredient_status(
        self, cocktail_id: int, user_id: str, ingredients: list[dict]
    ) -> list[dict]:
        """基于品类（ingredient_family）标注原料是否在酒柜中。"""
        uid = uuid.UUID(user_id)
        cabinet_rows = db.session.execute(
            text("SELECT family_id FROM user_cabinet WHERE user_id = :uid"),
            {"uid": uid},
        ).all()
        cabinet_family_ids = {r[0] for r in cabinet_rows}

        annotated = []
        for ing in ingredients:
            item = dict(ing)
            fid = item.get("ingredient_family_id")
            if fid and fid in cabinet_family_ids:
                item["status"] = "owned"
                item["substitute"] = None
            elif item.get("is_easily_available"):
                item["status"] = "available"
                item["substitute"] = None
            else:
                item["status"] = "missing"
                item["substitute"] = self._find_substitute(fid, item.get("category"))
            annotated.append(item)
        return annotated

    def _find_substitute(
        self, family_id: int | None, category: str | None
    ) -> str | None:
        """在同品类中寻找 is_easily_available=TRUE 的品类作为替代建议。"""
        if not category:
            return None
        row = db.session.execute(
            text(
                """
                SELECT COALESCE(f.name_zh, f.name)
                FROM ingredient_family f
                WHERE f.category = :cat
                  AND f.is_easily_available = TRUE
                  AND (:fid IS NULL OR f.id != :fid)
                LIMIT 1
                """
            ),
            {"cat": category, "fid": family_id},
        ).first()
        if row:
            return f"可用 {row[0]} 代替"
        return None

    def _parse_steps(self, instructions: str) -> list[dict]:
        """Split instruction text into numbered steps."""
        if not instructions:
            return []

        parts = re.split(r"(?:\r?\n)+|(?<=\.)(?=\s*\d+[\.\、])", instructions.strip())
        parts = [p.strip() for p in parts if p.strip()]

        steps = []
        for i, part in enumerate(parts, 1):
            duration_hint = self._extract_duration(part)
            steps.append(
                {
                    "order": i,
                    "text": part,
                    "duration_hint": duration_hint,
                }
            )
        return steps

    def _extract_duration(self, text: str) -> str | None:
        """Extract time hints like '30 seconds', '15秒' from step text."""
        patterns = [
            r"(\d+)\s*秒",
            r"(\d+)\s*分钟",
            r"(\d+)\s*second",
            r"(\d+)\s*minute",
        ]
        for pat in patterns:
            m = re.search(pat, text, re.IGNORECASE)
            if m:
                return m.group(0)
        return None


cocktail_service = CocktailService()
