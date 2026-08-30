"""
Poster rendering engine for Cogentic AI (Jalte Diye Foundation).
Provides dynamic font scaling, boundary validation, and responsive typography
to ensure text strictly fits within the safe zone of any background image.
"""

from __future__ import annotations

import logging
import os
from PIL import Image, ImageDraw, ImageFont

logger = logging.getLogger(__name__)

# --- THEME REGISTRY (colors, alignments, and safe zones) ---
THEME_REGISTRY = {
    "Climate & Environment": {
        "quote_color": "#15803d",
        "explanation_color": "#166534",
        "quote_align": "LEFT",
        "expl_align": "LEFT",
        "margin_left_ratio": 0.15,
        "margin_right_ratio": 0.15,
        "center_zone_top_ratio": 0.22,
        "center_zone_bottom_ratio": 0.70,
    },
    "Health & Mindfulness": {
        "quote_color": "#8c6239",
        "explanation_color": "#6e4b2a",
        "quote_align": "LEFT",
        "expl_align": "LEFT",
        "margin_left_ratio": 0.15,
        "margin_right_ratio": 0.15,
        "center_zone_top_ratio": 0.22,
        "center_zone_bottom_ratio": 0.70,
    },
    "Women Empowerment": {
        "quote_color": "#dd1c4b",
        "explanation_color": "#9f1239",
        "quote_align": "LEFT",
        "expl_align": "LEFT",
        "margin_left_ratio": 0.15,
        "margin_right_ratio": 0.15,
        "center_zone_top_ratio": 0.22,
        "center_zone_bottom_ratio": 0.70,
    },
    "Quality Education": {
        "quote_color": "#b91c1c",
        "explanation_color": "#7f1d1d",
        "quote_align": "LEFT",
        "expl_align": "LEFT",
        "margin_left_ratio": 0.15,
        "margin_right_ratio": 0.15,
        "center_zone_top_ratio": 0.22,
        "center_zone_bottom_ratio": 0.70,
    },
    "Social Education": {
        "quote_color": "#b91c1c",
        "explanation_color": "#7f1d1d",
        "quote_align": "LEFT",
        "expl_align": "LEFT",
        "margin_left_ratio": 0.15,
        "margin_right_ratio": 0.15,
        "center_zone_top_ratio": 0.22,
        "center_zone_bottom_ratio": 0.70,
    },
    "Peace & Justice": {
        "quote_color": "#00689d",
        "explanation_color": "#004366",
        "quote_align": "LEFT",
        "expl_align": "LEFT",
        "margin_left_ratio": 0.15,
        "margin_right_ratio": 0.15,
        "center_zone_top_ratio": 0.22,
        "center_zone_bottom_ratio": 0.70,
    },
    "Foundation Events": {
        "quote_color": "#8c6239",
        "explanation_color": "#6e4b2a",
        "quote_align": "LEFT",
        "expl_align": "LEFT",
        "margin_left_ratio": 0.15,
        "margin_right_ratio": 0.15,
        "center_zone_top_ratio": 0.22,
        "center_zone_bottom_ratio": 0.70,
    },
    "jdf_general": {
        "quote_color": "#3a3a3a",
        "explanation_color": "#555555",
        "quote_align": "LEFT",
        "expl_align": "LEFT",
        "margin_left_ratio": 0.15,
        "margin_right_ratio": 0.15,
        "center_zone_top_ratio": 0.22,
        "center_zone_bottom_ratio": 0.70,
    },
}

GLOBAL_LAYOUT = {
    "font_name": "Raleway-VariableFont_wght.ttf",
    "fallback_font_name": "Raleway-ExtraLight.ttf",
    "quote_weight": 600,
    "explanation_weight": 400,
}


def load_font(font_name: str, size: int, weight: int | None = None) -> ImageFont.FreeTypeFont | ImageFont.ImageFont:
    """Safely load a TrueType font with weight variations if supported."""
    search_paths = [
        os.path.join(os.path.dirname(os.path.abspath(__file__)), font_name),
        os.path.join(os.path.dirname(os.path.abspath(__file__)), "fonts", font_name),
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

    # Fallback to secondary font if primary fails
    fallback_name = GLOBAL_LAYOUT.get("fallback_font_name", "arial.ttf")
    if font_name != fallback_name:
        return load_font(fallback_name, size, weight)

    logger.warning("Could not find font '%s'. Using default PIL font.", font_name)
    return ImageFont.load_default()


def measure_text_width(text: str, font: ImageFont.FreeTypeFont | ImageFont.ImageFont, draw: ImageDraw.ImageDraw) -> int:
    """Return the pixel width of a single text line."""
    if not text:
        return 0
    bb = draw.textbbox((0, 0), text, font=font)
    return bb[2] - bb[0]


def measure_text_height(text: str, font: ImageFont.FreeTypeFont | ImageFont.ImageFont, draw: ImageDraw.ImageDraw) -> int:
    """Return the pixel height of a single text line."""
    if not text:
        return 0
    bb = draw.textbbox((0, 0), text, font=font)
    return bb[3] - bb[1]


def wrap_text(
    text: str,
    font: ImageFont.FreeTypeFont | ImageFont.ImageFont,
    draw: ImageDraw.ImageDraw,
    max_width: int,
) -> list[str]:
    """
    Wrap text word-by-word into lines that strictly fit within max_width.
    Respects explicit newline breaks while wrapping individual paragraphs.
    """
    if not text:
        return []

    paragraphs = text.strip().split("\n")
    all_lines: list[str] = []

    for paragraph in paragraphs:
        words = paragraph.strip().split()
        if not words:
            continue

        current: list[str] = []
        for word in words:
            test_line = " ".join(current + [word])
            if measure_text_width(test_line, font, draw) <= max_width:
                current.append(word)
            else:
                if current:
                    all_lines.append(" ".join(current))
                current = [word]
        if current:
            all_lines.append(" ".join(current))

    return all_lines


def block_height(
    lines: list[str],
    font: ImageFont.FreeTypeFont | ImageFont.ImageFont,
    draw: ImageDraw.ImageDraw,
    line_spacing: int,
) -> int:
    """Calculate the total vertical pixel height of a multi-line text block."""
    if not lines:
        return 0
    return sum(measure_text_height(line, font, draw) + line_spacing for line in lines) - line_spacing


def calculate_adaptive_layout(
    quote_text: str,
    explanation_text: str,
    W: int,
    H: int,
    cfg: dict,
    draw: ImageDraw.ImageDraw,
    font_name: str,
) -> tuple[ImageFont.FreeTypeFont, ImageFont.FreeTypeFont, list[str], list[str], int, int, int, int, int]:
    """
    Dynamically scale typography and spacing so the complete composite
    (quote + block gap + explanation) fits perfectly inside the safe zone.

    Returns:
        (quote_font, explanation_font, quote_lines, expl_lines,
         line_spacing, block_gap, total_content_h, zone_top, zone_bottom)
    """
    margin_left = int(W * cfg["margin_left_ratio"])
    margin_right = int(W * cfg["margin_right_ratio"])
    max_text_width = max(100, W - margin_left - margin_right)

    zone_top = int(H * cfg["center_zone_top_ratio"])
    zone_bottom = int(H * cfg["center_zone_bottom_ratio"])
    zone_height = max(100, zone_bottom - zone_top)

    # Initial target sizes proportional to canvas height
    target_quote_size = max(44, int(H * 0.046))
    target_expl_size = max(24, int(H * 0.025))

    min_quote_size = max(26, int(H * 0.026))
    min_expl_size = max(16, int(H * 0.016))

    current_quote_size = target_quote_size
    current_expl_size = target_expl_size

    # Fit-to-bounds iteration loop
    while current_quote_size >= min_quote_size:
        line_spacing = max(6, int(current_expl_size * 0.40))
        block_gap = max(18, int(current_quote_size * 0.65))

        q_font = load_font(font_name, current_quote_size, GLOBAL_LAYOUT["quote_weight"])
        e_font = load_font(font_name, current_expl_size, GLOBAL_LAYOUT["explanation_weight"])

        q_lines = wrap_text(quote_text, q_font, draw, max_text_width)
        e_lines = wrap_text(explanation_text, e_font, draw, max_text_width)

        q_h = block_height(q_lines, q_font, draw, line_spacing)
        e_h = block_height(e_lines, e_font, draw, line_spacing)
        total_h = q_h + (block_gap if (q_lines and e_lines) else 0) + e_h

        if total_h <= zone_height:
            return q_font, e_font, q_lines, e_lines, line_spacing, block_gap, total_h, zone_top, zone_bottom

        # Decrement font sizes proportionally
        current_quote_size -= 2
        current_expl_size = max(min_expl_size, int(current_quote_size * 0.55))

    # If still tight at minimum font size, compress line spacing and block gap
    q_font = load_font(font_name, min_quote_size, GLOBAL_LAYOUT["quote_weight"])
    e_font = load_font(font_name, min_expl_size, GLOBAL_LAYOUT["explanation_weight"])
    q_lines = wrap_text(quote_text, q_font, draw, max_text_width)
    e_lines = wrap_text(explanation_text, e_font, draw, max_text_width)

    line_spacing = max(4, int(min_expl_size * 0.25))
    block_gap = max(12, int(min_quote_size * 0.35))
    q_h = block_height(q_lines, q_font, draw, line_spacing)
    e_h = block_height(e_lines, e_font, draw, line_spacing)
    total_h = q_h + (block_gap if (q_lines and e_lines) else 0) + e_h

    return q_font, e_font, q_lines, e_lines, line_spacing, block_gap, total_h, zone_top, zone_bottom


def render_output_image(
    bg_image_path: str,
    quote_text: str,
    explanation_text: str,
    theme: str | None = None,
    output_filename: str = "daily_quote_output.jpg",
) -> bool:
    """
    Renders quote and explanation typography onto the specified background image.
    Uses dynamic typography scaling and safe zone alignment.
    """
    if not os.path.exists(bg_image_path):
        logger.error("Source background asset not found: '%s'", bg_image_path)
        return False

    # Select theme config
    if theme and theme in THEME_REGISTRY:
        cfg = THEME_REGISTRY[theme]
    else:
        filename_key = os.path.basename(bg_image_path).strip()
        cfg = THEME_REGISTRY.get(filename_key, THEME_REGISTRY["jdf_general"])

    try:
        img = Image.open(bg_image_path).convert("RGB")
        draw = ImageDraw.Draw(img)
        W, H = img.size

        font_name = GLOBAL_LAYOUT["font_name"]

        (
            quote_font,
            explanation_font,
            quote_lines,
            expl_lines,
            line_spacing,
            block_gap,
            total_content_h,
            zone_top,
            zone_bottom,
        ) = calculate_adaptive_layout(
            quote_text=quote_text,
            explanation_text=explanation_text,
            W=W,
            H=H,
            cfg=cfg,
            draw=draw,
            font_name=font_name,
        )

        margin_left = int(W * cfg["margin_left_ratio"])
        margin_right = int(W * cfg["margin_right_ratio"])
        zone_height = zone_bottom - zone_top

        # Center the total block vertically in the designated safe zone
        y_cursor = zone_top + max(0, (zone_height - total_content_h) // 2)

        # Draw quote lines
        quote_align = cfg.get("quote_align", "LEFT")
        for line in quote_lines:
            line_w = measure_text_width(line, quote_font, draw)
            if quote_align == "CENTER":
                x_pos = (W - line_w) // 2
            elif quote_align == "RIGHT":
                x_pos = W - margin_right - line_w
            else:  # LEFT
                x_pos = margin_left

            draw.text((x_pos, y_cursor), line, font=quote_font, fill=cfg["quote_color"])
            y_cursor += measure_text_height(line, quote_font, draw) + line_spacing

        if quote_lines and expl_lines:
            y_cursor = (y_cursor - line_spacing) + block_gap

        # Draw explanation lines
        expl_align = cfg.get("expl_align", "LEFT")
        for line in expl_lines:
            line_w = measure_text_width(line, explanation_font, draw)
            if expl_align == "CENTER":
                x_pos = (W - line_w) // 2
            elif expl_align == "RIGHT":
                x_pos = W - margin_right - line_w
            else:  # LEFT
                x_pos = margin_left

            draw.text((x_pos, y_cursor), line, font=explanation_font, fill=cfg["explanation_color"])
            y_cursor += measure_text_height(line, explanation_font, draw) + line_spacing

        # Save output composite
        os.makedirs(os.path.dirname(output_filename) or ".", exist_ok=True)
        img.save(output_filename, format="JPEG", quality=95)
        logger.info("Poster rendered successfully: '%s'", output_filename)
        return True

    except Exception as exc:
        logger.exception("Poster rendering failed: %s", exc)
        return False
