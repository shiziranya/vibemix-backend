from __future__ import annotations

import json
import uuid

from sqlalchemy import func, text

from ..extensions import db, get_redis
from ..models.cabinet import UserCabinet
from ..models.ingredient_family import IngredientFamily
from ..utils.errors import FamilyAlreadyInCabinet, FamilyNotFound

_STATS_TTL = 300  # 5 minutes


class CabinetService:
    # ── 查酒柜 ───────────────────────────────────────────────────────────────

    def get_cabinet(self, user_id: str) -> list[dict]:
        rows = (
            db.session.query(UserCabinet, IngredientFamily)
            .join(IngredientFamily, IngredientFamily.id == UserCabinet.family_id)
            .filter(UserCabinet.user_id == uuid.UUID(user_id))
            .order_by(IngredientFamily.category, IngredientFamily.name_zh)
            .all()
        )
        cabinet_ids = {uc.family_id for uc, _ in rows}
        return [fam.to_dict(in_cabinet=True) for _, fam in rows]

    # ── 添加品类 ─────────────────────────────────────────────────────────────

    def add_ingredient(self, user_id: str, family_id: int) -> dict:
        fam = db.session.get(IngredientFamily, family_id)
        if not fam:
            raise FamilyNotFound()

        existing = (
            db.session.query(UserCabinet)
            .filter_by(user_id=uuid.UUID(user_id), family_id=family_id)
            .first()
        )
        if existing:
            raise FamilyAlreadyInCabinet()

        entry = UserCabinet(user_id=uuid.UUID(user_id), family_id=family_id)
        db.session.add(entry)
        db.session.commit()

        self._invalidate_stats_cache(user_id)
        stats = self.get_stats(user_id)
        newly = self._count_newly_unlocked(user_id, family_id)

        # 触发星图解锁刷新
        try:
            from ..tasks.map_tasks import refresh_map_unlocked
            refresh_map_unlocked.delay(user_id)
        except Exception:
            pass

        return {**fam.to_dict(in_cabinet=True), "newly_unlocked": newly, **stats}

    # ── 删除品类 ─────────────────────────────────────────────────────────────

    def remove_ingredient(self, user_id: str, family_id: int) -> dict:
        entry = (
            db.session.query(UserCabinet)
            .filter_by(user_id=uuid.UUID(user_id), family_id=family_id)
            .first()
        )
        if entry:
            db.session.delete(entry)
            db.session.commit()
        self._invalidate_stats_cache(user_id)

        try:
            from ..tasks.map_tasks import refresh_map_unlocked
            refresh_map_unlocked.delay(user_id)
        except Exception:
            pass

        return self.get_stats(user_id)

    # ── 统计 ─────────────────────────────────────────────────────────────────

    def get_stats(self, user_id: str) -> dict:
        cache_key = f"cabinet:stats:{user_id}"
        try:
            r = get_redis()
            cached = r.get(cache_key)
            if cached:
                return json.loads(cached)
        except Exception:
            pass
        stats = self._compute_stats(user_id)
        try:
            r = get_redis()
            r.setex(cache_key, _STATS_TTL, json.dumps(stats))
        except Exception:
            pass
        return stats

    def _compute_stats(self, user_id: str) -> dict:
        total = (
            db.session.query(func.count(UserCabinet.id))
            .filter(UserCabinet.user_id == uuid.UUID(user_id))
            .scalar()
        ) or 0

        base_count = (
            db.session.query(func.count(UserCabinet.id))
            .join(IngredientFamily, IngredientFamily.id == UserCabinet.family_id)
            .filter(UserCabinet.user_id == uuid.UUID(user_id), IngredientFamily.is_base_spirit.is_(True))
            .scalar()
        ) or 0

        non_base_count = (
            db.session.query(func.count(UserCabinet.id))
            .join(IngredientFamily, IngredientFamily.id == UserCabinet.family_id)
            .filter(
                UserCabinet.user_id == uuid.UUID(user_id),
                IngredientFamily.is_base_spirit.is_(False),
                IngredientFamily.category.isnot(None),
            )
            .scalar()
        ) or 0

        fids = self._get_user_cabinet_family_ids(user_id)
        unlocked = self._count_unlocked_recipes(fids)

        return {
            "total": total,
            "base_spirit_count": base_count,
            "modifier_count": non_base_count,
            "unlocked_recipe_count": unlocked,
        }

    def _get_user_cabinet_family_ids(self, user_id: str) -> list[int]:
        """返回用户酒柜中所有 ingredient_family ID。"""
        rows = (
            db.session.query(UserCabinet.family_id)
            .filter(UserCabinet.user_id == uuid.UUID(user_id))
            .all()
        )
        return [r.family_id for r in rows]

    def _count_unlocked_recipes(self, cabinet_family_ids: list[int]) -> int:
        """
        可调制配方数量：配方中所有 ingredient_family.is_easily_available=FALSE 的
        原料品类都在用户酒柜（cabinet_family_ids）中，则该配方可调制。
        is_easily_available=TRUE 的品类（果汁/苏打等）视为随时可得。
        """
        if not cabinet_family_ids:
            return 0
        return db.session.execute(
            text("""
                SELECT COUNT(DISTINCT c.id)
                FROM cocktails c
                WHERE NOT EXISTS (
                    SELECT 1
                    FROM cocktail_ingredients ci
                    JOIN ingredient_family f ON ci.ingredient_family_id = f.id
                    WHERE ci.cocktail_id = c.id
                      AND f.is_easily_available = FALSE
                      AND ci.ingredient_family_id != ALL(:fids)
                )
            """),
            {"fids": cabinet_family_ids},
        ).scalar() or 0

    def _count_newly_unlocked(self, user_id: str, new_family_id: int) -> int:
        """新增一个品类后，新解锁的配方数量。"""
        fam = db.session.get(IngredientFamily, new_family_id)
        if not fam:
            return 0
        existing_ids = self._get_user_cabinet_family_ids(user_id)
        before_ids = [fid for fid in existing_ids if fid != new_family_id]
        after_ids  = list(set(existing_ids + [new_family_id]))
        before = self._count_unlocked_recipes(before_ids)
        after  = self._count_unlocked_recipes(after_ids)
        return max(0, after - before)

    # ── 预览解锁 ─────────────────────────────────────────────────────────────

    def preview_unlock(self, user_id: str, family_id: int) -> int:
        fam = db.session.get(IngredientFamily, family_id)
        if not fam:
            raise FamilyNotFound()
        return self._count_newly_unlocked(user_id, family_id)

    # ── 搜索原料 ─────────────────────────────────────────────────────────────

    def search_ingredients(
        self,
        q: str | None = None,
        category: str | None = None,
        family: str | None = None,
        page: int = 1,
        per_page: int = 20,
        user_id: str | None = None,
    ) -> dict:
        from sqlalchemy import or_

        query = db.session.query(IngredientFamily)
        if q:
            query = query.filter(
                or_(
                    IngredientFamily.name.ilike(f"%{q}%"),
                    IngredientFamily.name_zh.ilike(f"%{q}%"),
                )
            )
        if category:
            query = query.filter(IngredientFamily.category == category)
        if family:
            query = query.filter(IngredientFamily.base_spirit_family == family)

        total = query.count()
        items = (
            query
            .order_by(IngredientFamily.is_base_spirit.desc(), IngredientFamily.name_zh)
            .offset((page - 1) * per_page)
            .limit(per_page)
            .all()
        )

        cabinet_ids: set[int] = set()
        if user_id:
            cabinet_ids = set(self._get_user_cabinet_family_ids(user_id))

        return {
            "items": [fam.to_dict(in_cabinet=fam.id in cabinet_ids) for fam in items],
            "total": total,
            "page": page,
            "per_page": per_page,
        }

    # ── 内部 ─────────────────────────────────────────────────────────────────

    def _invalidate_stats_cache(self, user_id: str) -> None:
        try:
            r = get_redis()
            r.delete(f"cabinet:stats:{user_id}")
        except Exception:
            pass


cabinet_service = CabinetService()
