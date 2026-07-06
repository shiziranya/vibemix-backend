from __future__ import annotations
"""
豆包 LLM 服务：封装推荐调用。
包含超时降级、JSON 解析失败重试、限流退避等容错逻辑。

普通接口：单次调用完成选酒 + 原料 + 步骤。
流式接口：两阶段调用
  Phase 1 (约 5-8s)：选酒 + 文案（selected_id / reason / poetic_copy / mood_caption / tweaks）
  Phase 2 (约 10s)：原料清单 + 调制步骤（聚焦，max_tokens 更小）
两种模式：classic（经典）/ original（原创特调）。
"""
import json
import logging
import time
from dataclasses import dataclass, field
from typing import Generator

from flask import current_app
from openai import OpenAI, RateLimitError, APITimeoutError, APIConnectionError

logger = logging.getLogger(__name__)

# ------------------------------------------------------------------ #
# Single-call prompts  (used by non-streaming recommend())
# ------------------------------------------------------------------ #
CLASSIC_SYSTEM_PROMPT = """你是专业调酒师助手。根据用户需求和候选配方，选出最合适的鸡尾酒，生成推荐文案、原料清单和分步调制指引。严格按以下 JSON Schema 输出，不输出额外文字。

【经典模式（classic）】仅可对原料用量小幅微调（±20%），不得替换或增减原料种类。

JSON Schema:
{"selected_id":<int>,"cocktail_name":<string,英文名与候选列表一致>,"cocktail_name_zh":<string,中文名与候选列表一致>,"reason":<string,2-3句，围绕用户情绪说明契合点，有温度感>,"poetic_copy":<string,1句诗意文案如"苦中带甜，像某个值得的夜晚">,"mood_caption":<string,融入用户心情如"今晚的心情是微醺，所以调了这杯Negroni">,"tweaks":null,"prototype_name":null,"prototype_name_zh":null,"ingredients":[{"name_zh":<string,原料中文名，必须与配方原料列表中该原料名称完全一致，一字不差>,"measure_raw":<string,精确用量如"45ml">,"note":<string|null>}],"steps":[{"order":<int,从1开始>,"text":<string,精确操作，量化时间>,"duration_hint":<string|null>}]}

原料状态：[✓已有]=用户已有直接用 | [便利店]=随时可得 | [需采购]=需专门购买
选择原则：满足口味偏好的前提下，优先[✓已有]最多、[需采购]最少的配方。
原料规则：列出全部原料，不得增减原料种类；name_zh必须与候选配方原料列表中该原料的名称完全一致、一字不差（系统依赖此名称识别用户酒柜，任何同义词/简写/大小写变体都会导致识别失败）；[✓已有]的note填null；[需采购]的note注明可用的已有替代品；用量精确（写"45ml"非"适量"）。
步骤规则：3-7步，每步一件事；覆盖器具准备→量取→混合→摇匀→过滤→装饰；有时间要求的必须量化（"用力摇晃15秒"）。"""

ORIGINAL_SYSTEM_PROMPT = """你是富有创意的专业调酒师。根据用户需求和候选配方，选原型进行大胆二次创作，带来惊喜与情绪价值。严格按以下 JSON Schema 输出，不输出额外文字。

【原创模式（original）】以候选配方为原型，可替换原料、调整用量、增加1-2种新原料（香料/草本/苦精等）。酸甜比基础约2:1:1（基酒:酸:甜），摇制15秒约稀释10-15%，注重口感层次（骨架+平衡+修饰）。

JSON Schema:
{"selected_id":<int,原型配方id>,"cocktail_name":<string,特调英文名，可创意命名>,"cocktail_name_zh":<string,特调中文名，有个性>,"prototype_name":<string,原型英文名>,"prototype_name_zh":<string,原型中文名>,"reason":<string,2-4句，围绕用户情绪描述契合感和创意改动带来的独特体验>,"poetic_copy":<string,1句诗意文案，有独特个性>,"mood_caption":<string,融入用户心情和特调特点>,"tweaks":[{"content":<string,自然语言描述改动内容，如"以青柠汁替代柠檬汁">,"reason":<string,改动原因，调酒师视角>,"effect":<string,对口感或风味的具体影响，用户感知视角>}],"ingredients":[{"name_zh":<string,原料中文名，保留原料必须与配方列表名称完全一致（一字不差），新增/替换原料若在用户酒柜中存在则使用酒柜中的名称>,"measure_raw":<string,精确用量>,"note":<string|null>}],"steps":[{"order":<int,从1开始>,"text":<string,精确操作，量化时间>,"duration_hint":<string|null>}]}

原料状态：[✓已有]=已有 | [便利店]=可得 | [需采购]=需购买
选择原则：选最契合情绪、有改造潜力的原型，兼顾[✓已有]数量。
原料规则：列出改造后全部原料；保留原料的name_zh必须与配方原料列表中名称完全一致、一字不差（系统依赖此名称识别用户酒柜）；新增/替换的原料若在用户已有原料（酒柜）列表中有对应品类，name_zh必须使用酒柜列表中该原料的名称；用量精确；[需采购]原料的note注明可用的已有替代品。
步骤规则：3-7步，每步一件事；覆盖器具准备→量取→混合→摇匀→过滤→装饰；有时间要求的必须量化。"""

# ------------------------------------------------------------------ #
# Two-phase streaming prompts
# Phase 1: cocktail selection + text copy  (max_tokens ~500, fast)
# Phase 2: ingredients + steps             (max_tokens ~800, focused)
# ------------------------------------------------------------------ #
SELECTION_SYSTEM_PROMPT = """你是专业调酒师助手。从候选配方中选出最合适的鸡尾酒并生成推荐文案。严格按JSON Schema输出，不输出额外文字。

经典模式（classic）：仅可小幅微调用量（±20%），不替换或增减原料。
原创模式（original）：可替换原料、调整用量、增加1-2种新原料，注重酸甜平衡（基础比2:1:1）。

JSON Schema（classic）:
{"selected_id":<int>,"cocktail_name":<string,与候选列表一致>,"cocktail_name_zh":<string,与候选列表一致>,"reason":<string,2-3句，围绕用户情绪，有温度感>,"poetic_copy":<string,1句诗意文案>,"mood_caption":<string,融入用户心情>,"tweaks":null,"prototype_name":null,"prototype_name_zh":null}

JSON Schema（original，需同时填写tweaks/prototype_name/prototype_name_zh）:
{"selected_id":<int>,"cocktail_name":<string,可创意命名>,"cocktail_name_zh":<string,有个性>,"reason":<string,2-4句，围绕用户情绪>,"poetic_copy":<string,1句>,"mood_caption":<string>,"tweaks":[{"content":<string,自然语言描述改动内容，如"以青柠汁替代柠檬汁">,"reason":<string,改动原因，调酒师视角>,"effect":<string,对口感或风味的具体影响，用户感知视角>}],"prototype_name":<string>,"prototype_name_zh":<string>}

选择原则：满足口味偏好，优先[✓已有]多、[需采购]少的配方。原料状态：[✓已有]=已有 | [便利店]=可得 | [需采购]=需购买"""

DETAIL_SYSTEM_PROMPT = """你是专业调酒师助手。根据选定配方和改动方案，生成精确的原料清单和分步调制指引。严格按JSON Schema输出，不输出额外文字。

JSON Schema:
{"ingredients":[{"name_zh":<string,原料中文名，必须与配方原料列表中该原料名称完全一致，一字不差>,"measure_raw":<string,精确如"45ml">,"note":<string|null>}],"steps":[{"order":<int,从1开始>,"text":<string,精确操作，量化时间>,"duration_hint":<string|null>}]}

原料规则：列出全部原料；name_zh必须与配方原料列表中该原料名称完全一致、一字不差（尤其是[✓已有]标注的原料，系统依赖此名称识别用户酒柜，任何同义词/简写/变体都会导致酒柜识别失败）；原创模式新增/替换的原料若在用户已有原料（酒柜）列表中存在，name_zh必须使用酒柜列表中对应的名称；经典模式不增减原料种类；用量精确（写"45ml"非"适量"）；[需采购]原料note注明可用的已有替代品；[✓已有]原料note填null。
步骤规则：3-7步每步一件事；覆盖器具准备→量取→混合→摇匀→过滤→装饰；有时间要求的必须量化（"用力摇晃15秒"）。"""


@dataclass
class LLMResult:
    selected_id: int
    reason: str
    poetic_copy: str
    mood_caption: str
    cocktail_name: str = ""
    cocktail_name_zh: str = ""
    prototype_name: str | None = None
    prototype_name_zh: str | None = None
    tweaks: list | None = field(default=None)
    ingredients: list = field(default_factory=list)
    steps: list = field(default_factory=list)


class LLMService:
    def __init__(self):
        self._client: OpenAI | None = None
        self._provider: str | None = None

    def _get_provider(self) -> str:
        return current_app.config.get("LLM_PROVIDER", "doubao")

    @property
    def client(self) -> OpenAI:
        provider = self._get_provider()
        # Re-create the client if the provider has changed (e.g. between requests in tests)
        if self._client is None or self._provider != provider:
            self._provider = provider
            if provider == "deepseek":
                self._client = OpenAI(
                    base_url=current_app.config["DEEPSEEK_BASE_URL"],
                    api_key=current_app.config["DEEPSEEK_API_KEY"],
                    timeout=current_app.config["DEEPSEEK_LLM_TIMEOUT"],
                )
            else:
                self._client = OpenAI(
                    base_url=current_app.config["DOUBAO_BASE_URL"],
                    api_key=current_app.config["ARK_API_KEY"],
                    timeout=current_app.config["DOUBAO_LLM_TIMEOUT"],
                )
        return self._client

    def _model(self) -> str:
        if self._get_provider() == "deepseek":
            return current_app.config["DEEPSEEK_MODEL"]
        return current_app.config["DOUBAO_MODEL"]

    def _max_tokens(self, override: int | None = None) -> int:
        if override is not None:
            return override
        if self._get_provider() == "deepseek":
            return current_app.config["DEEPSEEK_MAX_TOKENS"]
        return current_app.config.get("DOUBAO_MAX_TOKENS", 1200)

    def _extra_call_kwargs(self) -> dict:
        """Return provider-specific extra kwargs for chat.completions.create."""
        provider = self._get_provider()
        if provider == "doubao":
            effort = current_app.config.get("DOUBAO_REASONING_EFFORT", "minimal")
            # 豆包的 reasoning_effort 是自定义扩展字段，必须通过 extra_body 传递
            # minimal = 不思考（最快）；留空则不传，由模型使用自身默认行为
            return {"extra_body": {"reasoning_effort": effort}} if effort else {}
        if provider == "deepseek":
            effort = current_app.config.get("DEEPSEEK_REASONING_EFFORT", "")
            if not effort:
                return {}
            return {
                "reasoning_effort": effort,
                "extra_body": {"thinking": {"type": "enabled"}},
            }
        return {}

    def _supports_json_mode(self) -> bool:
        """Thinking-enabled DeepSeek models do not support response_format=json_object.
        Doubao always supports it regardless of reasoning_effort."""
        if self._get_provider() != "deepseek":
            return True
        return not bool(current_app.config.get("DEEPSEEK_REASONING_EFFORT", ""))

    def recommend(
        self,
        candidates: list[dict],
        user_prefs: dict,
        owned_labels: list[str] | None = None,
    ) -> LLMResult:
        """One LLM call: select cocktail + generate ingredient list + steps."""
        if not candidates:
            raise ValueError("candidates list is empty")

        recipe_type = user_prefs.get("recipe_type", "classic")
        system_prompt = ORIGINAL_SYSTEM_PROMPT if recipe_type == "original" else CLASSIC_SYSTEM_PROMPT
        prompt = self._build_prompt(candidates, user_prefs, owned_labels or [])
        candidate_ids = {c["id"] for c in candidates}
        fallback = self._fallback_result(candidates, user_prefs)

        for attempt in range(3):
            try:
                raw = self._call_api(prompt, system_prompt)
                result = self._parse_result(raw, candidate_ids, recipe_type)
                return result
            except (APITimeoutError, APIConnectionError) as e:
                logger.warning("LLM timeout/connection error: %s, using fallback", e)
                return fallback
            except RateLimitError as e:
                wait = 2 ** attempt
                logger.warning("LLM rate limit, waiting %ds: %s", wait, e)
                time.sleep(wait)
                if attempt == 2:
                    return fallback
            except (json.JSONDecodeError, KeyError, ValueError) as e:
                logger.warning("LLM parse error attempt %d: %s", attempt + 1, e)
                if attempt == 2:
                    return fallback
            except Exception as e:
                logger.error("LLM unexpected error: %s", e)
                return fallback

        return fallback

    def _call_api(self, prompt: str, system_prompt: str) -> dict:
        kwargs: dict = {
            "model": self._model(),
            "messages": [
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": prompt},
            ],
            "temperature": 0.7,
            "max_tokens": self._max_tokens(),
        }
        if self._supports_json_mode():
            kwargs["response_format"] = {"type": "json_object"}
        kwargs.update(self._extra_call_kwargs())

        response = self.client.chat.completions.create(**kwargs)
        content = response.choices[0].message.content
        if content:
            logger.info("LLM raw reply (provider=%s model=%s): %s",
                        self._get_provider(), self._model(), content)
        else:
            logger.warning("LLM returned empty message content")
        return self._extract_json(content or "")

    @staticmethod
    def _extract_json(content: str) -> dict:
        """Parse JSON from model output, stripping markdown fences if present."""
        text = content.strip()
        if text.startswith("```"):
            # Remove ```json ... ``` fences produced by some models
            lines = text.splitlines()
            text = "\n".join(lines[1:-1] if lines[-1].strip() == "```" else lines[1:])
        start = text.find("{")
        end = text.rfind("}")
        if start != -1 and end != -1:
            text = text[start:end + 1]
        return json.loads(text)

    def stream_two_phase(
        self,
        candidates: list[dict],
        user_prefs: dict,
        owned_labels: list[str] | None = None,
    ) -> Generator[tuple[str, dict], None, None]:
        """Two-phase streaming for structured batch delivery.

        Yields (phase, payload) tuples:
          ("selection", dict)   — Phase 1 done: selected_id + text copy fields
          ("ingredients", list) — Phase 2: parsed ingredient list
          ("steps", list)       — Phase 2: parsed step list
          ("error", str)        — on failure (any phase)

        Phase 1 (selection + text copy) uses a focused prompt with ~500 max_tokens
        so it returns in ~5-8 s regardless of total steps length.
        Phase 2 (ingredients + steps) runs after Phase 1 is yielded, using the
        known selected candidate to build a tighter prompt (~800 max_tokens).
        """
        if not candidates:
            raise ValueError("candidates list is empty")

        recipe_type = user_prefs.get("recipe_type", "classic")
        candidate_ids = {c["id"] for c in candidates}
        fallback = self._fallback_result(candidates, user_prefs)
        owned = owned_labels or []

        # ── Phase 1: selection + text copy ──────────────────────────── #
        prompt1 = self._build_selection_prompt(candidates, user_prefs, owned)
        try:
            p1_kwargs: dict = {
                "model": self._model(),
                "messages": [
                    {"role": "system", "content": SELECTION_SYSTEM_PROMPT},
                    {"role": "user", "content": prompt1},
                ],
                "temperature": 0.7,
                "max_tokens": self._max_tokens(500),
            }
            if self._supports_json_mode():
                p1_kwargs["response_format"] = {"type": "json_object"}
            p1_kwargs.update(self._extra_call_kwargs())
            resp1 = self.client.chat.completions.create(**p1_kwargs)
            sel_raw = self._extract_json(resp1.choices[0].message.content or "{}")
            logger.info("Phase 1 done: selected_id=%s", sel_raw.get("selected_id"))
        except Exception as e:
            logger.error("Phase 1 LLM error: %s", e)
            # Yield fallback selection so downstream can still render batch1
            yield "selection", {
                "selected_id": fallback.selected_id,
                "cocktail_name": fallback.cocktail_name,
                "cocktail_name_zh": fallback.cocktail_name_zh,
                "reason": fallback.reason,
                "poetic_copy": fallback.poetic_copy,
                "mood_caption": fallback.mood_caption,
                "tweaks": None,
                "prototype_name": None,
                "prototype_name_zh": None,
            }
            yield "ingredients", []
            yield "steps", fallback.steps
            return

        selected_id = int(sel_raw.get("selected_id") or fallback.selected_id)
        if selected_id not in candidate_ids:
            selected_id = fallback.selected_id
            sel_raw["selected_id"] = selected_id

        yield "selection", sel_raw

        # ── Phase 2: ingredients + steps ────────────────────────────── #
        selected_candidate = next(
            (c for c in candidates if c["id"] == selected_id), candidates[0]
        )
        tweaks = sel_raw.get("tweaks") or []
        prompt2 = self._build_detail_prompt(selected_candidate, recipe_type, tweaks, owned)
        try:
            p2_kwargs: dict = {
                "model": self._model(),
                "messages": [
                    {"role": "system", "content": DETAIL_SYSTEM_PROMPT},
                    {"role": "user", "content": prompt2},
                ],
                "temperature": 0.7,
                "max_tokens": self._max_tokens(800),
            }
            if self._supports_json_mode():
                p2_kwargs["response_format"] = {"type": "json_object"}
            p2_kwargs.update(self._extra_call_kwargs())
            resp2 = self.client.chat.completions.create(**p2_kwargs)
            det_raw = self._extract_json(resp2.choices[0].message.content or "{}")
            logger.info("Phase 2 done, ingredients=%d steps=%d",
                        len(det_raw.get("ingredients", [])),
                        len(det_raw.get("steps", [])))
        except Exception as e:
            logger.error("Phase 2 LLM error: %s", e)
            yield "ingredients", []
            yield "steps", fallback.steps
            return

        # Parse ingredients — IDs are resolved by system, not LLM
        ingredients = []
        for ing in det_raw.get("ingredients") or []:
            if not isinstance(ing, dict):
                continue
            name_zh = str(ing.get("name_zh", "")).strip()
            if not name_zh:
                continue
            ingredients.append({
                "name_zh": name_zh,
                "measure_raw": str(ing.get("measure_raw", "")),
                "note": ing.get("note") or None,
            })
        yield "ingredients", ingredients

        # Parse steps
        steps = []
        for i, s in enumerate(det_raw.get("steps") or [], 1):
            if isinstance(s, dict) and s.get("text"):
                steps.append({
                    "order": int(s.get("order", i)),
                    "text": str(s["text"]),
                    "duration_hint": s.get("duration_hint") or None,
                })
        yield "steps", steps or fallback.steps

    def _parse_result(
        self, raw: dict, valid_ids: set[int], recipe_type: str = "classic"
    ) -> LLMResult:
        selected_id = int(raw["selected_id"])
        if selected_id not in valid_ids:
            logger.warning(
                "LLM returned id %d not in candidates %s, using first",
                selected_id,
                valid_ids,
            )
            selected_id = next(iter(valid_ids))

        # ingredient_family_id is resolved by system via name matching, not output by LLM
        ingredients = []
        for ing in raw.get("ingredients") or []:
            if not isinstance(ing, dict):
                continue
            name_zh = str(ing.get("name_zh", "")).strip()
            if not name_zh:
                continue
            ingredients.append(
                {
                    "name_zh": name_zh,
                    "measure_raw": str(ing.get("measure_raw", "")),
                    "note": ing.get("note") or None,
                }
            )

        steps = []
        for i, s in enumerate(raw.get("steps") or [], 1):
            if isinstance(s, dict) and s.get("text"):
                steps.append(
                    {
                        "order": int(s.get("order", i)),
                        "text": str(s["text"]),
                        "duration_hint": s.get("duration_hint") or None,
                    }
                )

        return LLMResult(
            selected_id=selected_id,
            reason=str(raw.get("reason", "")),
            poetic_copy=str(raw.get("poetic_copy", "")),
            mood_caption=str(raw.get("mood_caption", "")),
            cocktail_name=str(raw.get("cocktail_name", "")),
            cocktail_name_zh=str(raw.get("cocktail_name_zh", "")),
            prototype_name=raw.get("prototype_name") or None,
            prototype_name_zh=raw.get("prototype_name_zh") or None,
            tweaks=raw.get("tweaks") or None,
            ingredients=ingredients,
            steps=steps,
        )

    def _fallback_result(self, candidates: list[dict], user_prefs: dict) -> LLMResult:
        best = min(candidates, key=lambda c: c.get("missing_count", 0))
        mood = user_prefs.get("mood_tags", [])
        mood_str = "、".join(mood) if mood else "微醺"
        name_zh = best.get("name_zh") or best.get("name", "这杯鸡尾酒")
        name_en = best.get("name", "")
        db_ings: list[dict] = best.get("ingredient_list", [])

        steps = self._build_fallback_steps(name_zh, db_ings)

        return LLMResult(
            selected_id=best["id"],
            reason=f"{name_zh} 非常适合你当前的酒柜，制作所需原料基本齐全，推荐尝试。",
            poetic_copy="每一杯都是一段故事的开始。",
            mood_caption=f"今晚的心情是{mood_str}，所以调了这杯 {name_zh}",
            cocktail_name=name_en,
            cocktail_name_zh=name_zh,
            prototype_name=None,
            prototype_name_zh=None,
            tweaks=None,
            ingredients=[],   # triggers DB fallback in recommend_service
            steps=steps,
        )

    def _build_fallback_steps(self, name: str, db_ings: list[dict]) -> list[dict]:
        """Generate minimal generic steps when LLM is unavailable."""
        ing_labels = [
            f"{i['name_zh']}({i['measure_raw']})" if i.get("measure_raw") else i["name_zh"]
            for i in db_ings
            if i.get("name_zh")
        ]
        step_texts = [
            f"准备调制 {name} 所需的所有原料：{', '.join(ing_labels) if ing_labels else '按配方备料'}",
            "准备好摇酒壶（或调酒杯）、量杯、吧勺和目标酒杯",
            "向摇酒壶中加入 6-8 颗冰块，让壶体充分冷却",
        ]
        for ing in db_ings:
            label = ing.get("name_zh", "")
            measure = ing.get("measure_raw", "")
            if label:
                step_texts.append(
                    f"用量杯量取 {measure} {label}，倒入摇酒壶".strip() if measure else f"将 {label} 倒入摇酒壶"
                )
        step_texts += [
            "盖紧摇酒壶，用力摇晃 15 秒，使原料充分融合并冷却",
            "用隔冰器将酒液过滤倒入预先冰镇好的酒杯中",
            "按需添加装饰物，即可享用",
        ]
        return [
            {"order": i + 1, "text": text, "duration_hint": None}
            for i, text in enumerate(step_texts)
        ]

    _STATUS_MARKER: dict[str, str] = {
        "owned": "✓已有",
        "available": "便利店",
        "missing": "需采购",
    }

    # ------------------------------------------------------------------ #
    # Two-phase prompt builders
    # ------------------------------------------------------------------ #

    def _build_selection_prompt(
        self, candidates: list[dict], prefs: dict, owned_labels: list[str]
    ) -> str:
        """Phase 1 prompt: candidate list + user prefs (no ingredient ids needed here)."""
        lines = []
        for c in candidates:
            db_ings: list[dict] = c.get("ingredient_list", [])
            ing_parts = []
            for ing in db_ings:
                marker = self._STATUS_MARKER.get(ing.get("llm_status", "missing"), "需采购")
                ing_parts.append(f"{ing.get('name_zh') or ''}[{marker}]")
            hist_tag = " [历史推荐]" if c.get("is_previously_recommended") else ""
            lines.append(
                f"- id:{c['id']} 名称:{c.get('name_zh') or c['name']}{hist_tag} "
                f"口感:{c.get('flavor_tags', [])} "
                f"缺料数:{c.get('missing_count', 0)} 原料:[{' '.join(ing_parts)}]"
            )

        owned_section = (
            f"\n用户酒柜已有原料（后续生成ingredients时，[✓已有]原料的name_zh须与此列表名称一字不差）：{', '.join(owned_labels)}\n"
            if owned_labels else ""
        )
        return (
            f"用户需求：酒精={prefs.get('abv_pref', 'any')} "
            f"口感={prefs.get('flavor_tags', [])} 模式={prefs.get('recipe_type', 'classic')} "
            f"自述={prefs.get('free_text', '无') or '无'}\n"
            f"{owned_section}"
            f"候选配方（[历史推荐]表示该配方已向用户推荐过，请优先选择无此标注的配方）：\n"
            + "\n".join(lines)
            + "\n\n请选出最合适的配方并生成推荐文案，按JSON Schema输出。"
        )

    def _build_detail_prompt(
        self,
        candidate: dict,
        recipe_type: str,
        tweaks: list,
        owned_labels: list[str],
    ) -> str:
        """Phase 2 prompt: selected cocktail ingredient list + tweak plan."""
        db_ings: list[dict] = candidate.get("ingredient_list", [])
        ing_lines = []
        for ing in db_ings:
            marker = self._STATUS_MARKER.get(ing.get("llm_status", "missing"), "需采购")
            ing_lines.append(
                f"  - {ing.get('name_zh') or ''}"
                f"({ing.get('measure_raw') or '适量'})[{marker}]"
            )

        tweak_section = ""
        if tweaks:
            tweak_lines = [
                f"  - {t.get('content')}（原因：{t.get('reason')}；口感影响：{t.get('effect')}）"
                for t in tweaks if isinstance(t, dict)
            ]
            tweak_section = "改动方案（original模式）：\n" + "\n".join(tweak_lines) + "\n"

        owned_section = (
            f"用户酒柜已有原料（name_zh必须使用此列表中的名称，一字不差）：{', '.join(owned_labels)}\n"
            if owned_labels else ""
        )
        return (
            f"配方：{candidate.get('name_zh') or candidate.get('name')} "
            f"（{candidate.get('name', '')}） id:{candidate['id']}\n"
            f"模式：{recipe_type}\n"
            f"{owned_section}"
            f"配方原料列表（[✓已有]原料的name_zh必须与此列表中的名称完全一致，一字不差）：\n"
            + "\n".join(ing_lines) + "\n"
            + tweak_section
            + "\n请生成精确原料清单和调制步骤，按JSON Schema输出。"
        )

    def _build_prompt(
        self, candidates: list[dict], prefs: dict, owned_labels: list[str]
    ) -> str:
        candidate_lines = []
        for c in candidates:
            db_ings: list[dict] = c.get("ingredient_list", [])
            ing_parts = []
            for ing in db_ings:
                marker = self._STATUS_MARKER.get(ing.get("llm_status", "missing"), "需采购")
                name = ing.get("name_zh") or ""
                measure = ing.get("measure_raw") or "适量"
                ing_parts.append(f"{name}({measure})[{marker}]")
            ing_str = "、".join(ing_parts) or "（原料信息缺失）"
            hist_tag = " [历史推荐]" if c.get("is_previously_recommended") else ""
            candidate_lines.append(
                f"- id:{c['id']} 名称:{c.get('name_zh') or c['name']}{hist_tag} "
                f"口感:{c.get('flavor_tags', [])} "
                f"缺料数:{c.get('missing_count', 0)}\n"
                f"  原料: {ing_str}"
            )
        candidate_list = "\n".join(candidate_lines)

        owned_section = (
            f"\n用户酒柜已有原料（生成ingredients时，[✓已有]原料的name_zh必须使用此列表中的名称，一字不差）：{', '.join(owned_labels)}\n"
            if owned_labels
            else ""
        )

        return f"""
用户需求：
- 酒精度偏好：{prefs.get('abv_pref', 'any')}
- 口感偏好：{prefs.get('flavor_tags', [])}
- 配方类型：{prefs.get('recipe_type', 'classic')}
- 自由描述：{prefs.get('free_text', '无') or '无'}
{owned_section}
候选配方列表（[历史推荐]表示该配方已向用户推荐过，请优先选择无此标注的配方；原料末尾标注酒柜状态；[✓已有]原料的name_zh必须与列表中名称完全一致，一字不差）：
{candidate_list}

请从候选列表中选出最合适的一款，按 JSON Schema 输出（含完整 ingredients 和 steps）。
"""


llm_service = LLMService()
