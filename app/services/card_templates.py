from __future__ import annotations
"""
卡片模板定义模块 v3

4 个模板：琥珀暮色 / 蓝调 / 黑 / 白

photo_area — orientation_mode: "auto"
──────────────────────────────────────
上传图片在后端/前端检测宽高，自动切换排版：

  横版图片 (width > height)
    占据卡片顶部，高度 = min(photo_h/photo_w × canvas_w/canvas_h, landscape.h_max)
    前端公式：h_frac = Math.min(img.height/img.width * (1080/1440), landscape.h_max)
    无模糊，轻叠层，底部渐变淡入背景

  竖版/方形图片 (width ≤ height)
    铺满整张卡片（h=1.0）
    无模糊，适度叠层，中下部渐变淡入背景，确保文字区可读

前端实现要点
────────────
1. 选图后立即读取 img.naturalWidth / img.naturalHeight
2. 按公式计算 h_frac，更新预览 Canvas 裁切区域
3. 叠 landscape.overlay_opacity 或 portrait.overlay_opacity 半透明矩形
4. 叠 fade LinearGradient（从 transparent 到 fade.color，区间 fade.start~fade.end，
   坐标相对于 photo_area 内部）

字体坐标系（同 v2）
────────────────────
pos_x / pos_y：归一化 0-1，乘以 1080 / 1440 得像素坐标
font_size：以 1440px 高度为基准；前端 actualSize = font_size * (canvasH / 1440)
letter_spacing：px，基准 1440px；0 = 无额外间距
line_height：行高倍数
opacity：层透明度 0-1，独立于 color
draggable：false 的层不渲染拖拽手柄，不接受 text_overrides
"""

import random
from typing import Optional

CANVAS = {"width": 1080, "height": 1440}

# ── 字体角色表 ─────────────────────────────────────────────────────────────────

FONT_ROLES: dict[str, dict] = {
    "sans_thin": {
        "css_family": "Noto Sans SC", "css_weight": 100,
        "google_fonts_url": "https://fonts.googleapis.com/css2?family=Noto+Sans+SC:wght@100",
        "backend_files": [
            "app/assets/fonts/NotoSansSC-Thin.ttf",
            "/usr/share/fonts/truetype/noto/NotoSansCJK-Regular.ttc",
            "/usr/share/fonts/opentype/noto/NotoSansCJK-Regular.ttc",
        ],
    },
    "sans_light": {
        "css_family": "Noto Sans SC", "css_weight": 300,
        "google_fonts_url": "https://fonts.googleapis.com/css2?family=Noto+Sans+SC:wght@300",
        "backend_files": [
            "app/assets/fonts/NotoSansSC-Light.ttf",
            "/usr/share/fonts/truetype/noto/NotoSansCJK-Regular.ttc",
            "/usr/share/fonts/opentype/noto/NotoSansCJK-Regular.ttc",
        ],
    },
    "sans_bold": {
        "css_family": "Noto Sans SC", "css_weight": 700,
        "google_fonts_url": "https://fonts.googleapis.com/css2?family=Noto+Sans+SC:wght@700",
        "backend_files": [
            "app/assets/fonts/NotoSansSC-Bold.ttf",
            "/usr/share/fonts/truetype/noto/NotoSansCJK-Bold.ttc",
            "/usr/share/fonts/opentype/noto/NotoSansCJK-Bold.ttc",
            "/usr/share/fonts/truetype/noto/NotoSansCJK-Regular.ttc",
        ],
    },
    "sans_black": {
        "css_family": "Noto Sans SC", "css_weight": 900,
        "google_fonts_url": "https://fonts.googleapis.com/css2?family=Noto+Sans+SC:wght@900",
        "backend_files": [
            "app/assets/fonts/NotoSansSC-Black.ttf",
            "/usr/share/fonts/truetype/noto/NotoSansCJK-Bold.ttc",
            "/usr/share/fonts/opentype/noto/NotoSansCJK-Bold.ttc",
            "/usr/share/fonts/truetype/noto/NotoSansCJK-Regular.ttc",
        ],
    },
    "serif": {
        "css_family": "Noto Serif SC", "css_weight": 400,
        "google_fonts_url": "https://fonts.googleapis.com/css2?family=Noto+Serif+SC:wght@400",
        "backend_files": [
            "app/assets/fonts/NotoSerifSC-Regular.ttf",
            "/usr/share/fonts/truetype/noto/NotoSerifCJK-Regular.ttc",
            "/usr/share/fonts/opentype/noto/NotoSerifCJK-Regular.ttc",
            "/usr/share/fonts/truetype/noto/NotoSansCJK-Regular.ttc",
        ],
    },
    "serif_semibold": {
        "css_family": "Noto Serif SC", "css_weight": 600,
        "google_fonts_url": "https://fonts.googleapis.com/css2?family=Noto+Serif+SC:wght@600",
        "backend_files": [
            "app/assets/fonts/NotoSerifSC-SemiBold.ttf",
            "/usr/share/fonts/truetype/noto/NotoSerifCJK-Bold.ttc",
            "/usr/share/fonts/opentype/noto/NotoSerifCJK-Bold.ttc",
            "/usr/share/fonts/truetype/noto/NotoSansCJK-Regular.ttc",
        ],
    },
    "serif_bold": {
        "css_family": "Noto Serif SC", "css_weight": 700,
        "google_fonts_url": "https://fonts.googleapis.com/css2?family=Noto+Serif+SC:wght@700",
        "backend_files": [
            "app/assets/fonts/NotoSerifSC-Bold.ttf",
            "/usr/share/fonts/truetype/noto/NotoSerifCJK-Bold.ttc",
            "/usr/share/fonts/opentype/noto/NotoSerifCJK-Bold.ttc",
            "/usr/share/fonts/truetype/noto/NotoSansCJK-Regular.ttc",
        ],
    },
}

# ── 预计算星点（蓝调装饰，保证前后端一致）────────────────────────────────────

def _make_dots(seed: int, count: int, region: dict,
               radii: list[float], opacity_range: tuple) -> list[dict]:
    rng = random.Random(seed)
    rx, ry, rw, rh = region["x"], region["y"], region["w"], region["h"]
    return [
        {
            "x": round(rx + rng.random() * rw, 4),
            "y": round(ry + rng.random() * rh, 4),
            "r": rng.choice(radii),
            "a": round(rng.uniform(*opacity_range), 2),
        }
        for _ in range(count)
    ]

_BLUE_STARS = _make_dots(
    seed=73, count=65,
    region={"x": 0, "y": 0, "w": 1, "h": 1},
    radii=[0.0009, 0.0009, 0.0009, 0.0018],
    opacity_range=(0.18, 0.60),
)

# ── 模板定义 ──────────────────────────────────────────────────────────────────

DEFAULT_TEMPLATE_ID = "amber"

TEMPLATES: dict[str, dict] = {

    # ══════════════════════════════════════════════════════════════════════════
    # 1. 琥珀暮色 — 暖琥珀渐变，衬线大字文案作主角
    # 横版图：照片占顶部，底部渐变淡入琥珀背景；竖版图：铺满卡片沉浸式
    # 字体：serif 大字文案 + sans_light 酒名（大字距）+ sans_thin 注脚
    # ══════════════════════════════════════════════════════════════════════════
    "amber": {
        "id": "amber",
        "name": "琥珀暮色",
        "description": "暖橘深棕，衬线文案作主角，把放松的情绪定格成画",
        "preview_hint": "琥珀渐变 · 衬线大字 · 横版顶部 / 竖版铺满",
        "canvas": CANVAS,
        "background": {
            "type": "gradient",
            "stops": [
                {"pos": 0.0, "color": "#1E0E03"},
                {"pos": 0.45, "color": "#4A2008"},
                {"pos": 1.0, "color": "#7A3510"},
            ],
        },
        "photo_area": {
            "orientation_mode": "auto",
            "fit": "cover", "shape": "rect", "blur": 0,
            "overlay_color": "#1A0800",
            "landscape": {
                "h_max": 0.50,
                "overlay_opacity": 0.22,
                "fade": {"direction": "bottom", "color": "#4A2008",
                         "start": 0.58, "end": 1.0},
            },
            "portrait": {
                "overlay_opacity": 0.46,
                "fade": {"direction": "bottom", "color": "#4A2008",
                         "start": 0.34, "end": 0.80},
            },
        },
        "text_layers": [
            {
                "id": "ai_copy",
                "data_key": "ai_copy",
                "font_role": "serif",
                "font_size": 70, "letter_spacing": 2, "line_height": 1.62,
                "color": "#FFF5E0", "opacity": 0.96,
                "pos_x": 0.07, "pos_y": 0.496, "max_width": 0.86,
                "align": "left", "draggable": True,
            },
            {
                "id": "cocktail_name_zh",
                "data_key": "cocktail_name_zh",
                "font_role": "sans_light",
                "font_size": 46, "letter_spacing": 8, "line_height": 1.2,
                "color": "#F4A460", "opacity": 1.0,
                "pos_x": 0.07, "pos_y": 0.706, "max_width": 0.86,
                "align": "left", "draggable": True,
            },
            {
                "id": "cocktail_name_en",
                "data_key": "cocktail_name",
                "font_role": "sans_thin",
                "font_size": 28, "letter_spacing": 9, "line_height": 1.2,
                "color": "#D49040", "opacity": 0.60,
                "pos_x": 0.075, "pos_y": 0.770, "max_width": 0.86,
                "align": "left", "draggable": True,
            },
            {
                "id": "mood_caption",
                "data_key": "mood_caption",
                "font_role": "sans_light",
                "font_size": 30, "letter_spacing": 0, "line_height": 1.45,
                "color": "#C89060", "opacity": 0.88,
                "pos_x": 0.07, "pos_y": 0.820, "max_width": 0.86,
                "align": "left", "draggable": True,
            },
            {
                "id": "recipe_label",
                "data_key": "custom_static", "default_text": "— 配方 —",
                "font_role": "sans_thin",
                "font_size": 22, "letter_spacing": 6, "line_height": 1.0,
                "color": "#F4A460", "opacity": 0.65,
                "pos_x": 0.07, "pos_y": 0.880, "max_width": 0.86,
                "align": "left", "draggable": False,
            },
            {
                "id": "watermark",
                "data_key": "custom_static", "default_text": "VibeMix",
                "font_role": "sans_thin",
                "font_size": 20, "letter_spacing": 5, "line_height": 1.0,
                "color": "#FFFFFF", "opacity": 0.22,
                "pos_x": 0.93, "pos_y": 0.972, "max_width": 0.30,
                "align": "right", "draggable": False,
            },
        ],
        "decorations": [],
        "show_ingredients": True,
        "ingredients_area": {
            "pos_x": 0.07, "pos_y": 0.902,
            "font_role": "sans_light", "font_size": 24,
            "col_count": 2, "row_height": 32, "max_items": 6,
            "align": "left",
            "color_owned":     "#5FCFB8",
            "color_available": "#F4C878",
            "color_missing":   "#FF8888",
            "color_unknown":   "#C8A870",
        },
    },

    # ══════════════════════════════════════════════════════════════════════════
    # 2. 蓝调 — 午夜蓝，衬线居中文案，星点背景，沉思独酌感
    # 横版图：照片占顶部；竖版图：铺满卡片，重叠层+渐变保证文字可读
    # 字体：serif 居中大字文案 + sans_bold 酒名（大字距）+ sans_thin 注脚
    # ══════════════════════════════════════════════════════════════════════════
    "blue": {
        "id": "blue",
        "name": "蓝调",
        "description": "午夜深蓝，衬线居中文案，独酌时刻最打动人的那张",
        "preview_hint": "午夜蓝渐变 · serif 居中文案 · 星点装饰",
        "canvas": CANVAS,
        "background": {
            "type": "gradient",
            "stops": [
                {"pos": 0.0, "color": "#020810"},
                {"pos": 0.5, "color": "#030C1C"},
                {"pos": 1.0, "color": "#040E22"},
            ],
        },
        "photo_area": {
            "orientation_mode": "auto",
            "fit": "cover", "shape": "rect", "blur": 0,
            "overlay_color": "#000000",
            "landscape": {
                "h_max": 0.52,
                "overlay_opacity": 0.28,
                "fade": {"direction": "bottom", "color": "#030C1C",
                         "start": 0.55, "end": 1.0},
            },
            "portrait": {
                "overlay_opacity": 0.60,
                "fade": {"direction": "bottom", "color": "#030C1C",
                         "start": 0.30, "end": 0.76},
            },
        },
        "text_layers": [
            {
                "id": "ai_copy",
                "data_key": "ai_copy",
                "font_role": "serif",
                "font_size": 62, "letter_spacing": 2, "line_height": 1.65,
                "color": "#B8D0F8", "opacity": 0.94,
                "pos_x": 0.50, "pos_y": 0.368, "max_width": 0.78,
                "align": "center", "draggable": True,
            },
            {
                "id": "cocktail_name_zh",
                "data_key": "cocktail_name_zh",
                "font_role": "sans_bold",
                "font_size": 60, "letter_spacing": 5, "line_height": 1.1,
                "color": "#E8F0FF", "opacity": 1.0,
                "pos_x": 0.50, "pos_y": 0.598, "max_width": 0.84,
                "align": "center", "draggable": True,
            },
            {
                "id": "cocktail_name_en",
                "data_key": "cocktail_name",
                "font_role": "sans_thin",
                "font_size": 26, "letter_spacing": 10, "line_height": 1.2,
                "color": "#4868A8", "opacity": 0.72,
                "pos_x": 0.50, "pos_y": 0.680, "max_width": 0.84,
                "align": "center", "draggable": True,
            },
            {
                "id": "mood_caption",
                "data_key": "mood_caption",
                "font_role": "sans_light",
                "font_size": 30, "letter_spacing": 1, "line_height": 1.50,
                "color": "#405872", "opacity": 0.85,
                "pos_x": 0.50, "pos_y": 0.736, "max_width": 0.78,
                "align": "center", "draggable": True,
            },
            {
                "id": "recipe_label",
                "data_key": "custom_static", "default_text": "— 配方 —",
                "font_role": "sans_thin",
                "font_size": 22, "letter_spacing": 6, "line_height": 1.0,
                "color": "#6888C8", "opacity": 0.60,
                "pos_x": 0.50, "pos_y": 0.822, "max_width": 0.78,
                "align": "center", "draggable": False,
            },
            {
                "id": "watermark",
                "data_key": "custom_static", "default_text": "VibeMix",
                "font_role": "sans_thin",
                "font_size": 20, "letter_spacing": 5, "line_height": 1.0,
                "color": "#FFFFFF", "opacity": 0.18,
                "pos_x": 0.93, "pos_y": 0.972, "max_width": 0.30,
                "align": "right", "draggable": False,
            },
        ],
        "decorations": [
            {
                "type": "dots",
                "points": _BLUE_STARS,
                "color": "#FFFFFF",
                "comment": "星点；前端：x*cw, y*ch, r*cw radius, globalAlpha=a",
            },
        ],
        "show_ingredients": True,
        "ingredients_area": {
            "pos_x": 0.11, "pos_y": 0.846,
            "font_role": "sans_light", "font_size": 24,
            "col_count": 2, "row_height": 32, "max_items": 6,
            "align": "left",
            "color_owned":     "#5FCFB8",
            "color_available": "#80C8FF",
            "color_missing":   "#FF8080",
            "color_unknown":   "#607898",
        },
    },

    # ══════════════════════════════════════════════════════════════════════════
    # 3. 黑 — 近黑极简，serif_bold 大字 + 金色 overline，杂志封面感
    # 横版图：顶部精确裁切；竖版图：铺满，金色文字在深色照片上清晰可读
    # 字体：serif_bold 超大标题 + sans_thin 大字距 overline + sans_light 正文
    # ══════════════════════════════════════════════════════════════════════════
    "noir": {
        "id": "noir",
        "name": "黑",
        "description": "近黑背景，serif 大字配金色细线，最高级的一张",
        "preview_hint": "近黑渐变 · serif 金标题 · 金色分隔线",
        "canvas": CANVAS,
        "background": {
            "type": "gradient",
            "stops": [
                {"pos": 0.0, "color": "#070707"},
                {"pos": 0.6, "color": "#0E0E0E"},
                {"pos": 1.0, "color": "#080808"},
            ],
        },
        "photo_area": {
            "orientation_mode": "auto",
            "fit": "cover", "shape": "rect", "blur": 0,
            "overlay_color": "#000000",
            "landscape": {
                "h_max": 0.48,
                "overlay_opacity": 0.18,
                "fade": {"direction": "bottom", "color": "#080808",
                         "start": 0.62, "end": 1.0},
            },
            "portrait": {
                "overlay_opacity": 0.38,
                "fade": {"direction": "bottom", "color": "#080808",
                         "start": 0.38, "end": 0.78},
            },
        },
        "text_layers": [
            {
                "id": "overline_static",
                "data_key": "custom_static", "default_text": "VIBEMIX  MIXOLOGY",
                "font_role": "sans_thin",
                "font_size": 18, "letter_spacing": 11, "line_height": 1.0,
                "color": "#C8A840", "opacity": 0.50,
                "pos_x": 0.06, "pos_y": 0.520, "max_width": 0.88,
                "align": "left", "draggable": False,
            },
            {
                "id": "cocktail_name_zh",
                "data_key": "cocktail_name_zh",
                "font_role": "serif_bold",
                "font_size": 90, "letter_spacing": 1, "line_height": 1.1,
                "color": "#F5E6C8", "opacity": 1.0,
                "pos_x": 0.06, "pos_y": 0.548, "max_width": 0.88,
                "align": "left", "draggable": True,
            },
            {
                "id": "cocktail_name_en",
                "data_key": "cocktail_name",
                "font_role": "sans_thin",
                "font_size": 26, "letter_spacing": 9, "line_height": 1.2,
                "color": "#C8A840", "opacity": 0.85,
                "pos_x": 0.065, "pos_y": 0.682, "max_width": 0.88,
                "align": "left", "draggable": True,
            },
            {
                "id": "ai_copy",
                "data_key": "ai_copy",
                "font_role": "sans_light",
                "font_size": 32, "letter_spacing": 0, "line_height": 1.55,
                "color": "#C8C0B0", "opacity": 0.90,
                "pos_x": 0.06, "pos_y": 0.730, "max_width": 0.88,
                "align": "left", "draggable": True,
            },
            {
                "id": "recipe_label",
                "data_key": "custom_static", "default_text": "RECIPE  配方",
                "font_role": "sans_thin",
                "font_size": 20, "letter_spacing": 8, "line_height": 1.0,
                "color": "#C8A840", "opacity": 0.55,
                "pos_x": 0.06, "pos_y": 0.858, "max_width": 0.88,
                "align": "left", "draggable": False,
            },
            {
                "id": "watermark",
                "data_key": "custom_static", "default_text": "VibeMix × 本期调制",
                "font_role": "sans_thin",
                "font_size": 18, "letter_spacing": 6, "line_height": 1.0,
                "color": "#C8A840", "opacity": 0.30,
                "pos_x": 0.94, "pos_y": 0.972, "max_width": 0.48,
                "align": "right", "draggable": False,
            },
        ],
        "decorations": [
            {
                "type": "line",
                "x1": 0.06, "y1": 0.538, "x2": 0.94, "y2": 0.538,
                "color": "#C8A840", "opacity": 0.40, "thickness": 1,
            },
        ],
        "show_ingredients": True,
        "ingredients_area": {
            "pos_x": 0.06, "pos_y": 0.882,
            "font_role": "sans_light", "font_size": 24,
            "col_count": 2, "row_height": 32, "max_items": 6,
            "align": "left",
            "color_owned":     "#5FCFB8",
            "color_available": "#C8A840",
            "color_missing":   "#FF8080",
            "color_unknown":   "#A09070",
        },
    },

    # ══════════════════════════════════════════════════════════════════════════
    # 4. 白 — 纯白底色，sans_black vs sans_thin 极端字重对比
    # 横版图：顶部条带，图片底部渐变淡入白色；竖版图：铺满，强渐变到白，确保文字区纯白
    # 字体：sans_black 超大酒名 + sans_thin 极细正文，斯堪的纳维亚极简美学
    # ══════════════════════════════════════════════════════════════════════════
    "white": {
        "id": "white",
        "name": "白",
        "description": "白底黑字，Black 与 Thin 双极对比，极简中的高级感",
        "preview_hint": "白底 · Black 超大酒名 · 横版顶部 / 竖版渐变到白",
        "canvas": CANVAS,
        "background": {
            "type": "gradient",
            "stops": [
                {"pos": 0.0, "color": "#F8F8F8"},
                {"pos": 1.0, "color": "#F2F2F0"},
            ],
        },
        "photo_area": {
            "orientation_mode": "auto",
            "fit": "cover", "shape": "rect", "blur": 0,
            "overlay_color": "#F8F8F8",
            "landscape": {
                "h_max": 0.46,
                "overlay_opacity": 0.04,
                "fade": {"direction": "bottom", "color": "#F8F8F8",
                         "start": 0.68, "end": 1.0},
            },
            "portrait": {
                "overlay_opacity": 0.05,
                # 竖版：中段强渐变至白，确保 y≥0.58 为纯白背景供深色文字
                "fade": {"direction": "bottom", "color": "#F8F8F8",
                         "start": 0.30, "end": 0.58},
            },
        },
        "text_layers": [
            {
                "id": "cocktail_name_zh",
                "data_key": "cocktail_name_zh",
                "font_role": "sans_black",
                "font_size": 100, "letter_spacing": -2, "line_height": 1.05,
                "color": "#141414", "opacity": 1.0,
                "pos_x": 0.06, "pos_y": 0.512, "max_width": 0.88,
                "align": "left", "draggable": True,
            },
            {
                "id": "cocktail_name_en",
                "data_key": "cocktail_name",
                "font_role": "sans_thin",
                "font_size": 28, "letter_spacing": 9, "line_height": 1.2,
                "color": "#888888", "opacity": 0.80,
                "pos_x": 0.065, "pos_y": 0.642, "max_width": 0.88,
                "align": "left", "draggable": True,
            },
            {
                "id": "ai_copy",
                "data_key": "ai_copy",
                "font_role": "sans_thin",
                "font_size": 34, "letter_spacing": 1, "line_height": 1.62,
                "color": "#404040", "opacity": 0.88,
                "pos_x": 0.06, "pos_y": 0.698, "max_width": 0.88,
                "align": "left", "draggable": True,
            },
            {
                "id": "recipe_label",
                "data_key": "custom_static", "default_text": "— 配方 —",
                "font_role": "sans_thin",
                "font_size": 22, "letter_spacing": 5, "line_height": 1.0,
                "color": "#141414", "opacity": 0.38,
                "pos_x": 0.06, "pos_y": 0.836, "max_width": 0.88,
                "align": "left", "draggable": False,
            },
            {
                "id": "watermark",
                "data_key": "custom_static", "default_text": "VibeMix",
                "font_role": "sans_thin",
                "font_size": 18, "letter_spacing": 7, "line_height": 1.0,
                "color": "#AAAAAA", "opacity": 0.50,
                "pos_x": 0.93, "pos_y": 0.972, "max_width": 0.28,
                "align": "right", "draggable": False,
            },
        ],
        "decorations": [
            {
                "type": "line",
                "x1": 0.06, "y1": 0.500, "x2": 0.28, "y2": 0.500,
                "color": "#141414", "opacity": 0.28, "thickness": 1,
            },
        ],
        "show_ingredients": True,
        "ingredients_area": {
            "pos_x": 0.06, "pos_y": 0.858,
            "font_role": "sans_thin", "font_size": 24,
            "col_count": 2, "row_height": 32, "max_items": 6,
            "align": "left",
            "color_owned":     "#1A8A6A",
            "color_available": "#1A5FAA",
            "color_missing":   "#CC2020",
            "color_unknown":   "#444444",
        },
    },
}

# ── 辅助函数 ───────────────────────────────────────────────────────────────────

def get_template(template_id: str) -> Optional[dict]:
    return TEMPLATES.get(template_id)


def get_template_or_default(template_id: Optional[str]) -> dict:
    if template_id and template_id in TEMPLATES:
        return TEMPLATES[template_id]
    return TEMPLATES[DEFAULT_TEMPLATE_ID]


def list_templates() -> list[dict]:
    return [
        {
            "id": t["id"],
            "name": t["name"],
            "description": t["description"],
            "preview_hint": t.get("preview_hint", ""),
            "has_photo_area": t.get("photo_area") is not None,
            "show_ingredients": t.get("show_ingredients", False),
            "bg_stops": t["background"]["stops"],
        }
        for t in TEMPLATES.values()
    ]


def get_required_font_roles(template_id: str) -> list[str]:
    tmpl = get_template(template_id)
    if not tmpl:
        return []
    roles = {layer["font_role"] for layer in tmpl.get("text_layers", [])}
    ia = tmpl.get("ingredients_area")
    if ia and "font_role" in ia:
        roles.add(ia["font_role"])
    return sorted(roles)
