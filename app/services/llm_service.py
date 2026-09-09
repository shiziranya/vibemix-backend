from __future__ import annotations
"""
豆包 LLM 服务：封装推荐调用。
包含超时降级、JSON 解析失败重试、限流退避等容错逻辑。

普通接口：根据模式调用
  - classic: 仅选酒 + 文案（ingredients/steps 使用数据库配方）
  - original: 选酒 + 文案 + 自定义原料 + 调制步骤
流式接口：两阶段调用
  Phase 1 (约 5-8s)：选酒 + 文案（selected_id / reason / poetic_copy / mood_caption / tweaks）
  Phase 2 (约 10s，仅 original 模式)：原料清单 + 调制步骤（聚焦，max_tokens 更小）
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

# 复用的文案风格模块
_VOICE = """【文案风格：说人话，做嘴替】
你不是端着的酒单文案，是那个秒懂用户此刻情绪的朋友。用户喝的不是酒，是那口情绪（班味/emo/报复性放松/不想说话）。先接住情绪，再递酒。
1. 先共情再推酒：读出用户那句话的潜台词（"想喝热带的"=想逃工位，"来杯烈的"=今天遭老罪了），写到用户直呼"这不就是我嘴替"。
2. 反矫情反鸡汤：拉黑"值得的夜晚""温柔的风""把阳光装进杯子里"这类塑料诗意，要真诚、具体、带自嘲和幽默。
3. 有网感但别硬凑梗：可用当下语感（松弛感/电子/续命/破防/i人e人/momo…），一次最多点一两个且必须贴题，宁可不用也别尬。
4. 短句有节奏、情绪直给，别写成产品说明书；每次换句式，别套同一个万能模板。
5. 底线：不低俗、不阴阳用户、不贩卖焦虑；网感是外壳，真诚和好喝是内核。
各字段怎么写：
- reason：2-3句，先点破用户情绪/潜台词，再自然带出为什么是这杯（度数/口味/家里有没有料），像朋友递酒时唠嗑，有温度也有点欠。
- poetic_copy：1句能直接发朋友圈的态度slogan，短、有记忆点、反矫情，别写古诗。
- mood_caption：一句自然地描述用户情绪和这杯酒的关系，口语化、有画面感，不要套用"今晚精神状态"或"今日状态"这种格式化开头。
- 命名：原创特调的 cocktail_name_zh 要起个有梗、能截图分享的名字（语感示例：电子布洛芬/勿扰模式/工位度假计划/已读乱回），别平庸直译；经典模式名字必须与候选列表完全一致、不得改名，把火力全压在文案上。
风格示例（学语气即可，严禁照抄，按真实输入重新创作）：
· 被领导骂了想喝烈的 → 名"电子布洛芬"｜reason"被骂这事儿酒解决不了，但能帮你先泡一泡。柜里的威士忌打底，两滴苦精上强度，烈到你顾不上白天那档子事，喝完早点睡明天还是体面打工人"｜poetic_copy"解决不了领导，先解决这杯"｜mood_caption"想原地失忆的时候，就得来这么一杯猛的"
· 周五想喝甜的犒劳自己 → reason"熬到周五你配拥有一整个甜，度数不高、柜里现成料就能凑齐，坐下就喝，当给自己提前发的年终奖"｜poetic_copy"这周唯一达成的KPI：对自己好一点"｜mood_caption"报复性快乐就整杯甜的，不解释\""""

CLASSIC_SYSTEM_PROMPT = """你是懂调酒、更懂人的调酒师助手。根据用户需求和候选配方，选出最合适的鸡尾酒并生成推荐文案。严格按以下 JSON Schema 输出，不输出额外文字。
【经典模式（classic）】选择经典配方，无需生成原料清单和调制步骤（系统将使用数据库中的标准配方）；鸡尾酒英文名/中文名必须与候选列表完全一致、不得改名，文案要写出彩。
""" + _VOICE + """
JSON Schema:
{"selected_id":<int>,"cocktail_name":<string,英文名与候选列表一致>,"cocktail_name_zh":<string,中文名与候选列表一致>,"reason":<string,2-3句，先点破情绪再带出契合点，有温度有网感>,"poetic_copy":<string,1句态度slogan，短、反矫情>,"mood_caption":<string,一句说穿精神状态，句式别每次一样>,"tweaks":null,"prototype_name":null,"prototype_name_zh":null}
原料状态：[✓已有]=用户已有直接用 | [便利店]=随时可得 | [需采购]=需专门购买
选择原则：满足口味偏好的前提下，优先[✓已有]最多、[需采购]最少的配方。"""

ORIGINAL_SYSTEM_PROMPT = """你是富有创意、又极其懂人的调酒师。根据用户需求和候选配方，选原型进行大胆二次创作，带来惊喜与情绪价值。严格按以下 JSON Schema 输出，不输出额外文字。
【原创模式（original）】以候选配方为原型，可替换原料、调整用量、增加1-2种新原料（香料/草本/苦精等）。酸甜比基础约2:1:1（基酒:酸:甜），摇制15秒约稀释10-15%，注重口感层次（骨架+平衡+修饰）。你要给这杯特调起一个有梗、能截图分享的名字。
""" + _VOICE + """
JSON Schema:
{"selected_id":<int,原型配方id>,"cocktail_name":<string,特调英文名，简洁有格调可创意命名>,"cocktail_name_zh":<string,特调中文名，有梗有记忆点能截图分享，呼应用户情绪>,"prototype_name":<string,原型英文名>,"prototype_name_zh":<string,原型中文名>,"reason":<string,2-4句，先点破情绪再描述契合感与创意改动带来的独特体验>,"poetic_copy":<string,1句态度slogan，短、有记忆点、反矫情>,"mood_caption":<string,一句说穿精神状态并带出特调特点，句式别每次一样>,"tweaks":[{"content":<string,自然语言描述改动，如"以青柠汁替代柠檬汁">,"reason":<string,改动原因，调酒师视角>,"effect":<string,对口感或风味的影响，用户感知视角，可口语有画面感>}],"ingredients":[{"name_zh":<string,原料中文名，保留原料必须与配方列表名称完全一致（一字不差），新增/替换原料若在用户酒柜中存在则使用酒柜中的名称>,"measure_raw":<string,精确用量>,"note":<string|null>}],"steps":[{"order":<int,从1开始>,"text":<string,精确操作，量化时间>,"duration_hint":<string|null>}]}
原料状态：[✓已有]=已有 | [便利店]=可得 | [需采购]=需购买
选择原则：选最契合情绪、有改造潜力的原型，兼顾[✓已有]数量。
原料规则：列出改造后全部原料；保留原料的name_zh必须与配方原料列表中名称完全一致、一字不差（系统依赖此名称识别用户酒柜）；新增/替换的原料若在用户已有原料（酒柜）列表中有对应品类，name_zh必须使用酒柜列表中该原料的名称；用量精确；[需采购]原料的note注明可用的已有替代品。
步骤规则：3-7步，每步一件事；覆盖器具准备→量取→混合→摇匀→过滤→装饰；有时间要求的必须量化。"""

# ------------------------------------------------------------------ #
# Two-phase streaming prompts
# Phase 1: cocktail selection + text copy  (max_tokens ~500, fast)
# Phase 2: ingredients + steps             (max_tokens ~800, focused)
# ------------------------------------------------------------------ #
SELECTION_SYSTEM_PROMPT = """你是懂调酒、更懂人的调酒师助手。从候选配方中选出最合适的鸡尾酒并生成推荐文案。严格按JSON Schema输出，不输出额外文字。
经典模式（classic）：仅可小幅微调用量（±20%），不替换或增减原料；鸡尾酒英文名/中文名必须与候选列表完全一致、不得改名。
原创模式（original）：可替换原料、调整用量、增加1-2种新原料，注重酸甜平衡（基础比2:1:1）；给特调起个有梗、能截图分享的名字。
""" + _VOICE + """
JSON Schema（classic）:
{"selected_id":,"cocktail_name":,"cocktail_name_zh":,"reason":,"poetic_copy":,"mood_caption":,"tweaks":null,"prototype_name":null,"prototype_name_zh":null}
JSON Schema（original，需同时填写tweaks/prototype_name/prototype_name_zh）:
{"selected_id":,"cocktail_name":,"cocktail_name_zh":,"reason":,"poetic_copy":,"mood_caption":,"tweaks":[{"content":,"reason":,"effect":}],"prototype_name":,"prototype_name_zh":}
选择原则：满足口味偏好，优先[✓已有]多、[需采购]少的配方。原料状态：[✓已有]=已有 | [便利店]=可得 | [需采购]=需购买"""

DETAIL_SYSTEM_PROMPT = """你是专业调酒师助手。根据选定配方和改动方案，生成精确的原料清单和分步调制指引。严格按JSON Schema输出，不输出额外文字。
JSON Schema:
{"ingredients":[{"name_zh":,"measure_raw":,"note":}],"steps":[{"order":,"text":,"duration_hint":}]}
原料规则：列出全部原料；name_zh必须与配方原料列表中该原料名称完全一致、一字不差（尤其是[✓已有]标注的原料，系统依赖此名称识别用户酒柜，任何同义词/简写/变体都会导致酒柜识别失败）；原创模式新增/替换的原料若在用户已有原料（酒柜）列表中存在，name_zh必须使用酒柜列表中对应的名称；经典模式不增减原料种类；用量精确（写"45ml"非"适量"）；[需采购]原料note注明可用的已有替代品；[✓已有]原料note填null。
步骤规则：3-7步每步一件事；覆盖器具准备→量取→混合→摇匀→过滤→装饰；有时间要求的必须量化（"用力摇晃15秒"）。步骤文本以清晰可执行为第一优先，可略带利落的口吻，但不堆砌网络梗、不喧宾夺主。"""


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
        """One LLM call: select cocktail + generate content.
        
        - classic mode: select + text copy only (ingredients/steps from DB)
        - original mode: select + text copy + custom ingredients + steps
        """
        if not candidates:
            raise ValueError("candidates list is empty")

        recipe_type = user_prefs.get("recipe_type", "classic")
        candidate_ids = {c["id"] for c in candidates}
        fallback = self._fallback_result(candidates, user_prefs)
        
        # Classic mode: only select cocktail + generate text copy
        if recipe_type == "classic":
            system_prompt = CLASSIC_SYSTEM_PROMPT
            prompt = self._build_selection_prompt(candidates, user_prefs, owned_labels or [])
        else:
            # Original mode: full generation (select + ingredients + steps)
            system_prompt = ORIGINAL_SYSTEM_PROMPT
            prompt = self._build_prompt(candidates, user_prefs, owned_labels or [])

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

    def select_cocktail(
        self,
        candidates: list[dict],
        user_prefs: dict,
        owned_labels: list[str] | None = None,
    ) -> dict:
        """仅执行选酒 + 文案生成。不生成原料和步骤。

        适用于：
        - classic 模式的独立选酒（使用数据库配方）
        - 流式接口的 Phase 1
        
        返回 sel_raw dict，包含 selected_id / reason / poetic_copy /
        mood_caption / cocktail_name / cocktail_name_zh。
        """
        if not candidates:
            raise ValueError("candidates list is empty")

        fallback = self._fallback_result(candidates, user_prefs)
        owned = owned_labels or []
        prompt = self._build_selection_prompt(candidates, user_prefs, owned)
        candidate_ids = {c["id"] for c in candidates}

        try:
            kwargs: dict = {
                "model": self._model(),
                "messages": [
                    {"role": "system", "content": SELECTION_SYSTEM_PROMPT},
                    {"role": "user", "content": prompt},
                ],
                "temperature": 0.7,
                "max_tokens": self._max_tokens(500),
            }
            if self._supports_json_mode():
                kwargs["response_format"] = {"type": "json_object"}
            kwargs.update(self._extra_call_kwargs())
            resp = self.client.chat.completions.create(**kwargs)
            raw = self._extract_json(resp.choices[0].message.content or "{}")
            logger.info("select_cocktail done: selected_id=%s", raw.get("selected_id"))

            selected_id = int(raw.get("selected_id") or fallback.selected_id)
            if selected_id not in candidate_ids:
                selected_id = fallback.selected_id
                raw["selected_id"] = selected_id
            return raw

        except Exception as e:
            logger.error("select_cocktail LLM error: %s", e)
            return {
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

        # ── Phase 2: ingredients + steps (original mode only) ────────── #
        if recipe_type == "classic":
            # Classic mode: use DB recipe, no LLM call for ingredients/steps
            logger.info("Classic mode: skipping Phase 2, will use DB recipe")
            yield "ingredients", []
            yield "steps", []
            return
        
        # Original mode: generate custom ingredients + steps
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
        """Generate fallback result when LLM is unavailable.
        
        - ingredients: always empty (system will use DB recipe)
        - steps: generic steps for original mode; empty for classic mode
        """
        best = min(candidates, key=lambda c: c.get("missing_count", 0))
        mood = user_prefs.get("mood_tags", [])
        mood_str = "、".join(mood) if mood else "微醺"
        name_zh = best.get("name_zh") or best.get("name", "这杯鸡尾酒")
        name_en = best.get("name", "")
        db_ings: list[dict] = best.get("ingredient_list", [])
        recipe_type = user_prefs.get("recipe_type", "classic")

        # Classic mode: empty steps (use DB recipe)
        # Original mode: generic steps as fallback
        steps = [] if recipe_type == "classic" else self._build_fallback_steps(name_zh, db_ings)

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
            ingredients=[],   # always empty - system will use DB recipe
            steps=steps,
        )

    def _build_fallback_steps(self, name: str, db_ings: list[dict]) -> list[dict]:
        """Generate minimal generic steps when LLM is unavailable."""
        ing_labels = [
            f"{i['name_zh']}({i.get('measure_normalized') or i.get('measure_raw') or '适量'})"
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
            # 优先使用归一化用量
            measure = ing.get("measure_normalized") or ing.get("measure_raw", "")
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
            # 优先使用归一化用量，避免LLM输出oz等非标准单位
            measure = ing.get("measure_normalized") or ing.get("measure_raw") or "适量"
            ing_lines.append(
                f"  - {ing.get('name_zh') or ''}"
                f"({measure})[{marker}]"
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
                # 优先使用归一化用量，避免LLM输出oz等非标准单位
                measure = ing.get("measure_normalized") or ing.get("measure_raw") or "适量"
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
