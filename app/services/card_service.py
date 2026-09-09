from __future__ import annotations
"""
卡片合成服务 v3

合成层次（底 → 顶）
───────────────────
1. 背景渐变（gradient stops）
2. 用户照片（photo_area，自动横竖版布局，无模糊）
3. 装饰层（decorations list）
4. 文字层（text_layers，应用 text_overrides 位置覆盖）
5. 食材列表（show_ingredients=True 时）

固定输出：portrait 750×1000 JPEG。

orientation_mode: "auto" 处理逻辑
──────────────────────────────────
检测上传图片宽高比：
  横版 (width > height)：照片占据卡片顶部
    - 高度 = min(photo_h/photo_w × 750/1000, landscape.h_max)  （归一化）
    - 轻叠层 + 底部渐变淡入背景色
  竖版/方形 (width ≤ height)：照片铺满整张卡片
    - rect = {x:0, y:0, w:1, h:1}
    - 适度叠层 + 中下部渐变淡入背景，确保文字区可读

照片不做高斯模糊（blur 固定为 0）。
"""
import io
import logging
import math
import os
import urllib.request
from dataclasses import dataclass, field
from functools import lru_cache
from typing import Optional

from PIL import Image, ImageDraw, ImageFilter, ImageFont

from .card_templates import FONT_ROLES, DEFAULT_TEMPLATE_ID, get_template_or_default

logger = logging.getLogger(__name__)

CANVAS_W, CANVAS_H = 750, 1000

# 相对路径基准
_BASE_DIR = os.path.dirname(os.path.dirname(__file__))  # app/


# ── Data container ─────────────────────────────────────────────────────────────

@dataclass
class CardParams:
    cocktail_name: str
    cocktail_name_zh: str
    ai_copy: str
    mood_caption: str
    ingredients: list[dict]
    user_photo_url: Optional[str]
    template_id: str = DEFAULT_TEMPLATE_ID
    text_overrides: dict = field(default_factory=dict)

    @property
    def ingredients_brief(self) -> str:
        parts = []
        for ing in self.ingredients[:5]:
            name = ing.get("name_zh") or ing.get("name", "")
            measure = ing.get("measure_raw", "")
            if name:
                parts.append(f"{name} {measure}".strip())
        return "  ·  ".join(parts)


# ── Font loading ───────────────────────────────────────────────────────────────

# Fallback font paths（系统 Noto CJK）
_FALLBACK_FONTS = [
    "/usr/share/fonts/truetype/noto/NotoSansCJK-Regular.ttc",
    "/usr/share/fonts/opentype/noto/NotoSansCJK-Regular.ttc",
    "/usr/share/fonts/noto-cjk/NotoSansCJK-Regular.ttc",
    "/System/Library/Fonts/PingFang.ttc",
    "/usr/share/fonts/truetype/liberation/LiberationSans-Regular.ttf",
]


@lru_cache(maxsize=128)
def _load_font(role: str, size: int) -> ImageFont.ImageFont:
    """Load font for a given role and pixel size, with fallback chain."""
    candidates: list[str] = []

    if role in FONT_ROLES:
        for path in FONT_ROLES[role]["backend_files"]:
            # Support both absolute and relative paths
            if not os.path.isabs(path):
                path = os.path.join(_BASE_DIR, path)
            candidates.append(path)

    candidates.extend(_FALLBACK_FONTS)

    for path in candidates:
        if os.path.exists(path):
            try:
                return ImageFont.truetype(path, size)
            except Exception:
                continue

    return ImageFont.load_default()


# ── Main service ───────────────────────────────────────────────────────────────

class CardService:

    def generate_card(self, params: CardParams) -> bytes:
        template = get_template_or_default(params.template_id)
        canvas = Image.new("RGB", (CANVAS_W, CANVAS_H))

        self._draw_background(canvas, template["background"])

        photo_area = template.get("photo_area")
        if photo_area and params.user_photo_url:
            try:
                self._composite_photo(canvas, params.user_photo_url, photo_area)
            except Exception as e:
                logger.warning("Failed to load user photo: %s", e)

        self._draw_decorations(canvas, template.get("decorations", []))

        data_map = self._build_data_map(params)
        draw = ImageDraw.Draw(canvas)

        for layer in template.get("text_layers", []):
            if not layer.get("visible", True):
                continue
            self._render_text_layer(draw, canvas, layer, data_map,
                                    params.text_overrides)

        if template.get("show_ingredients"):
            ing_area = template.get("ingredients_area", {})
            self._draw_ingredients(draw, canvas, params.ingredients, ing_area)

        buf = io.BytesIO()
        canvas.save(buf, format="JPEG", quality=92, optimize=True)
        return buf.getvalue()

    # ── Background ─────────────────────────────────────────────────────────────

    def _draw_background(self, canvas: Image.Image, bg: dict) -> None:
        w, h = canvas.size
        stops = bg["stops"]  # [{"pos": 0.0, "color": "#rrggbb"}, ...]
        draw = ImageDraw.Draw(canvas)

        if len(stops) == 1:
            draw.rectangle([(0, 0), (w, h)], fill=self._hex_rgb(stops[0]["color"]))
            return

        for y in range(h):
            frac = y / (h - 1)
            # Find surrounding stops
            lo = stops[0]
            hi = stops[-1]
            for i in range(len(stops) - 1):
                if stops[i]["pos"] <= frac <= stops[i + 1]["pos"]:
                    lo, hi = stops[i], stops[i + 1]
                    break
            span = hi["pos"] - lo["pos"]
            t = (frac - lo["pos"]) / span if span > 0 else 0
            c1 = self._hex_rgb(lo["color"])
            c2 = self._hex_rgb(hi["color"])
            r = int(c1[0] + (c2[0] - c1[0]) * t)
            g = int(c1[1] + (c2[1] - c1[1]) * t)
            b = int(c1[2] + (c2[2] - c1[2]) * t)
            draw.line([(0, y), (w, y)], fill=(r, g, b))

    # ── Photo compositing ──────────────────────────────────────────────────────

    def _resolve_photo_area(self, area: dict, img_w: int, img_h: int) -> dict:
        """
        将 orientation_mode="auto" 的 photo_area 按实际图片宽高比解析为
        含有具体 rect / overlay_opacity / fade 的 flat dict，供后续合成使用。
        """
        is_landscape = img_w > img_h
        if is_landscape:
            mode = area["landscape"]
            # 横版：照片按原始宽高比缩放填满卡片宽度，高度归一化（相对 1440px）
            # h_frac = (photo_h / photo_w) × (canvas_w / canvas_h)
            h_frac = min((img_h / img_w) * (CANVAS_W / CANVAS_H),
                         mode["h_max"])
            rect = {"x": 0.0, "y": 0.0, "w": 1.0, "h": round(h_frac, 4)}
        else:
            mode = area["portrait"]
            rect = {"x": 0.0, "y": 0.0, "w": 1.0, "h": 1.0}

        return {
            "rect":            rect,
            "fit":             area.get("fit", "cover"),
            "shape":           area.get("shape", "rect"),
            "corner_radius":   area.get("corner_radius", 0.06),
            "overlay_color":   area.get("overlay_color", "#000000"),
            "overlay_opacity": mode["overlay_opacity"],
            "blur":            0,  # 永不模糊
            "fade":            mode.get("fade"),
        }

    def _composite_photo(self, canvas: Image.Image, photo_url: str,
                         area: dict) -> None:
        data = self._fetch_image(photo_url)
        img_raw = Image.open(io.BytesIO(data))

        # Resolve orientation-aware area if needed
        if area.get("orientation_mode") == "auto":
            effective = self._resolve_photo_area(area, img_raw.width, img_raw.height)
        else:
            effective = area

        cw, ch = canvas.size
        rect = effective["rect"]
        px = int(rect["x"] * cw)
        py = int(rect["y"] * ch)
        pw = int(rect["w"] * cw)
        ph = int(rect["h"] * ch)
        if pw <= 0 or ph <= 0:
            return

        photo = img_raw.convert("RGBA")

        # cover fit
        ratio = max(pw / photo.width, ph / photo.height)
        nw = int(photo.width * ratio)
        nh = int(photo.height * ratio)
        photo = photo.resize((nw, nh), Image.LANCZOS)
        left = (nw - pw) // 2
        top = (nh - ph) // 2
        photo = photo.crop((left, top, left + pw, top + ph))

        # Solid overlay
        ov_opacity = effective.get("overlay_opacity", 0)
        if ov_opacity > 0:
            ov_color = self._hex_rgb(effective.get("overlay_color", "#000000"))
            overlay = Image.new("RGBA", photo.size, (*ov_color, int(ov_opacity * 255)))
            photo = Image.alpha_composite(photo, overlay)

        # Directional fade — gradient from transparent to bg color
        fade = effective.get("fade")
        if fade:
            photo = self._apply_fade(photo, fade)

        # Shape mask
        shape = effective.get("shape", "rect")
        if shape == "circle":
            photo = self._apply_circle_mask(photo)
        elif shape == "rounded":
            radius_norm = effective.get("corner_radius", 0.06)
            radius_px = max(4, int(radius_norm * min(pw, ph)))
            photo = self._apply_rounded_mask(photo, radius_px)

        # Composite onto canvas
        if shape in ("circle", "rounded"):
            region = canvas.crop((px, py, px + pw, py + ph)).convert("RGBA")
            composited = Image.alpha_composite(region, photo)
            canvas.paste(composited.convert("RGB"), (px, py))
        else:
            canvas.paste(photo.convert("RGB"), (px, py))

    def _apply_fade(self, photo: Image.Image, fade: dict) -> Image.Image:
        """Blend photo edge into a solid color via a directional gradient."""
        pw, ph = photo.size
        direction = fade.get("direction", "bottom")
        color = self._hex_rgb(fade.get("color", "#000000"))
        start = fade.get("start", 0.6)
        end = fade.get("end", 1.0)

        overlay = Image.new("RGBA", photo.size, (0, 0, 0, 0))
        draw = ImageDraw.Draw(overlay)

        if direction == "bottom":
            s_px = int(start * ph)
            e_px = int(end * ph)
            for y in range(s_px, ph):
                t = min(1.0, (y - s_px) / max(e_px - s_px, 1))
                a = int(255 * t)
                draw.line([(0, y), (pw - 1, y)], fill=(*color, a))
        elif direction == "top":
            s_px = int((1 - end) * ph)
            e_px = int((1 - start) * ph)
            for y in range(0, e_px):
                t = min(1.0, (e_px - y) / max(e_px - s_px, 1))
                a = int(255 * t)
                draw.line([(0, y), (pw - 1, y)], fill=(*color, a))
        elif direction == "left":
            s_px = int((1 - end) * pw)
            e_px = int((1 - start) * pw)
            for x in range(0, e_px):
                t = min(1.0, (e_px - x) / max(e_px - s_px, 1))
                a = int(255 * t)
                draw.line([(x, 0), (x, ph - 1)], fill=(*color, a))
        elif direction == "right":
            s_px = int(start * pw)
            e_px = int(end * pw)
            for x in range(s_px, pw):
                t = min(1.0, (x - s_px) / max(e_px - s_px, 1))
                a = int(255 * t)
                draw.line([(x, 0), (x, ph - 1)], fill=(*color, a))

        return Image.alpha_composite(photo, overlay)

    def _apply_circle_mask(self, img: Image.Image) -> Image.Image:
        """Crop image to inscribed circle, alpha outside."""
        img = img.convert("RGBA")
        pw, ph = img.size
        mask = Image.new("L", (pw, ph), 0)
        draw = ImageDraw.Draw(mask)
        r = min(pw, ph) // 2
        cx, cy = pw // 2, ph // 2
        draw.ellipse([(cx - r, cy - r), (cx + r, cy + r)], fill=255)
        img.putalpha(mask)
        return img

    def _apply_rounded_mask(self, img: Image.Image, radius: int) -> Image.Image:
        """Apply rounded rectangle alpha mask."""
        img = img.convert("RGBA")
        mask = Image.new("L", img.size, 0)
        draw = ImageDraw.Draw(mask)
        draw.rounded_rectangle([(0, 0), (img.width - 1, img.height - 1)],
                                radius=radius, fill=255)
        img.putalpha(mask)
        return img

    # ── Decorations ────────────────────────────────────────────────────────────

    def _draw_decorations(self, canvas: Image.Image,
                          decorations: list[dict]) -> None:
        w, h = canvas.size
        draw = ImageDraw.Draw(canvas, "RGBA")

        for dec in decorations:
            t = dec.get("type")

            if t == "line":
                x1 = int(dec["x1"] * w)
                y1 = int(dec["y1"] * h)
                x2 = int(dec["x2"] * w)
                y2 = int(dec["y2"] * h)
                color = self._hex_rgb(dec["color"])
                a = int(dec.get("opacity", 1.0) * 255)
                thick = max(1, dec.get("thickness", 1))
                draw.line([(x1, y1), (x2, y2)], fill=(*color, a), width=thick)

            elif t == "dashes":
                y_px = int(dec["y"] * h)
                x_start = int(dec["x_start"] * w)
                x_end = int(dec["x_end"] * w)
                color = self._hex_rgb(dec["color"])
                a = int(dec.get("opacity", 1.0) * 255)
                thick = max(1, dec.get("thickness", 1))
                dash = dec.get("dash", 20)
                gap = dec.get("gap", 12)
                x = x_start
                while x < x_end:
                    end_x = min(x + dash, x_end)
                    draw.line([(x, y_px), (end_x, y_px)],
                               fill=(*color, a), width=thick)
                    x += dash + gap

            elif t == "dots":
                color = self._hex_rgb(dec.get("color", "#FFFFFF"))
                for pt in dec.get("points", []):
                    px_x = int(pt["x"] * w)
                    px_y = int(pt["y"] * h)
                    # radius is normalized relative to canvas width
                    r = max(1, int(pt["r"] * w))
                    a = int(pt["a"] * 255)
                    draw.ellipse(
                        [(px_x - r, px_y - r), (px_x + r, px_y + r)],
                        fill=(*color, a),
                    )

            elif t == "radial_gradient":
                # Approximate radial gradient with concentric ellipses
                cx = int(dec["cx"] * w)
                cy = int(dec["cy"] * h)
                rx = int(dec["rx"] * w)
                ry = int(dec["ry"] * h)
                stops = dec.get("stops", [])
                if len(stops) < 2:
                    continue
                steps = 40
                for i in range(steps, 0, -1):
                    frac = i / steps
                    # Interpolate color stop
                    lo, hi = stops[0], stops[-1]
                    for j in range(len(stops) - 1):
                        if stops[j]["pos"] <= frac <= stops[j + 1]["pos"]:
                            lo, hi = stops[j], stops[j + 1]
                            break
                    span = hi["pos"] - lo["pos"]
                    t_val = (frac - lo["pos"]) / span if span > 0 else 0
                    c1 = self._hex_rgb(lo["color"])
                    c2 = self._hex_rgb(hi["color"])
                    r_mix = int(c1[0] + (c2[0] - c1[0]) * t_val)
                    g_mix = int(c1[1] + (c2[1] - c1[1]) * t_val)
                    b_mix = int(c1[2] + (c2[2] - c1[2]) * t_val)
                    a_mix = int((lo["opacity"] + (hi["opacity"] - lo["opacity"]) * t_val) * 255)
                    er = max(2, int(rx * frac))
                    eh = max(2, int(ry * frac))
                    draw.ellipse(
                        [(cx - er, cy - eh), (cx + er, cy + eh)],
                        fill=(r_mix, g_mix, b_mix, a_mix),
                    )

    # ── Text layers ────────────────────────────────────────────────────────────

    def _build_data_map(self, params: CardParams) -> dict[str, str]:
        return {
            "cocktail_name_zh":  params.cocktail_name_zh or params.cocktail_name,
            "cocktail_name":     params.cocktail_name,
            "ai_copy":           params.ai_copy or "",
            "mood_caption":      params.mood_caption or "",
            "ingredients_brief": params.ingredients_brief,
            "custom_static":     "",
        }

    def _render_text_layer(self, draw: ImageDraw.Draw, canvas: Image.Image,
                           layer: dict, data_map: dict,
                           overrides: dict) -> None:
        data_key = layer.get("data_key", "custom_static")
        if data_key == "custom_static":
            text = layer.get("default_text", "")
        else:
            text = data_map.get(data_key, "") or layer.get("default_text", "")
        if not text:
            return

        w, h = canvas.size
        role = layer.get("font_role", "sans")
        font_size = max(10, layer.get("font_size", 32))
        font = _load_font(role, font_size)

        color_rgb = self._hex_rgb(layer.get("color", "#FFFFFF"))
        layer_opacity = layer.get("opacity", 1.0)
        fill = (*color_rgb, int(255 * layer_opacity))

        letter_spacing = layer.get("letter_spacing", 0)
        line_height_mult = layer.get("line_height", 1.4)
        align = layer.get("align", "left")
        max_width_px = int(layer.get("max_width", 0.88) * w)

        # Apply position override (draggable layers only)
        override = overrides.get(layer["id"], {}) if layer.get("draggable", True) else {}
        pos_x = override.get("x", layer["pos_x"])
        pos_y = override.get("y", layer["pos_y"])

        x_ref = int(pos_x * w)
        y = int(pos_y * h)

        wrapped = self._wrap_text(draw, text, font, max_width_px, letter_spacing)

        for line in wrapped:
            line_w = self._measure_line(draw, line, font, letter_spacing)
            if align == "center":
                x = x_ref - line_w // 2
            elif align == "right":
                x = x_ref - line_w
            else:
                x = x_ref
            x = max(0, min(x, w - 1))

            self._draw_line_with_spacing(draw, x, y, line, font, fill, letter_spacing)

            # Line height: use font's actual line height * multiplier
            bbox = draw.textbbox((0, 0), "A", font=font)
            char_h = bbox[3] - bbox[1]
            y += int(char_h * line_height_mult)

    def _draw_line_with_spacing(self, draw: ImageDraw.Draw, x: int, y: int,
                                 text: str, font: ImageFont.ImageFont,
                                 fill: tuple, spacing: int) -> None:
        if spacing == 0:
            draw.text((x, y), text, font=font, fill=fill)
            return
        for char in text:
            draw.text((x, y), char, font=font, fill=fill)
            bbox = draw.textbbox((0, 0), char, font=font)
            x += (bbox[2] - bbox[0]) + spacing

    def _measure_line(self, draw: ImageDraw.Draw, text: str,
                       font: ImageFont.ImageFont, spacing: int) -> int:
        if not text:
            return 0
        if spacing == 0:
            bbox = draw.textbbox((0, 0), text, font=font)
            return bbox[2] - bbox[0]
        total = 0
        for i, char in enumerate(text):
            bbox = draw.textbbox((0, 0), char, font=font)
            total += bbox[2] - bbox[0]
            if i < len(text) - 1:
                total += spacing
        return total

    def _wrap_text(self, draw: ImageDraw.Draw, text: str,
                   font: ImageFont.ImageFont,
                   max_width: int, spacing: int) -> list[str]:
        lines: list[str] = []
        for paragraph in text.split("\n"):
            if not paragraph:
                lines.append("")
                continue
            current = ""
            for char in paragraph:
                test = current + char
                if self._measure_line(draw, test, font, spacing) <= max_width:
                    current = test
                else:
                    if current:
                        lines.append(current)
                    current = char
            if current:
                lines.append(current)
        return lines or [""]

    # ── Ingredients list ───────────────────────────────────────────────────────

    def _draw_ingredients(self, draw: ImageDraw.Draw, canvas: Image.Image,
                          ingredients: list[dict], area: dict) -> None:
        w, h = canvas.size
        role = area.get("font_role", "sans_light")
        font_size = area.get("font_size", 28)
        font = _load_font(role, font_size)
        align = area.get("align", "left")
        col_count = area.get("col_count", 2)
        row_height = area.get("row_height", 44)
        max_items = area.get("max_items", 8)

        x_ref = int(area.get("pos_x", 0.06) * w)
        y_start = int(area.get("pos_y", 0.64) * h)
        col_width = (w - x_ref * 2) // col_count

        items = ingredients[:max_items]
        for i, ing in enumerate(items):
            col = i % col_count
            row = i // col_count
            status = ing.get("status", "unknown")
            color_hex = {
                "owned":     area.get("color_owned",     "#5FCFB8"),
                "available": area.get("color_available", "#80D0FF"),
                "missing":   area.get("color_missing",   "#FF8080"),
            }.get(status, area.get("color_unknown", "#C8C8C8"))
            fill = (*self._hex_rgb(color_hex), 255)

            name = ing.get("name_zh") or ing.get("name", "")
            measure = ing.get("measure_raw", "")
            text = f"• {name} {measure}".strip()

            line_w = self._measure_line(draw, text, font, 0)
            if align == "center":
                x = x_ref - line_w // 2 + col * col_width
            else:
                x = x_ref + col * col_width

            draw.text((x, y_start + row * row_height), text, font=font, fill=fill)

    # ── Utilities ──────────────────────────────────────────────────────────────

    def _hex_rgb(self, hex_str: str) -> tuple[int, int, int]:
        s = hex_str.lstrip("#")
        if len(s) == 3:
            s = "".join(c * 2 for c in s)
        s = s[:6]  # take first 6 chars regardless of RRGGBBAA input
        return (int(s[0:2], 16), int(s[2:4], 16), int(s[4:6], 16))

    def _fetch_image(self, url: str) -> bytes:
        if url.startswith("file://"):
            path = url[len("file://"):]
            with open(path, "rb") as f:
                return f.read()
        req = urllib.request.Request(url, headers={"User-Agent": "VibeMix/1.0"})
        with urllib.request.urlopen(req, timeout=8) as resp:
            return resp.read()


card_service = CardService()
