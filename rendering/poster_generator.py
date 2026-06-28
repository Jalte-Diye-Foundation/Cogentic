"""PIL-based poster rendering from quote, explanation, and background image."""

from __future__ import annotations

import logging
import os
from typing import Any

from PIL import Image, ImageDraw, ImageFont

logger = logging.getLogger(__name__)

def load_font(
    font_name: str,
    size: int,
    project_root: str,
    weight: int | None = None
):

    paths = [
        os.path.join(project_root, font_name),
        os.path.join(project_root, "fonts", font_name),
        os.path.join("C:/Windows/Fonts", font_name),
        font_name
    ]

    for path in paths:
        try:
            font = ImageFont.truetype(
                path,
                size
            )
            return font
        except:
            continue
    return ImageFont.load_default()

def wrap_text(
    text,
    font,
    draw,
    max_width
):
    words = text.split()
    lines = []
    current = ""

    for word in words:

        test = current + " " + word

        width = draw.textbbox(
            (0,0),
            test,
            font=font
        )[2]


        if width <= max_width:

            current = test.strip()

        else:

            lines.append(current)

            current = word


    if current:
        lines.append(current)


    return lines


THEME_COLORS = {
    "Climate & Environment": {
        "quote": "#6A8E5A",
        "explanation": "#7A8C73",
    },
    "Peace & Justice": {
        "quote": "#5C8DB8",
        "explanation": "#6D8FA8",
    },
    "Social Education": {
        "quote": "#D25A6E",
        "explanation": "#A86F7B",
    },
    "Women Empowerment": {
        "quote": "#dd1c4b",
        "explanation": "#b9123c",
    },
    "Health & Mindfulness": {
        "quote": "#8c6239",
        "explanation": "#a17850",
    },
    "Foundation Events": {
        "quote": "#8c6239",
        "explanation": "#a17850",
    },
}

START_Y = {
    "Climate & Environment": 240,
    "Peace & Justice": 260,
    "Social Education": 260,
    "Women Empowerment": 300,
    "Health & Mindfulness": 260,
    "Foundation Events": 260,
}

THEME_LAYOUT = {
    "Quality Education": {
        "quote_x": 280,
        "quote_y": 250,
        "quote_width": 450,
        "quote_color": "#E55B6A",
        "exp_color": "#D76A78",
    },

    "Women Empowerment": {
        "quote_x": 290,
        "quote_y": 260,
        "quote_width": 430,
        "quote_color": "#E95A7A",
        "exp_color": "#D96A88",
    },

    "Climate & Environment": {
        "quote_x": 280,
        "quote_y": 200,
        "quote_width": 470,
        "quote_color": "#5A9E6A",
        "exp_color": "#7FA67E",
    },

    "Peace & Justice": {
        "quote_x": 270,
        "quote_y": 200,
        "quote_width": 420,
        "quote_color": "#4A8FD8",
        "exp_color": "#5A9FD8",
    },

    "Health & Mindfulness": {
        "quote_x": 280,
        "quote_y": 240,
        "quote_width": 450,
        "quote_color": "#8C6239",
        "exp_color": "#A17850",
    },

    "Foundation Events": {
        "quote_x": 280,
        "quote_y": 240,
        "quote_width": 450,
        "quote_color": "#8C6239",
        "exp_color": "#A17850",
    },
}
class PosterGenerator:


    def __init__(
        self,
        config: dict[str,Any],
        project_root: str
    ):

        self.config = config

        self.project_root = project_root

        self.poster_config = config["poster"]

        self.fonts = self.poster_config["fonts"]



    def render(
        self,
        quote,
        explanation,
        background_path,
        output_path,
        layout_name,
        theme_name=None
    ):
        print("INSIDE POSTER_GENERATOR")
        print("Theme =", theme_name)
        print("Layout =", layout_name)


        if not os.path.exists(background_path):

            raise FileNotFoundError(
                f"Background missing: {background_path}"
            )


        logger.info(
            "Loading background image: %s",
            background_path
        )


        # LOAD REAL IMAGE
        image = Image.open(
            background_path
        ).convert("RGB")


        # FORCE POSTER SIZE
        image = image.resize(
            (1080,1080)
        )


        draw = ImageDraw.Draw(image)

        theme = THEME_LAYOUT.get(
            theme_name,
            THEME_LAYOUT["Quality Education"]
        )



        quote_font = load_font(
            self.fonts["quote_font_name"],
            30,
            self.project_root
        )


        explanation_font = load_font(
            self.fonts["explanation_font_name"],
            16,
            self.project_root
        )



        # light overlay only, to keep background airy like the reference design
        overlay = Image.new(
            "RGBA",
            image.size,
            (255, 255, 255, 20)
        )

        image = Image.alpha_composite(
            image.convert("RGBA"),
            overlay
        ).convert("RGB")


        draw = ImageDraw.Draw(image)



        quote_lines = wrap_text(
            quote,
            quote_font,
            draw,
            theme["quote_width"]
        )


        x = theme["quote_x"]
        y = theme["quote_y"]


        for line in quote_lines:

            x = theme["quote_x"]

            draw.text(
                (x, y),
                line,
                font=quote_font,
                fill=theme["quote_color"]
            )

            y += 45



        exp_lines = wrap_text(
            explanation,
            explanation_font,
            draw,
            theme["quote_width"]
        )


        y += 25


        for line in exp_lines:

            x = theme["quote_x"]

            draw.text(
                (x, y),
                line,
                font=explanation_font,
                fill=theme["exp_color"]
            )


            y += 24



        os.makedirs(
            os.path.dirname(output_path),
            exist_ok=True
        )


        image.save(
            output_path,
            quality=95
        )


        logger.info(
            "Poster saved: %s",
            output_path
        )


        return output_path