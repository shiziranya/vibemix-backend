from __future__ import annotations
import re

from .errors import ValidationError

PHONE_RE = re.compile(r"^1[3-9]\d{9}$")

VALID_FLAVOR_TAGS = {
    "sweet", "sour", "bitter", "spicy", "fruity", "creamy",
    "citrus", "dry", "earthy", "floral", "herbal", "nutty",
    "refreshing", "rich", "savory", "smoky", "tropical",
}
VALID_ABV_PREFS = {"low", "medium", "high", "non-alcoholic", "any"}
VALID_RECIPE_TYPES = {"classic", "original"}
VALID_COCKTAIL_CATEGORIES = {"Craft", "Classic", "Other", "Shot"}
# 模板验证已移除 - 由 card_gen 服务动态提供，不在此处硬编码


def validate_phone(phone: str) -> str:
    if not phone or not PHONE_RE.match(phone):
        raise ValidationError("手机号格式不正确，请输入 11 位中国大陆手机号")
    return phone


def validate_password(password: str) -> str:
    if not password or len(password) < 6:
        raise ValidationError("密码长度不能少于 6 位")
    if len(password) > 64:
        raise ValidationError("密码长度不能超过 64 位")
    return password


def validate_recommend_request(data: dict) -> dict:
    flavor_tags = data.get("flavor_tags", [])
    if not isinstance(flavor_tags, list):
        raise ValidationError("flavor_tags 必须是数组")
    invalid = set(flavor_tags) - VALID_FLAVOR_TAGS
    if invalid:
        raise ValidationError(f"无效的 flavor_tags: {invalid}")

    abv_pref = data.get("abv_pref", "any")
    if abv_pref not in VALID_ABV_PREFS:
        raise ValidationError(f"abv_pref 必须是 {VALID_ABV_PREFS} 之一")

    recipe_type = data.get("recipe_type", "classic")
    if recipe_type not in VALID_RECIPE_TYPES:
        raise ValidationError(f"recipe_type 必须是 {VALID_RECIPE_TYPES} 之一")

    category = data.get("category", None)
    if category is not None and category not in VALID_COCKTAIL_CATEGORIES:
        raise ValidationError(f"category 必须是 {VALID_COCKTAIL_CATEGORIES} 之一，或不传")

    free_text = data.get("free_text", "")
    if free_text and len(free_text) > 200:
        free_text = free_text[:200]

    return {
        "flavor_tags": flavor_tags,
        "abv_pref": abv_pref,
        "recipe_type": recipe_type,
        "category": category,
        "free_text": free_text,
    }


def validate_card_request(data: dict) -> dict:
    cocktail_id = data.get("cocktail_id")
    # 适配 int 和 str 类型
    if not cocktail_id:
        raise ValidationError("cocktail_id 必填")
    
    if isinstance(cocktail_id, int):
        pass  # 已经是整数
    elif isinstance(cocktail_id, str):
        try:
            cocktail_id = int(cocktail_id)
        except ValueError:
            raise ValidationError("cocktail_id 必须是整数或可转换为整数的字符串")
    else:
        raise ValidationError("cocktail_id 必须是整数或字符串")

    # text_overrides: {layer_id: {x: float, y: float}} — 仅验证结构，不限制 key
    text_overrides = data.get("text_overrides") or {}
    if not isinstance(text_overrides, dict):
        raise ValidationError("text_overrides 必须是对象")
    validated_overrides: dict = {}
    for layer_id, pos in text_overrides.items():
        if not isinstance(pos, dict):
            continue
        x = pos.get("x")
        y = pos.get("y")
        if isinstance(x, (int, float)) and isinstance(y, (int, float)):
            validated_overrides[str(layer_id)] = {
                "x": float(max(0.0, min(1.0, x))),
                "y": float(max(0.0, min(1.0, y))),
            }

    template_id = data.get("template_id") or None
    # 验证 template_id 必须是字符串类型（不能是字典对象）
    if template_id is not None and not isinstance(template_id, str):
        raise ValidationError("template_id 必须是字符串")
    
    return {
        "session_id": data.get("session_id"),
        "cocktail_id": cocktail_id,
        "template_id": template_id,
        "text_overrides": validated_overrides,
        "user_photo_url": data.get("user_photo_url"),
        "mood_caption": data.get("mood_caption", ""),
    }
