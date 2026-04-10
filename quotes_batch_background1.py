import os
import csv
from PIL import Image, ImageDraw, ImageFont

# --- CONFIG ---
CONFIG = {
    "background_path": "background1.png",
    "csv_path": "quotes.csv",

    # Georgia regular for quote, Raleway for explanation
    "quote_font_name": "georgia.ttf",
    "explanation_font_name": "Raleway-VariableFont_wght.ttf",

    "quote_font_size": 64,
    "explanation_font_size": 35,
    "explanation_font_weight": 100,
    "explanation_stroke_width": 1,
    "explanation_letter_spacing": 1,

    "quote_color": "#3a3a3a",
    "explanation_color": "#555555",

    # Left margin (fraction of W) — applies to both quote and explanation
    "margin_left_ratio": 0.10,
    # Right margin for quote (fraction of W)
    "margin_right_ratio": 0.10,

    # --- Quote zone (top clear area) ---
    # Vertically: 5% – 48% of image height
    "quote_top_ratio":    0.04,
    "quote_bottom_ratio": 0.48,

    # --- Explanation zone (bottom-left, clear of the logo) ---
    # Logo occupies roughly x: 55%–100%, y: 50%–92%
    # So explanation sits in x: margin – 58%, y: 52% – 90%
    "expl_right_ratio":   0.56,   # explanation text stays left of this x fraction
    "expl_top_ratio":     0.23,
    "expl_bottom_ratio":  0.90,

    "line_spacing": 15,
}


def load_font(font_name, size, weight=None):
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
                except (AttributeError, OSError, TypeError, ValueError):
                    pass
            return font
        except (IOError, OSError):
            continue
    print(f"ERROR: Could not load '{font_name}'. Text will be invisible/tiny. "
          f"Make sure the font is installed or placed in the same folder.")
    return ImageFont.load_default()


def measure_text_width(text, font, draw, stroke_width=0, letter_spacing=0):
    if not text:
        return 0
    if letter_spacing == 0:
        bb = draw.textbbox((0, 0), text, font=font, stroke_width=stroke_width)
        return bb[2] - bb[0]

    width = 0
    for index, char in enumerate(text):
        bb = draw.textbbox((0, 0), char, font=font, stroke_width=stroke_width)
        width += bb[2] - bb[0]
        if index < len(text) - 1:
            width += letter_spacing
    return width


def wrap_text(text, font, draw, max_width, stroke_width=0, letter_spacing=0):
    """Wrap text word-by-word so no line exceeds max_width pixels."""
    words = text.split()
    lines = []
    current = []

    for word in words:
        test = " ".join(current + [word])
        w = measure_text_width(
            test,
            font,
            draw,
            stroke_width=stroke_width,
            letter_spacing=letter_spacing,
        )
        if w <= max_width:
            current.append(word)
        else:
            if current:
                lines.append(" ".join(current))
            current = [word]

    if current:
        lines.append(" ".join(current))
    return lines


def text_height(text, font, draw, stroke_width=0):
    bb = draw.textbbox((0, 0), text, font=font, stroke_width=stroke_width)
    return bb[3] - bb[1]


def block_height(lines, font, draw, line_spacing, stroke_width=0):
    h = 0
    for line in lines:
        h += text_height(line, font, draw, stroke_width=stroke_width) + line_spacing
    return h


def draw_spaced_text(draw, position, text, font, fill, stroke_width=0, stroke_fill=None,
                     letter_spacing=0):
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
        bb = draw.textbbox((0, 0), char, font=font, stroke_width=stroke_width)
        x += (bb[2] - bb[0]) + letter_spacing


def generate_images():

    # --- CHECK BACKGROUND ---
    if not os.path.exists(CONFIG["background_path"]):
        print("Error: Background image not found")
        return

    # --- LOAD FONTS ---
    quote_font = load_font(CONFIG["quote_font_name"], CONFIG["quote_font_size"])
    explanation_font = load_font(
        CONFIG["explanation_font_name"],
        CONFIG["explanation_font_size"],
        CONFIG["explanation_font_weight"],
    )

    # --- READ CSV ---
    data = []
    try:
        with open(CONFIG["csv_path"], "r", encoding="utf-8") as f:
            reader = csv.reader(f)
            next(reader)  # skip header
            for row in reader:
                if len(row) >= 2:
                    quote = row[0].strip().replace('"', '')
                    explanation = row[1].strip().replace('"', '')
                    data.append((quote, explanation))
    except FileNotFoundError:
        print("Error: CSV file not found")
        return

    print(f"Processing {len(data)} quotes...")

    # --- PROCESS EACH ENTRY ---
    for i, (quote, explanation) in enumerate(data):

        img = Image.open(CONFIG["background_path"]).convert("RGB")
        draw = ImageDraw.Draw(img)

        W, H = img.size

        # Pixel coordinates for layout zones
        margin_left  = int(W * CONFIG["margin_left_ratio"])
        margin_right = int(W * CONFIG["margin_right_ratio"])

        # --- QUOTE ZONE (top area, full width) ---
        quote_max_w  = W - margin_left - margin_right
        quote_top    = int(H * CONFIG["quote_top_ratio"])
        quote_bottom = int(H * CONFIG["quote_bottom_ratio"])

        # --- EXPLANATION ZONE (bottom-left, beside logo) ---
        expl_max_w   = int(W * CONFIG["expl_right_ratio"]) - margin_left
        expl_top     = int(H * CONFIG["expl_top_ratio"])
        expl_bottom  = int(H * CONFIG["expl_bottom_ratio"])

        # Wrap text to each zone's width
        quote_lines = wrap_text(quote, quote_font, draw, quote_max_w)
        expl_lines  = wrap_text(
            explanation,
            explanation_font,
            draw,
            expl_max_w,
            stroke_width=CONFIG["explanation_stroke_width"],
            letter_spacing=CONFIG["explanation_letter_spacing"],
        )

        # --- DRAW QUOTE (left-aligned, vertically centred in top zone) ---
        q_height = block_height(quote_lines, quote_font, draw, CONFIG["line_spacing"])
        q_zone_h = quote_bottom - quote_top
        y = quote_top + max(0, (q_zone_h - q_height) // 2)

        for line in quote_lines:
            bb = draw.textbbox((0, 0), line, font=quote_font)
            lh = bb[3] - bb[1]
            draw.text((margin_left, y), line, font=quote_font, fill=CONFIG["quote_color"])
            y += lh + CONFIG["line_spacing"]

        # --- DRAW EXPLANATION (left-aligned, vertically centred in bottom-left zone) ---
        e_height = block_height(
            expl_lines,
            explanation_font,
            draw,
            CONFIG["line_spacing"],
            CONFIG["explanation_stroke_width"],
        )
        e_zone_h = expl_bottom - expl_top
        y = expl_top + max(0, (e_zone_h - e_height) // 2)

        for line in expl_lines:
            lh = text_height(
                line,
                explanation_font,
                draw,
                stroke_width=CONFIG["explanation_stroke_width"],
            )
            draw_spaced_text(
                draw,
                (margin_left, y),
                line,
                font=explanation_font,
                fill=CONFIG["explanation_color"],
                stroke_width=CONFIG["explanation_stroke_width"],
                stroke_fill=CONFIG["explanation_color"],
                letter_spacing=CONFIG["explanation_letter_spacing"],
            )
            y += lh + CONFIG["line_spacing"]

        # --- SAVE IMAGE ---
        output_name = f"quote_{i+1:03d}.jpg"
        img.save(output_name, quality=95)
        print(f"Generated: {output_name}")


if __name__ == "__main__":
    generate_images()