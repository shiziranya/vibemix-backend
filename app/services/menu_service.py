from __future__ import annotations

import uuid
from datetime import date, datetime, timedelta
from decimal import Decimal
from typing import Optional

from sqlalchemy import and_, func, or_

from ..extensions import db
from ..models.cabinet import UserCabinet
from ..models.cocktail import Cocktail, CocktailIngredient
from ..models.ingredient import Ingredient
from ..models.ingredient_family import IngredientFamily
from ..models.saved_cocktail import UserSavedCocktail
from ..utils.errors import AppError, CocktailNotFound


class MenuService:
    """酒单服务：管理用户的收藏夹和今日酒单"""

    # ── 收藏夹管理 ───────────────────────────────────────────────────────────

    def add_to_favorites(
        self,
        user_id: str,
        cocktail_id: int,
        note: Optional[str] = None,
        add_to_today: bool = False,
        recommendation_id: Optional[int] = None,
    ) -> dict:
        """
        添加鸡尾酒到收藏夹
        
        Args:
            user_id: 用户ID
            cocktail_id: 鸡尾酒ID
            note: 个人笔记
            add_to_today: 是否同时添加到今日酒单
            recommendation_id: 推荐记录ID（如果来自LLM推荐）
            
        Returns:
            保存的鸡尾酒信息
        """
        # 检查鸡尾酒是否存在
        cocktail = db.session.get(Cocktail, cocktail_id)
        if not cocktail:
            raise CocktailNotFound()

        user_uuid = uuid.UUID(user_id)

        # 检查是否已存在
        existing = (
            db.session.query(UserSavedCocktail)
            .filter_by(user_id=user_uuid, cocktail_id=cocktail_id)
            .first()
        )

        if existing:
            raise AppError(4091, "该鸡尾酒已在收藏夹中", 409)

        # 创建收藏记录
        saved = UserSavedCocktail(
            user_id=user_uuid,
            cocktail_id=cocktail_id,
            personal_note=note,
            is_in_today=add_to_today,
            plan_date=date.today() if add_to_today else None,
            recommendation_id=recommendation_id,
        )

        db.session.add(saved)
        db.session.commit()

        return self._build_saved_cocktail_response(saved, cocktail)

    def get_favorites(
        self,
        user_id: str,
        exclude_today: bool = False,
        sort_by: str = "added_at",
    ) -> list[dict]:
        """
        获取收藏夹列表
        
        Args:
            user_id: 用户ID
            exclude_today: 是否排除今日酒单中的
            sort_by: 排序方式 (added_at, name, difficulty)
            
        Returns:
            收藏的鸡尾酒列表
        """
        user_uuid = uuid.UUID(user_id)

        query = (
            db.session.query(UserSavedCocktail, Cocktail)
            .join(Cocktail, Cocktail.id == UserSavedCocktail.cocktail_id)
            .filter(UserSavedCocktail.user_id == user_uuid)
        )

        if exclude_today:
            query = query.filter(UserSavedCocktail.is_in_today == False)

        # 排序
        if sort_by == "name":
            query = query.order_by(Cocktail.name_zh)
        elif sort_by == "difficulty":
            query = query.order_by(Cocktail.difficulty)
        else:  # added_at
            query = query.order_by(UserSavedCocktail.added_at.desc())

        results = query.all()

        return [
            self._build_saved_cocktail_response(saved, cocktail)
            for saved, cocktail in results
        ]

    def remove_from_favorites(self, user_id: str, saved_id: int) -> bool:
        """
        从收藏夹移除（会同时从今日酒单移除）
        
        Args:
            user_id: 用户ID
            saved_id: 保存记录ID
            
        Returns:
            是否删除成功
        """
        user_uuid = uuid.UUID(user_id)

        saved = (
            db.session.query(UserSavedCocktail)
            .filter_by(id=saved_id, user_id=user_uuid)
            .first()
        )

        if not saved:
            return False

        db.session.delete(saved)
        db.session.commit()
        return True

    # ── 今日酒单管理 ─────────────────────────────────────────────────────────

    def add_to_today(
        self,
        user_id: str,
        cocktail_id: int,
        note: Optional[str] = None,
        recommendation_id: Optional[int] = None,
    ) -> dict:
        """
        添加鸡尾酒到今日酒单（如果不在收藏夹，会先加入收藏夹）
        
        Args:
            user_id: 用户ID
            cocktail_id: 鸡尾酒ID
            note: 个人笔记
            recommendation_id: 推荐记录ID（如果来自LLM推荐）
            
        Returns:
            保存的鸡尾酒信息
        """
        user_uuid = uuid.UUID(user_id)

        # 检查是否已在收藏夹
        saved = (
            db.session.query(UserSavedCocktail)
            .filter_by(user_id=user_uuid, cocktail_id=cocktail_id)
            .first()
        )

        if saved:
            # 已在收藏夹，更新为今日酒单
            saved.is_in_today = True
            saved.plan_date = date.today()
            if note:
                saved.personal_note = note
            # 如果提供了 recommendation_id 且当前为空，则更新
            if recommendation_id and not saved.recommendation_id:
                saved.recommendation_id = recommendation_id
        else:
            # 不在收藏夹，直接添加
            return self.add_to_favorites(user_id, cocktail_id, note, add_to_today=True, recommendation_id=recommendation_id)

        db.session.commit()

        cocktail = db.session.get(Cocktail, cocktail_id)
        return self._build_saved_cocktail_response(saved, cocktail)

    def get_today_menu(
        self,
        user_id: str,
        target_date: Optional[date] = None,
    ) -> dict:
        """
        获取今日酒单
        
        Args:
            user_id: 用户ID
            target_date: 目标日期，默认今天
            
        Returns:
            今日酒单数据
        """
        if target_date is None:
            target_date = date.today()

        user_uuid = uuid.UUID(user_id)

        # 查询今日酒单
        results = (
            db.session.query(UserSavedCocktail, Cocktail)
            .join(Cocktail, Cocktail.id == UserSavedCocktail.cocktail_id)
            .filter(
                UserSavedCocktail.user_id == user_uuid,
                UserSavedCocktail.is_in_today == True,
            )
            .order_by(
                UserSavedCocktail.priority.desc(),
                UserSavedCocktail.added_at.desc(),
            )
            .all()
        )

        cocktails = [
            self._build_saved_cocktail_response(saved, cocktail)
            for saved, cocktail in results
        ]

        # 统计缺失材料
        total_missing = self._count_missing_ingredients(user_id, [c.id for _, c in results])

        return {
            "date": target_date.isoformat(),
            "count": len(cocktails),
            "cocktails": cocktails,
            "missing_ingredients_count": total_missing,
        }

    def remove_from_today(self, user_id: str, saved_id: int) -> bool:
        """
        从今日酒单移除（保留在收藏夹）
        
        Args:
            user_id: 用户ID
            saved_id: 保存记录ID
            
        Returns:
            是否更新成功
        """
        user_uuid = uuid.UUID(user_id)

        saved = (
            db.session.query(UserSavedCocktail)
            .filter_by(id=saved_id, user_id=user_uuid)
            .first()
        )

        if not saved:
            return False

        saved.is_in_today = False
        saved.plan_date = None
        db.session.commit()
        return True

    def update_note(self, user_id: str, saved_id: int, note: str) -> bool:
        """
        更新个人笔记
        
        Args:
            user_id: 用户ID
            saved_id: 保存记录ID
            note: 新笔记内容
            
        Returns:
            是否更新成功
        """
        user_uuid = uuid.UUID(user_id)

        saved = (
            db.session.query(UserSavedCocktail)
            .filter_by(id=saved_id, user_id=user_uuid)
            .first()
        )

        if not saved:
            return False

        saved.personal_note = note
        db.session.commit()
        return True

    def update_priority(self, user_id: str, saved_id: int, priority: int) -> bool:
        """
        更新优先级
        
        Args:
            user_id: 用户ID
            saved_id: 保存记录ID
            priority: 新优先级
            
        Returns:
            是否更新成功
        """
        user_uuid = uuid.UUID(user_id)

        saved = (
            db.session.query(UserSavedCocktail)
            .filter_by(id=saved_id, user_id=user_uuid)
            .first()
        )

        if not saved:
            return False

        saved.priority = priority
        db.session.commit()
        return True

    # ── 购物清单 ─────────────────────────────────────────────────────────────

    def generate_shopping_list(
        self,
        user_id: str,
        target_date: Optional[date] = None,
    ) -> dict:
        """
        生成购物清单（基于今日酒单）
        
        Args:
            user_id: 用户ID
            target_date: 目标日期，默认今天
            
        Returns:
            购物清单数据
        """
        if target_date is None:
            target_date = date.today()

        user_uuid = uuid.UUID(user_id)

        # 获取今日酒单的鸡尾酒
        saved_cocktails = (
            db.session.query(UserSavedCocktail)
            .filter(
                UserSavedCocktail.user_id == user_uuid,
                UserSavedCocktail.is_in_today == True,
            )
            .all()
        )

        if not saved_cocktails:
            return {
                "date": target_date.isoformat(),
                "cocktails": [],
                "have": [],
                "need": [],
                "total_missing": 0,
            }

        cocktail_ids = [s.cocktail_id for s in saved_cocktails]

        # 获取所有需要的材料
        ingredients_needed = self._aggregate_ingredients(cocktail_ids)

        # 获取用户酒柜
        user_cabinet_ids = self._get_user_cabinet_ids(user_id)

        # 分类：已有和需要购买
        have_list = []
        need_list = []

        for family_id, info in ingredients_needed.items():
            item = {
                "family_id": family_id,
                "name_zh": info["name_zh"],
                "name_en": info["name_en"],
                "category": info["category"],
                "total_ml": float(info["total_ml"]) if info["total_ml"] else None,
                "cocktails": info["cocktails"],
            }

            if family_id in user_cabinet_ids:
                have_list.append(item)
            else:
                need_list.append(item)

        # 获取鸡尾酒名称
        cocktails = (
            db.session.query(Cocktail)
            .filter(Cocktail.id.in_(cocktail_ids))
            .all()
        )
        cocktail_names = [c.name_zh or c.name for c in cocktails]

        return {
            "date": target_date.isoformat(),
            "cocktails": cocktail_names,
            "have": have_list,
            "need": need_list,
            "total_missing": len(need_list),
        }

    # ── 批量操作 ─────────────────────────────────────────────────────────────

    def batch_add_to_today(self, user_id: str, saved_ids: list[int]) -> dict:
        """批量添加到今日酒单"""
        user_uuid = uuid.UUID(user_id)

        updated = (
            db.session.query(UserSavedCocktail)
            .filter(
                UserSavedCocktail.id.in_(saved_ids),
                UserSavedCocktail.user_id == user_uuid,
            )
            .update(
                {
                    "is_in_today": True,
                    "plan_date": date.today(),
                },
                synchronize_session=False,
            )
        )

        db.session.commit()
        return {"updated": updated}

    def batch_remove_from_today(self, user_id: str, saved_ids: list[int]) -> dict:
        """批量从今日酒单移除"""
        user_uuid = uuid.UUID(user_id)

        updated = (
            db.session.query(UserSavedCocktail)
            .filter(
                UserSavedCocktail.id.in_(saved_ids),
                UserSavedCocktail.user_id == user_uuid,
            )
            .update(
                {"is_in_today": False, "plan_date": None},
                synchronize_session=False,
            )
        )

        db.session.commit()
        return {"updated": updated}

    def batch_delete(self, user_id: str, saved_ids: list[int]) -> dict:
        """批量删除"""
        user_uuid = uuid.UUID(user_id)

        deleted = (
            db.session.query(UserSavedCocktail)
            .filter(
                UserSavedCocktail.id.in_(saved_ids),
                UserSavedCocktail.user_id == user_uuid,
            )
            .delete(synchronize_session=False)
        )

        db.session.commit()
        return {"deleted": deleted}

    # ── 自动清理 ─────────────────────────────────────────────────────────────

    def cleanup_expired_today_menu(self, days_ago: int = 1) -> int:
        """
        清理过期的今日酒单（定时任务调用）
        
        Args:
            days_ago: 清理几天前的，默认1天
            
        Returns:
            清理的记录数
        """
        cutoff_date = date.today() - timedelta(days=days_ago)

        # 策略：将过期的今日酒单标记为非今日（保留在收藏夹）
        updated = (
            db.session.query(UserSavedCocktail)
            .filter(
                UserSavedCocktail.is_in_today == True,
                UserSavedCocktail.plan_date < cutoff_date,
            )
            .update(
                {"is_in_today": False, "plan_date": None},
                synchronize_session=False,
            )
        )

        db.session.commit()
        return updated

    # ── 辅助方法 ─────────────────────────────────────────────────────────────

    def _build_saved_cocktail_response(
        self,
        saved: UserSavedCocktail,
        cocktail: Cocktail,
    ) -> dict:
        """构建返回数据"""
        return {
            "saved_id": saved.id,
            "is_in_today": saved.is_in_today,
            "plan_date": saved.plan_date.isoformat() if saved.plan_date else None,
            "priority": saved.priority,
            "personal_note": saved.personal_note,
            "added_at": saved.added_at.isoformat() if saved.added_at else None,
            "recommendation_id": saved.recommendation_id,
            "cocktail": cocktail.to_summary(translate_enums=True),
        }

    def _count_missing_ingredients(self, user_id: str, cocktail_ids: list[int]) -> int:
        """统计缺失材料数量"""
        if not cocktail_ids:
            return 0

        # 获取所有需要的材料品类
        needed_families = set()
        for cid in cocktail_ids:
            ingredients = (
                db.session.query(CocktailIngredient)
                .join(Ingredient)
                .filter(CocktailIngredient.cocktail_id == cid)
                .all()
            )
            for ing in ingredients:
                ingredient = db.session.get(Ingredient, ing.ingredient_id)
                if ingredient and ingredient.ingredient_family_id:
                    needed_families.add(ingredient.ingredient_family_id)

        # 获取用户已有的
        user_cabinet_ids = self._get_user_cabinet_ids(user_id)

        # 计算缺失数量
        missing = needed_families - user_cabinet_ids
        return len(missing)

    def _aggregate_ingredients(self, cocktail_ids: list[int]) -> dict:
        """汇总材料清单"""
        ingredients_map = {}

        for cid in cocktail_ids:
            cocktail = db.session.get(Cocktail, cid)
            cocktail_name = cocktail.name_zh or cocktail.name if cocktail else "Unknown"

            ingredients = (
                db.session.query(CocktailIngredient, Ingredient, IngredientFamily)
                .join(Ingredient, Ingredient.id == CocktailIngredient.ingredient_id)
                .join(IngredientFamily, IngredientFamily.id == Ingredient.ingredient_family_id)
                .filter(CocktailIngredient.cocktail_id == cid)
                .all()
            )

            for ci, ing, fam in ingredients:
                if fam.id not in ingredients_map:
                    ingredients_map[fam.id] = {
                        "name_zh": fam.name_zh,
                        "name_en": fam.name,
                        "category": fam.category,
                        "total_ml": Decimal(0),
                        "cocktails": [],
                    }

                if ci.measure_ml:
                    ingredients_map[fam.id]["total_ml"] += ci.measure_ml

                if cocktail_name not in ingredients_map[fam.id]["cocktails"]:
                    ingredients_map[fam.id]["cocktails"].append(cocktail_name)

        return ingredients_map

    def _get_user_cabinet_ids(self, user_id: str) -> set[int]:
        """获取用户酒柜的材料ID集合"""
        user_uuid = uuid.UUID(user_id)
        cabinet = (
            db.session.query(UserCabinet.family_id)
            .filter(UserCabinet.user_id == user_uuid)
            .all()
        )
        return {c.family_id for c in cabinet}


# 全局单例
menu_service = MenuService()
