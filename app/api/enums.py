"""
枚举值查询 API
提供前端使用的所有枚举值及其中英文映射
"""
from flask import Blueprint
from ..utils.response import success
from ..utils.enums import (
    FLAVOR_TAGS,
    MOOD_TAGS,
    GLASS_TYPES,
    ABV_LEVELS,
    RECIPE_TYPES,
    COCKTAIL_CATEGORIES,
)

enums_bp = Blueprint("enums", __name__)


@enums_bp.route("/flavor-tags", methods=["GET"])
def get_flavor_tags():
    """获取所有口味标签（中英文）"""
    return success({
        "tags": [
            {"value": k, "label": v}
            for k, v in sorted(FLAVOR_TAGS.items(), key=lambda x: x[1])
        ]
    })


@enums_bp.route("/mood-tags", methods=["GET"])
def get_mood_tags():
    """获取所有心情标签（中英文）"""
    return success({
        "tags": [
            {"value": k, "label": v}
            for k, v in sorted(MOOD_TAGS.items(), key=lambda x: x[1])
        ]
    })


@enums_bp.route("/glass-types", methods=["GET"])
def get_glass_types():
    """获取所有杯型（中英文）
    
    注意：返回的是去重后的常见杯型列表
    """
    # 去重并只保留最常用的杯型
    common_glasses = {
        "cocktail glass": "鸡尾酒杯",
        "old fashioned": "古典杯",
        "highball": "高球杯",
        "collins": "可林杯",
        "martini": "马天尼杯",
        "coupe": "碟形杯",
        "nick & nora": "尼克诺拉杯",
        "margarita glass": "玛格丽塔杯",
        "hurricane": "飓风杯",
        "tiki": "提基杯",
        "champagne flute": "香槟笛杯",
        "wine glass": "葡萄酒杯",
        "snifter": "球形杯",
        "shot": "子弹杯",
        "copper mug": "铜杯",
        "irish coffee": "爱尔兰咖啡杯",
        "pint": "品脱杯",
    }
    
    return success({
        "types": [
            {"value": k, "label": v}
            for k, v in sorted(common_glasses.items(), key=lambda x: x[1])
        ]
    })


@enums_bp.route("/glass-types/all", methods=["GET"])
def get_all_glass_types():
    """获取所有杯型（包括变体，中英文）"""
    # 去重（多个英文对应同一个中文的，只保留一个）
    seen_zh = set()
    unique_glasses = []
    
    for en, zh in sorted(GLASS_TYPES.items(), key=lambda x: x[1]):
        if zh not in seen_zh:
            seen_zh.add(zh)
            unique_glasses.append({"value": en, "label": zh})
    
    return success({
        "types": unique_glasses
    })


@enums_bp.route("/abv-levels", methods=["GET"])
def get_abv_levels():
    """获取所有酒精度级别（中英文）"""
    return success({
        "levels": [
            {"value": k, "label": v}
            for k, v in ABV_LEVELS.items()
        ]
    })


@enums_bp.route("/recipe-types", methods=["GET"])
def get_recipe_types():
    """获取所有配方类型（中英文）"""
    return success({
        "types": [
            {"value": k, "label": v}
            for k, v in RECIPE_TYPES.items()
        ]
    })


@enums_bp.route("/categories", methods=["GET"])
def get_categories():
    """获取所有鸡尾酒分类（中英文）"""
    return success({
        "categories": [
            {"value": k, "label": v}
            for k, v in COCKTAIL_CATEGORIES.items()
        ]
    })


@enums_bp.route("/all", methods=["GET"])
def get_all_enums():
    """一次性获取所有枚举值"""
    return success({
        "flavor_tags": [
            {"value": k, "label": v}
            for k, v in sorted(FLAVOR_TAGS.items(), key=lambda x: x[1])
        ],
        "mood_tags": [
            {"value": k, "label": v}
            for k, v in sorted(MOOD_TAGS.items(), key=lambda x: x[1])
        ],
        "glass_types": [
            {"value": k, "label": v}
            for k, v in [
                ("cocktail glass", "鸡尾酒杯"),
                ("old fashioned", "古典杯"),
                ("highball", "高球杯"),
                ("martini", "马天尼杯"),
                ("coupe", "碟形杯"),
            ]
        ],
        "abv_levels": [
            {"value": k, "label": v}
            for k, v in ABV_LEVELS.items()
        ],
        "recipe_types": [
            {"value": k, "label": v}
            for k, v in RECIPE_TYPES.items()
        ],
        "categories": [
            {"value": k, "label": v}
            for k, v in COCKTAIL_CATEGORIES.items()
        ],
    })
