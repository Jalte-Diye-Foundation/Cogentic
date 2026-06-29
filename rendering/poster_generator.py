"""PIL-based poster rendering using ratio-based theme layouts."""

from __future__ import annotations

import logging
import os
from typing import Any

from PIL import Image, ImageDraw, ImageFont

logger = logging.getLogger(__name__)

# ---------- THEME REGISTRY (copy from your standalone script) ----------
THEME_REGISTRY = {
    "Climate & Environment": {
        "quote_color": "#15803d",
        "explanation_color": "#166534",
        "quote_align": "RIGHT",
        "expl_align": "LEFT",
        "margin_left_ratio": 0.22,
        "margin_right_ratio": 0.26,
        "center_zone_top_ratio": 0.18,
        "center_zone_bottom_ratio": 0.55,
    },
    "Health & Mindfulness": {
        "quote_color": "#8c6239",
        "explanation_color": "#a17850",
        "quote_align": "RIGHT",
        "expl_align": "LEFT",
        "margin_left_ratio": 0.20,
        "margin_right_ratio": 0.20,
        "center_zone_top_ratio": 0.08,
        "center_zone_bottom_ratio": 0.46,
    },
    "Women Empowerment": {
        "quote_color": "#dd1c4b",
        "explanation_color": "#b9123c",
        "quote_align": "LEFT",        # <-- changed from RIGHT to LEFT
        "expl_align": "LEFT",
        "margin_left_ratio": 0.24,
        "margin_right_ratio": 0.22,
        "center_zone_top_ratio": 0.39,
        "center_zone_bottom_ratio": 0.75,
    },
    "Social Education": {
        "quote_color": "#b91c1c",
        "explanation_color": "#b91c1c",
        "quote_align": "LEFT",
        "expl_align": "RIGHT",
        "margin_left_ratio": 0.22,
        "margin_right_ratio": 0.22,
        "center_zone_top_ratio": 0.38,
        "center_zone_bottom_ratio": 0.74,
    },
    "Quality Education": {
        "quote_color": "#b91c1c",
        "explanation_color": "#b91c1c",
        "quote_align": "LEFT",
        "expl_align": "RIGHT",
        "margin_left_ratio": 0.22,
        "margin_right_ratio": 0.22,
        "center_zone_top_ratio": 0.38,
        "center_zone_bottom_ratio": 0.74,
    },
    "Peace & Justice": {
        "quote_color": "#00689d",
        "explanation_color": "#005580",
        "quote_align": "LEFT",
        "expl_align": "RIGHT",
        "margin_left_ratio": 0.22,
        "margin_right_ratio": 0.24,
        "center_zone_top_ratio": 0.18,
        "center_zone_bottom_ratio": 0.55,
    },
    "Foundation Events": {
        "quote_color": "#8c6239",
        "explanation_color": "#a17850",
        "quote_align": "RIGHT",
        "expl_align": "LEFT",
        "margin_left_ratio": 0.20,
        "margin_right_ratio": 0.20,
        "center_zone_top_ratio": 0.08,
        "center_zone_bottom_ratio": 0.46,
    },
    "jdf_general": {
        "quote_color": "#8c6239",
        "explanation_color": "#a17850",
        "quote_align": "RIGHT",
        "expl_align": "LEFT",
        "margin_left_ratio": 0.20,
        "margin_right_ratio": 0.20,
        "center_zone_top_ratio": 0.12,
        "center_zone_bottom_ratio": 0.46,
    },
}

GLOBAL_LAYOUT = {
    "font_name": "Raleway-ExtraLight.ttf",
    "quote_font_size": 48,
    "explanation_font_size": 26,
    "explanation_font_weight": 300,
    "line_spacing": 12,
    "block_gap": 35,
}

# ---------- Helper functions ----------
def load_font(font_name, size, project_root, weight=None):
    search_paths = [
        os.path.join(project_root, font_name),
        os.path.join(project_root, "fonts", font_name),
        os.path.join("C:/Windows/Fonts", font_name),
        font_name,
    ]
    for path in search_paths:
        try:
            font = ImageFont.truetype(path, size)
            if weight is not None and hasattr(font, "set_variation_by_axes"):
                try:
                    font.set_variation_by_axes([weight])
                except Exception:
                    pass
            return font
        except (IOError, OSError):
            continue
    logger.warning(f"Could not find '{font_name}'. Using default font.")
    return ImageFont.load_default()

def measure_text_width(text, font, draw):
    if not text:
        return 0
    bb = draw.textbbox((0, 0), text, font=font)
    return bb[2] - bb[0]

def wrap_text(text, font, draw, max_width):
    words = text.split()
    lines, current = [], []
    for word in words:
        test = " ".join(current + [word])
        if measure_text_width(test, font, draw) <= max_width:
            current.append(word)
        else:
            if current:
                lines.append(" ".join(current))
            current = [word]
    if current:
        lines.append(" ".join(current))
    return lines

def text_height(text, font, draw):
    bb = draw.textbbox((0, 0), text, font=font)
    return bb[3] - bb[1]

def block_height(lines, font, draw, line_spacing):
    if not lines:
        return 0
    return sum(text_height(line, font, draw) + line_spacing for line in lines) - line_spacing

# ---------- Main PosterGenerator class ----------
class PosterGenerator:
    def __init__(self, config: dict[str, Any], project_root: str):
        self.config = config
        self.project_root = project_root
        self.poster_config = config["poster"]
        self.fonts = self.poster_config["fonts"]

    def render(
        self,
        quote: str,
        explanation: str,
        background_path: str,
        output_path: str,
        layout_name: str,          # kept for compatibility
        theme: str | None = None,
    ) -> str:
        # Determine theme config
        if theme is None:
            folder = os.path.basename(os.path.dirname(background_path))
            folder_to_theme = {
                "climate": "Climate & Environment",
                "health": "Health & Mindfulness",
                "women": "Women Empowerment",
                "education": "Quality Education",
                "peace": "Peace & Justice",
                "events": "Foundation Events",
            }
            theme = folder_to_theme.get(folder, "jdf_general")
            logger.info(f"Inferred theme from folder: {theme}")

        cfg = THEME_REGISTRY.get(theme, THEME_REGISTRY["jdf_general"])
        logger.info(f"Using theme config for: {theme}")

        if not os.path.exists(background_path):
            raise FileNotFoundError(f"Background missing: {background_path}")

        img = Image.open(background_path).convert("RGB")
        W, H = img.size
        draw = ImageDraw.Draw(img)

        quote_font = load_font(
            GLOBAL_LAYOUT["font_name"],
            GLOBAL_LAYOUT["quote_font_size"],
            self.project_root,
        )
        explanation_font = load_font(
            GLOBAL_LAYOUT["font_name"],
            GLOBAL_LAYOUT["explanation_font_size"],
            self.project_root,
            GLOBAL_LAYOUT["explanation_font_weight"],
        )

        margin_left = int(W * cfg["margin_left_ratio"])
        margin_right = int(W * cfg["margin_right_ratio"])
        max_text_width = W - margin_left - margin_right

        zone_top = int(H * cfg["center_zone_top_ratio"])
        zone_bottom = int(H * cfg["center_zone_bottom_ratio"])
        zone_height = zone_bottom - zone_top

        clean_quote = quote.strip().replace("\n", " ")
        clean_expl = explanation.strip().replace("\n", " ")

        quote_lines = wrap_text(clean_quote, quote_font, draw, max_text_width)
        expl_lines = wrap_text(clean_expl, explanation_font, draw, max_text_width)

        quote_block_h = block_height(quote_lines, quote_font, draw, GLOBAL_LAYOUT["line_spacing"])
        expl_block_h = block_height(expl_lines, explanation_font, draw, GLOBAL_LAYOUT["line_spacing"])
        total_content_h = quote_block_h + GLOBAL_LAYOUT["block_gap"] + expl_block_h

        y_cursor = zone_top + max(0, (zone_height - total_content_h) // 2)

        if quote_lines:
            quote_multiline = "\n".join(quote_lines)
            if cfg["quote_align"] == "LEFT":
                x_pos = margin_left
                align = "left"
            else:
                x_pos = W - margin_right
                align = "right"
            draw.multiline_text(
                (x_pos, y_cursor),
                quote_multiline,
                font=quote_font,
                fill=cfg["quote_color"],
                align=align,
                spacing=GLOBAL_LAYOUT["line_spacing"],
            )
            y_cursor += quote_block_h + GLOBAL_LAYOUT["block_gap"]

        if expl_lines:
            expl_multiline = "\n".join(expl_lines)
            if cfg["expl_align"] == "LEFT":
                x_pos = margin_left
                align = "left"
            else:
                x_pos = W - margin_right
                align = "right"
            draw.multiline_text(
                (x_pos, y_cursor),
                expl_multiline,
                font=explanation_font,
                fill=cfg["explanation_color"],
                align=align,
                spacing=GLOBAL_LAYOUT["line_spacing"],
            )

        os.makedirs(os.path.dirname(output_path), exist_ok=True)
        img.save(output_path, quality=95)
        logger.info(f"Poster saved: {output_path}")
        return output_path
