"""
鸡尾酒相关的枚举值定义及中英文映射
"""
from __future__ import annotations
from typing import Optional

# ══════════════════════════════════════════════════════════════════════════
# 口味标签 (Flavor Tags)
# ══════════════════════════════════════════════════════════════════════════

FLAVOR_TAGS = {
    "sweet": "甜",
    "sour": "酸",
    "bitter": "苦",
    "spicy": "辛辣",
    "fruity": "果香",
    "creamy": "奶油",
    "citrus": "柑橘",
    "dry": "干爽",
    "earthy": "泥土气息",
    "floral": "花香",
    "herbal": "草本",
    "nutty": "坚果",
    "refreshing": "清爽",
    "rich": "浓郁",
    "savory": "咸鲜",
    "smoky": "烟熏",
    "tropical": "热带",
}

# ══════════════════════════════════════════════════════════════════════════
# 心情标签 (Mood Tags)
# ══════════════════════════════════════════════════════════════════════════

MOOD_TAGS = {
    "romantic": "浪漫",
    "elegant": "优雅",
    "refreshing": "清爽",
    "relaxing": "放松",
    "mysterious": "神秘",
    "energetic": "活力",
    "sophisticated": "精致",
    "casual": "随性",
    "cozy": "温馨",
    "adventurous": "冒险",
    "nostalgic": "怀旧",
    "playful": "俏皮",
    "bold": "大胆",
    "mellow": "柔和",
    "festive": "欢庆",
    "contemplative": "沉思",
    "sensual": "感性",
    "vibrant": "活泼",
}

# ══════════════════════════════════════════════════════════════════════════
# 杯型 (Glass Types)
# ══════════════════════════════════════════════════════════════════════════

GLASS_TYPES = {
    # Old Fashioned / Rocks 系列
    "old fashioned glass": "古典杯",
    "old-fashioned glass": "古典杯",
    "old fashioned": "古典杯",
    "old-fashioned": "古典杯",
    "rocks glass": "古典杯",
    "rocks": "古典杯",
    "double old fashioned glass": "双料古典杯",
    "double rocks glass": "双料古典杯",
    "lowball glass": "古典杯",
    "footed rocks glass": "脚古典杯",
    "etched rocks glass": "蚀刻古典杯",
    "v-shaped rocks glass": "V形古典杯",
    "crystal rocks": "水晶古典杯",
    
    # Highball / Collins / Tall
    "highball glass": "高球杯",
    "highball": "高球杯",
    "collins glass": "可林杯",
    "collins": "可林杯",
    "tall glass": "高杯",
    "fizz glass": "菲士杯",
    "bamboo highball glass": "竹制高球杯",
    
    # Martini / Cocktail / Coupe / Nick & Nora
    "martini glass": "马天尼杯",
    "martini": "马天尼杯",
    "cocktail glass": "鸡尾酒杯",
    "coupe glass": "碟形杯",
    "coupe": "碟形杯",
    "egg coupe": "蛋形碟形杯",
    "royal coupette": "皇家碟形杯",
    "nick & nora": "尼克诺拉杯",
    "nick and nora glass": "尼克诺拉杯",
    "nick and nora": "尼克诺拉杯",
    
    # Margarita / Hurricane / Tiki
    "margarita glass": "玛格丽塔杯",
    "margarita/coupette glass": "玛格丽塔杯",
    "hurricane glass": "飓风杯",
    "hurricane": "飓风杯",
    "tiki glass": "提基杯",
    "tiki cat glass": "提基猫杯",
    "tiki": "提基杯",
    
    # Champagne / Wine / Port
    "champagne flute": "香槟笛杯",
    "wine glass": "葡萄酒杯",
    "stemless wine glass": "无脚葡萄酒杯",
    "white wine glass": "白葡萄酒杯",
    "port glass": "波特酒杯",
    "copita glass": "科皮塔杯",
    "balloon glass": "气球杯",
    "large balloon glass": "大气球杯",
    
    # Brandy / Snifter
    "brandy snifter": "白兰地球形杯",
    "snifter": "球形杯",
    "canadian glencairn glass": "格兰凯恩杯",
    
    # Beer
    "beer glass": "啤酒杯",
    "beer mug": "啤酒马克杯",
    "beer pilsner": "皮尔森啤酒杯",
    "pilsner glass": "皮尔森杯",
    "pint glass": "品脱杯",
    "pint": "品脱杯",
    "lager": "拉格杯",
    "shorty beer": "短身啤酒杯",
    
    # Mug / Cup
    "copper mug": "铜杯",
    "coffee mug": "咖啡马克杯",
    "glass mug": "玻璃马克杯",
    "mug": "马克杯",
    "irish coffee mug": "爱尔兰咖啡杯",
    "irish coffee glass": "爱尔兰咖啡杯",
    "irish coffee cup": "爱尔兰咖啡杯",
    "julep cup": "薄荷朱莉普杯",
    "tin cup": "锡杯",
    "espresso cup": "浓缩咖啡杯",
    "demitasse glass": "小咖啡杯",
    
    # Shot / Cordial
    "shot glass": "子弹杯",
    "shot": "子弹杯",
    "cordial glass": "利口酒杯",
    "stemmed cordial glass": "高脚利口酒杯",
    "pousse cafe glass": "彩虹酒杯",
    "flip glass": "蛋酒杯",
    
    # Punch / Goblet / Other
    "punch bowl": "潘趣碗",
    "punch glass": "潘趣杯",
    "goblet": "高脚大杯",
    "tumbler": "平底杯",
    "small tumbler": "小平底杯",
    "pitcher": "壶",
    "jar": "梅森罐",
    "mason jar": "梅森罐",
    "bucket": "冰桶杯",
    "handled glass": "带柄杯",
    "chilled glass": "冰镇杯",
    "smoked glass": "烟熏杯",
    "vintage glass": "复古杯",
    "whiskey glass": "威士忌杯",
    "whiskey sour glass": "威士忌酸杯",
    "8 oz glass": "8盎司杯",
    "large antique vintage shaker": "古董摇酒壶",
}

# ══════════════════════════════════════════════════════════════════════════
# 酒精度级别 (ABV Levels)
# ══════════════════════════════════════════════════════════════════════════

ABV_LEVELS = {
    "non-alcoholic": "无酒精",
    "low": "低度",
    "medium": "中度",
    "high": "高度",
    "any": "任意",
}

# ══════════════════════════════════════════════════════════════════════════
# 配方类型 (Recipe Types)
# ══════════════════════════════════════════════════════════════════════════

RECIPE_TYPES = {
    "classic": "经典",
    "original": "原创",
}

# ══════════════════════════════════════════════════════════════════════════
# 鸡尾酒分类 (Cocktail Categories)
# ══════════════════════════════════════════════════════════════════════════

COCKTAIL_CATEGORIES = {
    "Craft": "手工精调",
    "Classic": "经典款",
    "Other": "其他",
    "Shot": "短饮",
}

# ══════════════════════════════════════════════════════════════════════════
# 工具函数
# ══════════════════════════════════════════════════════════════════════════

def translate_flavor_tags(tags: list[str]) -> list[str]:
    """将英文口味标签翻译为中文"""
    return [FLAVOR_TAGS.get(tag.lower(), tag) for tag in tags]


def translate_mood_tags(tags: list[str]) -> list[str]:
    """将英文心情标签翻译为中文"""
    return [MOOD_TAGS.get(tag.lower(), tag) for tag in tags]


def translate_glass_type(glass_type: Optional[str]) -> str:
    """将英文杯型翻译为中文"""
    if not glass_type:
        return "鸡尾酒杯"
    return GLASS_TYPES.get(glass_type.lower().strip(), glass_type)


def translate_abv_level(level: Optional[str]) -> str:
    """将英文酒精度级别翻译为中文"""
    if not level:
        return "中度"
    return ABV_LEVELS.get(level.lower(), level)


def translate_recipe_type(recipe_type: Optional[str]) -> str:
    """将英文配方类型翻译为中文"""
    if not recipe_type:
        return "经典"
    return RECIPE_TYPES.get(recipe_type.lower(), recipe_type)


def translate_category(category: Optional[str]) -> str:
    """将英文分类翻译为中文"""
    if not category:
        return ""
    return COCKTAIL_CATEGORIES.get(category, category)


# ══════════════════════════════════════════════════════════════════════════
# 反向映射 (中文 -> 英文)
# ══════════════════════════════════════════════════════════════════════════

FLAVOR_TAGS_ZH_TO_EN = {v: k for k, v in FLAVOR_TAGS.items()}
MOOD_TAGS_ZH_TO_EN = {v: k for k, v in MOOD_TAGS.items()}
GLASS_TYPES_ZH_TO_EN = {v: k for k, v in GLASS_TYPES.items()}
ABV_LEVELS_ZH_TO_EN = {v: k for k, v in ABV_LEVELS.items()}
RECIPE_TYPES_ZH_TO_EN = {v: k for k, v in RECIPE_TYPES.items()}
COCKTAIL_CATEGORIES_ZH_TO_EN = {v: k for k, v in COCKTAIL_CATEGORIES.items()}
