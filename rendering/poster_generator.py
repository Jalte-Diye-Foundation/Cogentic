"""PIL-based poster rendering from quote, explanation, and background image."""

from __future__ import annotations

import logging
import os
from typing import Any

from PIL import Image, ImageDraw, ImageFont

logger = logging.getLogger(__name__)


def load_font(font_name: str, size: int, project_root: str, weight: int | None = None) -> ImageFont.FreeTypeFont | ImageFont.ImageFont:
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
                except (AttributeError, OSError, TypeError, ValueError):
                    pass
            return font
        except (OSError, IOError):
            continue
    logger.warning("Could not load font '%s'; using default font.", font_name)
    return ImageFont.load_default()


def measure_text_width(
    text: str,
    font: ImageFont.FreeTypeFont | ImageFont.ImageFont,
    draw: ImageDraw.ImageDraw,
    stroke_width: int = 0,
    letter_spacing: int = 0,
) -> int:
    if not text:
        return 0
    if letter_spacing == 0:
        bbox = draw.textbbox((0, 0), text, font=font, stroke_width=stroke_width)
        return bbox[2] - bbox[0]

    width = 0
    for index, char in enumerate(text):
        bbox = draw.textbbox((0, 0), char, font=font, stroke_width=stroke_width)
        width += bbox[2] - bbox[0]
        if index < len(text) - 1:
            width += letter_spacing
    return width


def wrap_text(
    text: str,
    font: ImageFont.FreeTypeFont | ImageFont.ImageFont,
    draw: ImageDraw.ImageDraw,
    max_width: int,
    stroke_width: int = 0,
    letter_spacing: int = 0,
) -> list[str]:
    words = text.split()
    lines: list[str] = []
    current: list[str] = []

    for word in words:
        test = " ".join(current + [word])
        width = measure_text_width(
            test, font, draw, stroke_width=stroke_width, letter_spacing=letter_spacing
        )
        if width <= max_width:
            current.append(word)
        else:
            if current:
                lines.append(" ".join(current))
            current = [word]

    if current:
        lines.append(" ".join(current))
    return lines


def text_height(
    text: str,
    font: ImageFont.FreeTypeFont | ImageFont.ImageFont,
    draw: ImageDraw.ImageDraw,
    stroke_width: int = 0,
) -> int:
    bbox = draw.textbbox((0, 0), text, font=font, stroke_width=stroke_width)
    return bbox[3] - bbox[1]


def block_height(
    lines: list[str],
    font: ImageFont.FreeTypeFont | ImageFont.ImageFont,
    draw: ImageDraw.ImageDraw,
    line_spacing: int,
    stroke_width: int = 0,
) -> int:
    height = 0
    for line in lines:
        height += text_height(line, font, draw, stroke_width=stroke_width) + line_spacing
    return height


def draw_spaced_text(
    draw: ImageDraw.ImageDraw,
    position: tuple[int, int],
    text: str,
    font: ImageFont.FreeTypeFont | ImageFont.ImageFont,
    fill: str,
    stroke_width: int = 0,
    stroke_fill: str | None = None,
    letter_spacing: int = 0,
) -> None:
    if letter_spacing == 0:
        draw.text(
            position,
            text,
            font=font,
            fill=fill,
            stroke_width=stroke_width,
            stroke_fill=stroke_fill,
        )
        return

    x, y = position
    for char in text:
        draw.text(
            (x, y),
            char,
            font=font,
            fill=fill,
            stroke_width=stroke_width,
            stroke_fill=stroke_fill,
        )
        bbox = draw.textbbox((0, 0), char, font=font, stroke_width=stroke_width)
        x += (bbox[2] - bbox[0]) + letter_spacing


class PosterGenerator:
    """Renders a single poster image with quote and explanation text overlays."""

    def __init__(self, config: dict[str, Any], project_root: str) -> None:
        self._config = config
        self._project_root = project_root
        self._poster_config = config["poster"]
        self._fonts = self._poster_config["fonts"]

    def render(
        self,
        quote: str,
        explanation: str,
        background_path: str,
        output_path: str,
        layout_name: str,
    ) -> str:
        """Render and save a poster; returns the output file path."""
        if not os.path.exists(background_path):
            raise FileNotFoundError(f"Background image not found: {background_path}")

        layout = self._poster_config["layouts"].get(layout_name)
        if layout is None:
            raise ValueError(f"Unknown poster layout: {layout_name}")

        os.makedirs(os.path.dirname(output_path) or ".", exist_ok=True)

        quote_font = load_font(
            self._fonts["quote_font_name"],
            layout["quote_font_size"],
            self._project_root,
        )
        explanation_font = load_font(
            self._fonts["explanation_font_name"],
            layout["explanation_font_size"],
            self._project_root,
            layout.get("explanation_font_weight"),
        )

        image = Image.open(background_path).convert("RGB")
        draw = ImageDraw.Draw(image)
        width, height = image.size

        margin_left = int(width * layout["margin_left_ratio"])
        margin_right = int(width * layout["margin_right_ratio"])
        quote_max_width = width - margin_left - margin_right
        quote_top = int(height * layout["quote_top_ratio"])
        quote_bottom = int(height * layout["quote_bottom_ratio"])

        quote_lines = wrap_text(quote, quote_font, draw, quote_max_width)
        quote_block_height = block_height(
            quote_lines, quote_font, draw, layout["line_spacing"]
        )
        quote_zone_height = quote_bottom - quote_top
        y = quote_top + max(0, (quote_zone_height - quote_block_height) // 2)

        for line in quote_lines:
            bbox = draw.textbbox((0, 0), line, font=quote_font)
            line_height = bbox[3] - bbox[1]
            draw.text((margin_left, y), line, font=quote_font, fill=layout["quote_color"])
            y += line_height + layout["line_spacing"]

        if layout_name == "right_explanation":
            self._draw_right_explanation(
                draw, explanation, explanation_font, layout, width, height, margin_left
            )
        else:
            self._draw_left_explanation(
                draw, explanation, explanation_font, layout, width, height, margin_left
            )

        quality = self._poster_config.get("quality", 95)
        image.save(output_path, quality=quality)
        logger.info("Poster saved to %s", output_path)
        return output_path

    def _draw_left_explanation(
        self,
        draw: ImageDraw.ImageDraw,
        explanation: str,
        explanation_font: ImageFont.FreeTypeFont | ImageFont.ImageFont,
        layout: dict[str, Any],
        width: int,
        height: int,
        margin_left: int,
    ) -> None:
        expl_max_width = int(width * layout["expl_right_ratio"]) - margin_left
        expl_top = int(height * layout["expl_top_ratio"])
        expl_bottom = int(height * layout["expl_bottom_ratio"])
        stroke_width = layout["explanation_stroke_width"]
        letter_spacing = layout["explanation_letter_spacing"]

        expl_lines = wrap_text(
            explanation,
            explanation_font,
            draw,
            expl_max_width,
            stroke_width=stroke_width,
            letter_spacing=letter_spacing,
        )
        expl_block_height = block_height(
            expl_lines,
            explanation_font,
            draw,
            layout["line_spacing"],
            stroke_width,
        )
        expl_zone_height = expl_bottom - expl_top
        y = expl_top + max(0, (expl_zone_height - expl_block_height) // 2)

        for line in expl_lines:
            line_height = text_height(line, explanation_font, draw, stroke_width=stroke_width)
            draw_spaced_text(
                draw,
                (margin_left, y),
                line,
                font=explanation_font,
                fill=layout["explanation_color"],
                stroke_width=stroke_width,
                stroke_fill=layout["explanation_color"],
                letter_spacing=letter_spacing,
            )
            y += line_height + layout["line_spacing"]

    def _draw_right_explanation(
        self,
        draw: ImageDraw.ImageDraw,
        explanation: str,
        explanation_font: ImageFont.FreeTypeFont | ImageFont.ImageFont,
        layout: dict[str, Any],
        width: int,
        height: int,
        margin_left: int,
    ) -> None:
        expl_left = int(width * layout["expl_left_ratio"])
        expl_right = width - margin_left
        expl_max_width = max(1, expl_right - expl_left)
        expl_top = int(height * layout["expl_top_ratio"])
        expl_bottom = int(height * layout["expl_bottom_ratio"])
        stroke_width = layout["explanation_stroke_width"]
        letter_spacing = layout["explanation_letter_spacing"]

        expl_lines = wrap_text(
            explanation,
            explanation_font,
            draw,
            expl_max_width,
            stroke_width=stroke_width,
            letter_spacing=letter_spacing,
        )
        expl_block_height = block_height(
            expl_lines,
            explanation_font,
            draw,
            layout["line_spacing"],
            stroke_width,
        )
        expl_zone_height = expl_bottom - expl_top
        y = expl_top + max(0, (expl_zone_height - expl_block_height) // 2)

        for line in expl_lines:
            line_height = text_height(line, explanation_font, draw, stroke_width=stroke_width)
            line_width = measure_text_width(
                line,
                explanation_font,
                draw,
                stroke_width=stroke_width,
                letter_spacing=letter_spacing,
            )
            line_x = max(expl_left, expl_right - line_width)
            draw_spaced_text(
                draw,
                (line_x, y),
                line,
                font=explanation_font,
                fill=layout["explanation_color"],
                stroke_width=stroke_width,
                stroke_fill=layout["explanation_color"],
                letter_spacing=letter_spacing,
            )
            y += line_height + layout["line_spacing"]
