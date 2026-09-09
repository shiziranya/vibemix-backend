from __future__ import annotations

import json
import uuid

from sqlalchemy import func, text

from ..extensions import db, get_redis
from ..models.cabinet import UserCabinet
from ..models.ingredient_family import IngredientFamily
from ..models.user import User
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

        # 更新推荐基酒
        self.update_user_spirit_recommendation(user_id)

        return {**fam.to_dict(in_cabinet=True), "newly_unlocked": newly, **stats}

    # ── 删除品类 ─────────────────────────────────────────────────────────────

    def remove_ingredient(self, user_id: str, family_id: int) -> dict:
        # 计算删除前的可调配方数
        before_ids = self._get_user_cabinet_family_ids(user_id)
        before_count = self._count_unlocked_recipes(before_ids)
        
        entry = (
            db.session.query(UserCabinet)
            .filter_by(user_id=uuid.UUID(user_id), family_id=family_id)
            .first()
        )
        if entry:
            db.session.delete(entry)
            db.session.commit()
        
        # 计算删除后的可调配方数
        after_ids = self._get_user_cabinet_family_ids(user_id)
        after_count = self._count_unlocked_recipes(after_ids)
        recipes_lost = max(0, before_count - after_count)
        
        self._invalidate_stats_cache(user_id)

        try:
            from ..tasks.map_tasks import refresh_map_unlocked
            refresh_map_unlocked.delay(user_id)
        except Exception:
            pass

        # 更新推荐基酒
        self.update_user_spirit_recommendation(user_id)

        stats = self.get_stats(user_id)
        return {**stats, "recipes_lost": recipes_lost}

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
        
        关键逻辑：
        - 只检查 is_easily_available=FALSE 的原料
        - 这些原料必须在用户酒柜中
        - 便利店易购材料（is_easily_available=TRUE）被忽略
        - 空酒柜时，返回只需便利店材料的配方（无需任何购买的材料）
        
        示例：
        - 空酒柜：返回只需便利店材料的配方（如"甜蜜香蕉"只需蜂蜜+牛奶+香蕉）
        - 有材料：返回可用酒柜材料+便利店材料制作的配方
        """
        # 空数组传给 PostgreSQL 的 ALL() 运算符会让条件永远为真
        # 因此空酒柜时会返回所有不含 is_easily_available=FALSE 原料的配方
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
            {"fids": cabinet_family_ids or []},
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

    # ── 推荐基酒 ─────────────────────────────────────────────────────────────

    def calculate_best_spirit_recommendation(self, user_id: str) -> dict | None:
        """
        计算用户添加哪个基酒后能解锁最多的配方数量。
        
        算法：
        1. 获取所有未拥有的基酒品类
        2. 遍历每个基酒，模拟添加后能解锁的配方数量
        3. 返回解锁配方最多的基酒
        
        注意：
        - 只计算 is_easily_available=FALSE 的原料
        - 便利店易购材料（果汁、糖浆等）不影响计算
        
        返回: {"family_id": int, "unlock_count": int, "family": dict} 或 None
        """
        # 获取用户当前酒柜中的品类
        current_family_ids = self._get_user_cabinet_family_ids(user_id)
        
        # 获取所有基酒品类（排除已经在酒柜中的）
        base_spirit_families = (
            db.session.query(IngredientFamily)
            .filter(
                IngredientFamily.is_base_spirit.is_(True),
                ~IngredientFamily.id.in_(current_family_ids) if current_family_ids else True
            )
            .all()
        )
        
        if not base_spirit_families:
            return None
        
        best_family = None
        max_unlock_count = 0
        
        # 遍历每个基酒，计算能解锁的配方数量
        for family in base_spirit_families:
            # 模拟添加该基酒后的酒柜
            simulated_family_ids = current_family_ids + [family.id]
            unlock_count = self._count_unlocked_recipes(simulated_family_ids)
            
            # 计算新增解锁数量
            current_unlock_count = self._count_unlocked_recipes(current_family_ids)
            new_unlock_count = unlock_count - current_unlock_count
            
            if new_unlock_count > max_unlock_count:
                max_unlock_count = new_unlock_count
                best_family = family
        
        if best_family:
            return {
                "family_id": best_family.id,
                "unlock_count": max_unlock_count,
                "family": best_family.to_dict(in_cabinet=False),
            }
        
        return None

    def update_user_spirit_recommendation(self, user_id: str) -> None:
        """
        更新用户表中的推荐基酒信息。
        """
        recommendation = self.calculate_best_spirit_recommendation(user_id)
        
        user = db.session.query(User).filter_by(id=uuid.UUID(user_id)).first()
        if user:
            if recommendation:
                user.recommended_spirit_family_id = recommendation["family_id"]
                user.recommended_spirit_unlock_count = recommendation["unlock_count"]
            else:
                user.recommended_spirit_family_id = None
                user.recommended_spirit_unlock_count = None
            
            db.session.commit()

    def get_user_spirit_recommendation(self, user_id: str) -> dict | None:
        """
        获取用户的推荐基酒信息（从用户表读取）。
        """
        user = db.session.query(User).filter_by(id=uuid.UUID(user_id)).first()
        if not user or not user.recommended_spirit_family_id:
            return None
        
        family = db.session.get(IngredientFamily, user.recommended_spirit_family_id)
        if not family:
            return None
        
        return {
            "family_id": user.recommended_spirit_family_id,
            "unlock_count": user.recommended_spirit_unlock_count,
            "family": family.to_dict(in_cabinet=False),
        }

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
