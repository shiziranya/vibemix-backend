from __future__ import annotations
"""
推荐服务：整合 SQL 召回 + LLM 精选（选酒+生成步骤）+ 缺料分析，写入推荐历史。
酒柜现在基于 ingredient_family（品类）存储，状态标注同步使用品类 ID 判断。
"""
import json
import uuid
from collections import defaultdict

from sqlalchemy import text

from ..extensions import db, get_redis
from ..models.cocktail import Cocktail
from ..models.recommendation import RecommendationHistory
from ..utils.errors import NoCandidatesFound, SessionNotFound
from .cabinet_service import cabinet_service
from .cocktail_service import cocktail_service
from .llm_service import llm_service
from .matching_service import matching_service

_SESSION_TTL = 1800  # 30 minutes
_session_store: dict = {}  # In-memory fallback when Redis is unavailable


class RecommendService:
    def recommend(self, user_id: str, prefs: dict) -> dict:
        """New recommendation session."""
        session_id = f"sess_{uuid.uuid4().hex[:12]}"
        return self._do_recommend(user_id, prefs, session_id, exclude_ids=[])

    def stream_recommend(self, user_id: str, prefs: dict):
        """New streaming recommendation session.

        Returns (session_id, generator).  The generator yields SSE-ready dicts:
          {"type": "chunk", "text": <str>}          — raw JSON fragment from LLM
          {"type": "done",  "data": <full result>}   — final structured response
          {"type": "error", "message": <str>}        — on unexpected failure
        """
        session_id = f"sess_{uuid.uuid4().hex[:12]}"
        return session_id, self._do_stream_recommend(user_id, prefs, session_id)

    def refresh(self, user_id: str, session_id: str) -> dict:
        """Refresh (换一个) within the same session."""
        session_data = self._load_session(session_id)
        if not session_data:
            raise SessionNotFound()

        prefs = session_data["prefs"]
        exclude_ids = session_data.get("seen_ids", [])
        return self._do_recommend(user_id, prefs, session_id, exclude_ids=exclude_ids)

    def _do_stream_recommend(self, user_id: str, prefs: dict, session_id: str):
        """Two-phase streaming generator.

        Yields structured SSE event dicts in display order:
          {"type": "batch1", "cocktail": {...}, "ai": {...}}
          {"type": "batch2", "ingredients": [...]}
          {"type": "batch3", "steps": [...]}
          {"type": "done"}
          {"type": "error", "message": "..."}
        """
        # ── DB preparation (same as _do_recommend) ───────────────────── #
        try:
            user_family_ids = cabinet_service._get_user_cabinet_family_ids(user_id)
            history_ids = self._get_user_history_ids(user_id)
            candidates = matching_service.recall_candidates(
                user_family_ids=user_family_ids,
                abv_pref=prefs.get("abv_pref", "any"),
                flavor_tags=prefs.get("flavor_tags", []),
                recipe_type=prefs.get("recipe_type", "classic"),
                exclude_ids=[],
                history_ids=history_ids,
                category=prefs.get("category"),
            )
            if not candidates:
                yield {"type": "error", "message": "no_candidates"}
                return

            candidates = self._enrich_candidates_with_ingredients(candidates)
            cabinet_fids = set(user_family_ids)
            candidates = self._tag_ingredient_status_for_llm(candidates, cabinet_fids)
            owned_labels = self._get_owned_ingredient_labels(list(user_family_ids))
            cabinet_family_ids = self._get_cabinet_family_ids(user_id)
        except Exception as e:
            yield {"type": "error", "message": str(e)}
            return

        # ── Two-phase LLM ────────────────────────────────────────────── #
        sel_raw: dict = {}
        llm_ingredients: list = []
        llm_steps: list = []
        cocktail = None

        for phase, payload in llm_service.stream_two_phase(
            candidates, prefs, owned_labels=owned_labels
        ):
            if phase == "error":
                yield {"type": "error", "message": str(payload)}
                return

            if phase == "selection":
                sel_raw = payload
                selected_id = int(sel_raw.get("selected_id") or candidates[0]["id"])

                cocktail = db.session.get(Cocktail, selected_id)
                if not cocktail:
                    cocktail = db.session.get(Cocktail, candidates[0]["id"])

                # ── Batch 1: cocktail card + AI text copy ─────────────── #
                yield {
                    "type": "batch1",
                    "cocktail": cocktail.to_summary(),
                    "ai": {
                        "reason": str(sel_raw.get("reason", "")),
                        "poetic_copy": str(sel_raw.get("poetic_copy", "")),
                        "mood_caption": str(sel_raw.get("mood_caption", "")),
                        "cocktail_name": str(sel_raw.get("cocktail_name", "") or cocktail.name),
                        "cocktail_name_zh": str(
                            sel_raw.get("cocktail_name_zh", "")
                            or cocktail.name_zh
                            or cocktail.name
                        ),
                        "prototype_name": sel_raw.get("prototype_name") or None,
                        "prototype_name_zh": sel_raw.get("prototype_name_zh") or None,
                        "tweaks": sel_raw.get("tweaks") or None,
                    },
                }

            elif phase == "ingredients":
                llm_ingredients = payload
                selected_id = int(sel_raw.get("selected_id") or candidates[0]["id"])
                selected_candidate = next(
                    (c for c in candidates if c["id"] == selected_id), None
                )
                db_ing_by_name: dict[str, dict] = {
                    (ing.get("name_zh") or "").strip(): ing
                    for ing in (selected_candidate or {}).get("ingredient_list", [])
                    if ing.get("name_zh")
                }

                if llm_ingredients:
                    base_ings = self._merge_llm_ingredients(llm_ingredients, db_ing_by_name)
                else:
                    base_ings = list(db_ing_by_name.values()) or (
                        cocktail_service._get_ingredients(cocktail.id) if cocktail else []
                    )

                annotated = self._annotate_ingredients(base_ings, cabinet_family_ids)

                # ── Batch 2: ingredient list ──────────────────────────── #
                yield {"type": "batch2", "ingredients": annotated}

            elif phase == "steps":
                llm_steps = payload

                # ── Batch 3: steps ────────────────────────────────────── #
                yield {"type": "batch3", "steps": llm_steps}

        # ── Save history & session, then signal done ─────────────────── #
        try:
            if cocktail:
                from .llm_service import LLMResult
                llm_result = LLMResult(
                    selected_id=cocktail.id,
                    reason=str(sel_raw.get("reason", "")),
                    poetic_copy=str(sel_raw.get("poetic_copy", "")),
                    mood_caption=str(sel_raw.get("mood_caption", "")),
                    cocktail_name=str(sel_raw.get("cocktail_name", "")),
                    cocktail_name_zh=str(sel_raw.get("cocktail_name_zh", "")),
                    prototype_name=sel_raw.get("prototype_name") or None,
                    prototype_name_zh=sel_raw.get("prototype_name_zh") or None,
                    tweaks=sel_raw.get("tweaks") or None,
                    ingredients=llm_ingredients,
                    steps=llm_steps,
                )
                self._save_history(user_id, session_id, cocktail.id, prefs, llm_result)
                self._save_session(session_id, prefs, [cocktail.id])
        except Exception as e:
            # History save failure should not block the client
            import logging as _log
            _log.getLogger(__name__).error("Failed to save history: %s", e)

        yield {"type": "done"}

    def get_history(self, user_id: str, page: int = 1, per_page: int = 20) -> dict:
        uid = uuid.UUID(user_id)
        total = (
            db.session.query(RecommendationHistory)
            .filter_by(user_id=uid)
            .count()
        )
        rows = (
            db.session.query(RecommendationHistory)
            .filter_by(user_id=uid)
            .order_by(RecommendationHistory.created_at.desc())
            .offset((page - 1) * per_page)
            .limit(per_page)
            .all()
        )
        return {
            "items": [r.to_dict() for r in rows],
            "total": total,
            "page": page,
            "per_page": per_page,
        }

    # ------------------------------------------------------------------ #
    # Core pipeline
    # ------------------------------------------------------------------ #

    def _do_recommend(
        self,
        user_id: str,
        prefs: dict,
        session_id: str,
        exclude_ids: list[int],
    ) -> dict:
        # 1. 获取用户酒柜品类 ID 及历史推荐记录
        user_family_ids = cabinet_service._get_user_cabinet_family_ids(user_id)
        history_ids = self._get_user_history_ids(user_id)

        # 2. SQL 召回：硬过滤（非易购材料全在酒柜）+ 软排序（历史推荐排后）
        candidates = matching_service.recall_candidates(
            user_family_ids=user_family_ids,
            abv_pref=prefs.get("abv_pref", "any"),
            flavor_tags=prefs.get("flavor_tags", []),
            recipe_type=prefs.get("recipe_type", "classic"),
            exclude_ids=exclude_ids,
            history_ids=history_ids,
            category=prefs.get("category"),
        )

        if not candidates:
            raise NoCandidatesFound()

        # 3. 为候选配方补充原料列表（供 LLM 使用）
        candidates = self._enrich_candidates_with_ingredients(candidates)

        # 3b. 为每个候选的原料标注酒柜状态（owned/available/missing），供 LLM 参考
        cabinet_fids = set(user_family_ids)
        candidates = self._tag_ingredient_status_for_llm(candidates, cabinet_fids)

        # 3c. 获取用户已有原料的中文名称，供 LLM 提出替代建议
        owned_labels = self._get_owned_ingredient_labels(list(user_family_ids))

        # 4. LLM 精选 + 生成步骤
        llm_result = llm_service.recommend(candidates, prefs, owned_labels=owned_labels)

        # 5. 获取完整配方记录
        cocktail = db.session.get(Cocktail, llm_result.selected_id)
        if not cocktail:
            cocktail = db.session.get(Cocktail, candidates[0]["id"])

        # 6. 构建带状态标注的原料列表
        cabinet_family_ids = self._get_cabinet_family_ids(user_id)
        selected_candidate = next(
            (c for c in candidates if c["id"] == llm_result.selected_id), None
        )
        db_ing_by_name: dict[str, dict] = {
            (ing.get("name_zh") or "").strip(): ing
            for ing in (selected_candidate or {}).get("ingredient_list", [])
            if ing.get("name_zh")
        }

        if llm_result.ingredients:
            base_ingredients = self._merge_llm_ingredients(llm_result.ingredients, db_ing_by_name)
        else:
            base_ingredients = list(db_ing_by_name.values()) or cocktail_service._get_ingredients(cocktail.id)

        annotated_ingredients = self._annotate_ingredients(base_ingredients, cabinet_family_ids)

        # 7. 写入历史
        self._save_history(user_id, session_id, cocktail.id, prefs, llm_result)

        # 8. 更新 session 缓存
        seen_ids = list(set(exclude_ids + [cocktail.id]))
        self._save_session(session_id, prefs, seen_ids)

        return {
            "session_id": session_id,
            "cocktail": cocktail.to_summary(),
            "ai": {
                "reason": llm_result.reason,
                "poetic_copy": llm_result.poetic_copy,
                "mood_caption": llm_result.mood_caption,
                "cocktail_name": llm_result.cocktail_name or cocktail.name,
                "cocktail_name_zh": llm_result.cocktail_name_zh or cocktail.name_zh or cocktail.name,
                "prototype_name": llm_result.prototype_name,
                "prototype_name_zh": llm_result.prototype_name_zh,
                "tweaks": llm_result.tweaks,
            },
            "ingredients": annotated_ingredients,
            "steps": llm_result.steps,
        }

    def _merge_llm_ingredients(
        self, llm_ings: list[dict], db_ing_by_name: dict[str, dict]
    ) -> list[dict]:
        """Merge LLM-generated ingredient data with DB metadata.

        Matching strategy (in order):
        1. Exact name_zh match against the selected candidate's ingredient list.
        2. DB lookup in ingredient_family by name_zh (for new ingredients in
           original mode, or minor name discrepancies).
        ingredient_family_id and ingredient_id are always resolved by the system,
        never taken from LLM output.
        """
        merged = []
        for llm_ing in llm_ings:
            name_zh = (llm_ing.get("name_zh") or "").strip()
            if not name_zh:
                continue

            # 1. Try exact match in candidate's ingredient list
            db_ing = db_ing_by_name.get(name_zh, {})

            # 2. DB fallback: query ingredient_family by name
            if not db_ing:
                db_ing = self._lookup_ingredient_family_by_name(name_zh)

            merged.append(
                {
                    "ingredient_family_id": db_ing.get("ingredient_family_id"),
                    "ingredient_id": db_ing.get("ingredient_id"),
                    "name": db_ing.get("name", name_zh),
                    "name_zh": name_zh,
                    "measure_raw": llm_ing.get("measure_raw") or db_ing.get("measure_raw"),
                    "measure_ml": db_ing.get("measure_ml"),
                    "is_easily_available": db_ing.get("is_easily_available", False),
                    "category": db_ing.get("category"),
                    "note": llm_ing.get("note"),
                    "status": "unknown",
                    "substitute": None,
                }
            )
        return merged

    def _lookup_ingredient_family_by_name(self, name_zh: str) -> dict:
        """Query ingredient_family table by Chinese name, return a dict compatible
        with the ingredient_list structure, or empty dict if not found."""
        if not name_zh:
            return {}
        row = db.session.execute(
            text(
                """
                SELECT id AS ingredient_family_id,
                       NULL::integer AS ingredient_id,
                       name,
                       name_zh,
                       is_easily_available,
                       category,
                       NULL::numeric AS measure_ml
                FROM ingredient_family
                WHERE name_zh = :name
                   OR name ILIKE :name
                LIMIT 1
                """
            ),
            {"name": name_zh},
        ).mappings().first()
        return dict(row) if row else {}

    def _enrich_candidates_with_ingredients(self, candidates: list[dict]) -> list[dict]:
        """批量获取候选配方的完整原料列表（含 ingredient_family_id），供 LLM 使用。"""
        if not candidates:
            return candidates

        cocktail_ids = [c["id"] for c in candidates]
        rows = db.session.execute(
            text(
                """
                SELECT ci.cocktail_id,
                       ci.ingredient_id,
                       ci.ingredient_family_id,
                       COALESCE(f.name, i.name)                               AS name,
                       COALESCE(f.name_zh, f.name, i.name_zh, i.name)        AS name_zh,
                       ci.measure_raw,
                       ci.measure_ml,
                       COALESCE(f.is_easily_available, i.is_easily_available) AS is_easily_available,
                       COALESCE(f.category, i.category)                       AS category
                FROM cocktail_ingredients ci
                JOIN ingredients i ON i.id = ci.ingredient_id
                LEFT JOIN ingredient_family f ON f.id = ci.ingredient_family_id
                WHERE ci.cocktail_id = ANY(:ids)
                ORDER BY ci.cocktail_id, ci.sort_order
                """
            ),
            {"ids": cocktail_ids},
        ).all()

        ing_map: dict[int, list[dict]] = defaultdict(list)
        for row in rows:
            ing_map[row.cocktail_id].append(
                {
                    "ingredient_id": row.ingredient_id,
                    "ingredient_family_id": row.ingredient_family_id,
                    "name": row.name,
                    "name_zh": row.name_zh,
                    "measure_raw": row.measure_raw,
                    "measure_ml": float(row.measure_ml) if row.measure_ml else None,
                    "is_easily_available": row.is_easily_available,
                    "category": row.category,
                    "status": "unknown",
                    "substitute": None,
                }
            )

        return [
            {**c, "ingredient_list": ing_map.get(c["id"], [])}
            for c in candidates
        ]

    def _tag_ingredient_status_for_llm(
        self, candidates: list[dict], cabinet_fids: set[int]
    ) -> list[dict]:
        """给每个候选配方的原料加 llm_status 字段（owned/available/missing），
        不影响后续 _annotate_ingredients 的逻辑，仅用于构建 LLM prompt。"""
        for c in candidates:
            for ing in c.get("ingredient_list", []):
                fid = ing.get("ingredient_family_id")
                if fid and fid in cabinet_fids:
                    ing["llm_status"] = "owned"
                elif ing.get("is_easily_available"):
                    ing["llm_status"] = "available"
                else:
                    ing["llm_status"] = "missing"
        return candidates

    def _get_owned_ingredient_labels(self, family_ids: list[int]) -> list[str]:
        """返回用户酒柜中所有品类的中文名称列表，格式：'朗姆酒（烈酒）'。"""
        if not family_ids:
            return []
        rows = db.session.execute(
            text(
                "SELECT COALESCE(name_zh, name) AS label, category "
                "FROM ingredient_family WHERE id = ANY(:ids) ORDER BY category, name_zh"
            ),
            {"ids": family_ids},
        ).all()
        return [
            f"{r.label}（{r.category}）" if r.category else r.label
            for r in rows
        ]

    def _get_cabinet_family_ids(self, user_id: str) -> set[int]:
        """返回用户酒柜中所有品类 ID。"""
        uid = uuid.UUID(user_id)
        rows = db.session.execute(
            text("SELECT family_id FROM user_cabinet WHERE user_id = :uid"),
            {"uid": uid},
        ).all()
        return {r[0] for r in rows}

    def _get_user_history_ids(self, user_id: str, limit: int = 50) -> list[int]:
        """返回用户最近推荐过的鸡尾酒 ID 列表（去重，按时间倒序，最多 limit 条）。"""
        uid = uuid.UUID(user_id)
        rows = db.session.execute(
            text(
                """
                SELECT cocktail_id
                FROM recommendation_history
                WHERE user_id = :uid AND cocktail_id IS NOT NULL
                ORDER BY created_at DESC
                LIMIT :limit
                """
            ),
            {"uid": uid, "limit": limit},
        ).all()
        seen: set[int] = set()
        result: list[int] = []
        for r in rows:
            if r[0] not in seen:
                seen.add(r[0])
                result.append(r[0])
        return result

    def _annotate_ingredients(
        self, ingredients: list[dict], cabinet_family_ids: set[int]
    ) -> list[dict]:
        """基于品类 ID 标注原料的酒柜状态（owned / available / missing）。"""
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
                item["substitute"] = cocktail_service._find_substitute(
                    fid, item.get("category")
                )
            annotated.append(item)
        return annotated

    def _save_history(
        self,
        user_id: str,
        session_id: str,
        cocktail_id: int,
        prefs: dict,
        llm_result,
    ) -> None:
        record = RecommendationHistory(
            user_id=uuid.UUID(user_id),
            session_id=session_id,
            cocktail_id=cocktail_id,
            mood_tags=prefs.get("mood_tags"),
            abv_pref=prefs.get("abv_pref"),
            flavor_tags=prefs.get("flavor_tags"),
            recipe_type=prefs.get("recipe_type"),
            category=prefs.get("category"),
            free_text=prefs.get("free_text"),
            cocktail_name=llm_result.cocktail_name or None,
            cocktail_name_zh=llm_result.cocktail_name_zh or None,
            prototype_name=llm_result.prototype_name,
            prototype_name_zh=llm_result.prototype_name_zh,
            ai_reason=llm_result.reason,
            ai_poetic=llm_result.poetic_copy,
            ai_tweaks=llm_result.tweaks,
            ai_ingredients=llm_result.ingredients or None,
            ai_steps=llm_result.steps or None,
        )
        db.session.add(record)
        db.session.commit()

    # ------------------------------------------------------------------ #
    # Session cache (Redis with DB fallback)
    # ------------------------------------------------------------------ #

    def _save_session(
        self, session_id: str, prefs: dict, seen_ids: list[int]
    ) -> None:
        data = json.dumps({"prefs": prefs, "seen_ids": seen_ids}, ensure_ascii=False)
        try:
            r = get_redis()
            r.setex(f"recommend:session:{session_id}", _SESSION_TTL, data)
            return
        except Exception:
            pass
        _session_store[session_id] = data

    def _load_session(self, session_id: str) -> dict | None:
        try:
            r = get_redis()
            raw = r.get(f"recommend:session:{session_id}")
            if raw:
                return json.loads(raw)
        except Exception:
            pass
        raw = _session_store.get(session_id)
        if raw:
            return json.loads(raw)
        row = (
            db.session.query(RecommendationHistory)
            .filter_by(session_id=session_id)
            .order_by(RecommendationHistory.created_at.desc())
            .first()
        )
        if row:
            seen_ids = (
                db.session.query(RecommendationHistory.cocktail_id)
                .filter_by(session_id=session_id)
                .filter(RecommendationHistory.cocktail_id.isnot(None))
                .all()
            )
            return {
                "prefs": {
                    "mood_tags": row.mood_tags or [],
                    "abv_pref": row.abv_pref or "any",
                    "flavor_tags": row.flavor_tags or [],
                    "recipe_type": row.recipe_type or "classic",
                    "category": row.category,
                    "free_text": row.free_text or "",
                },
                "seen_ids": [r[0] for r in seen_ids],
            }
        return None


recommend_service = RecommendService()
