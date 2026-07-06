from __future__ import annotations
"""
SQL 召回层：根据用户酒柜和偏好过滤候选配方。

硬过滤：配方中所有非 is_easily_available 的原料，其 ingredient_family_id 必须
在用户酒柜中，确保用户仅需酒柜现有材料 + 便利店可购材料即可完成调制。

软排序：用户历史推荐过的配方会排在候选列表末尾（标记 is_previously_recommended），
供 LLM 优先选择新配方。

降级策略：候选集 < 10 时依次放宽 abv_pref → flavor_tags。
"""
from sqlalchemy import text

from ..extensions import db


class MatchingService:
    MIN_CANDIDATES = 10
    DEFAULT_LIMIT = 20

    def recall_candidates(
        self,
        user_family_ids: list[int],
        abv_pref: str,
        flavor_tags: list[str],
        recipe_type: str,
        exclude_ids: list[int],
        history_ids: list[int] | None = None,
        category: str | None = None,
        limit: int = DEFAULT_LIMIT,
    ) -> list[dict]:
        if not user_family_ids:
            return []

        # 降级策略：先放宽 abv_pref，再放宽 flavor_tags
        relaxation_levels = [
            (True, True),    # abv_on, flavor_on
            (False, True),   # 放宽 abv_pref
            (False, False),  # 放宽 flavor_tags
        ]

        candidates: list[dict] = []
        for use_abv, use_flavor in relaxation_levels:
            candidates = self._query(
                user_family_ids=user_family_ids,
                abv_pref=abv_pref if use_abv else "any",
                flavor_tags=flavor_tags if use_flavor else [],
                exclude_ids=exclude_ids,
                history_ids=history_ids or [],
                category=category,
                limit=limit,
            )
            if len(candidates) >= self.MIN_CANDIDATES:
                break

        return candidates

    def _query(
        self,
        user_family_ids: list[int],
        abv_pref: str,
        flavor_tags: list[str],
        exclude_ids: list[int],
        history_ids: list[int],
        limit: int,
        category: str | None = None,
    ) -> list[dict]:
        # 核心硬过滤：配方中所有非 is_easily_available 原料的 ingredient_family_id
        # 必须在用户酒柜中，否则排除该配方
        conditions = [
            """NOT EXISTS (
                SELECT 1
                FROM cocktail_ingredients ci2
                JOIN ingredients i2 ON i2.id = ci2.ingredient_id
                LEFT JOIN ingredient_family f2 ON f2.id = ci2.ingredient_family_id
                WHERE ci2.cocktail_id = c.id
                  AND COALESCE(f2.is_easily_available, i2.is_easily_available, FALSE) = FALSE
                  AND (
                      ci2.ingredient_family_id IS NULL
                      OR ci2.ingredient_family_id != ALL(:user_family_ids)
                  )
            )"""
        ]
        # sentinel: PostgreSQL 无法推断空数组类型，用 -1 代替空列表
        params: dict = {
            "user_family_ids": user_family_ids,
            "history_ids": history_ids if history_ids else [-1],
            "limit": limit,
        }

        if abv_pref and abv_pref != "any":
            conditions.append("c.abv_level = :abv_pref")
            params["abv_pref"] = abv_pref

        if flavor_tags:
            conditions.append("c.flavor_tags && :flavor_tags")
            params["flavor_tags"] = flavor_tags

        if exclude_ids:
            conditions.append("c.id != ALL(:exclude_ids)")
            params["exclude_ids"] = exclude_ids

        if category:
            conditions.append("c.category = :category")
            params["category"] = category

        where_clause = " AND ".join(conditions)

        sql = text(
            f"""
            SELECT
                c.id,
                c.name,
                c.name_zh,
                c.flavor_tags,
                c.abv_level,
                c.difficulty,
                c.image_url,
                c.non_available_ingredient_count AS missing_count,
                (c.id = ANY(:history_ids))        AS is_previously_recommended
            FROM cocktails c
            WHERE {where_clause}
            ORDER BY
                (c.id = ANY(:history_ids)) ASC,
                c.non_available_ingredient_count ASC,
                RANDOM()
            LIMIT :limit
            """
        )

        rows = db.session.execute(sql, params).mappings().all()
        return [dict(r) for r in rows]

    def get_base_spirit_names(self, family_ids: list[int]) -> list[str]:
        """Return name_zh list for given ingredient_family ids."""
        if not family_ids:
            return []
        sql = text(
            "SELECT COALESCE(name_zh, name) AS label FROM ingredient_family WHERE id = ANY(:ids)"
        )
        rows = db.session.execute(sql, {"ids": family_ids}).all()
        return [r[0] for r in rows]


matching_service = MatchingService()
