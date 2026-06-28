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
        layout_name
    ):


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



        quote_font = load_font(
            self.fonts["quote_font_name"],
            70,
            self.project_root
        )


        explanation_font = load_font(
            self.fonts["explanation_font_name"],
            35,
            self.project_root
        )



        # light overlay only, to keep background airy like the reference design
        overlay = Image.new(
            "RGBA",
            image.size,
            (255, 255, 255, 60)
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
            850
        )


        y = 180
        image_center_x = image.width // 2


        for line in quote_lines:

            line_width = draw.textbbox((0, 0), line, font=quote_font)[2]
            x = image_center_x - (line_width // 2)

            draw.text(
                (x, y),
                line,
                font=quote_font,
                fill="#7a1f2b"
            )

            y += 90



        exp_lines = wrap_text(
            explanation,
            explanation_font,
            draw,
            850
        )


        y += 80


        for line in exp_lines:

            line_width = draw.textbbox((0, 0), line, font=explanation_font)[2]
            x = image_center_x - (line_width // 2)

            draw.text(
                (x, y),
                line,
                font=explanation_font,
                fill="#444444"
            )


            y += 50



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