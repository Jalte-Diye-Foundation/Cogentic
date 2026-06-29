import os
from PIL import Image, ImageDraw, ImageFont

# --- THEME REGISTRY (keyed by theme name) ---
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
        "quote_align": "CENTER",        # <-- CENTER
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
        "quote_align": "CENTER",        # <-- CENTER
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
        "center_zone_top_ratio": 0.20,
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
                except Exception:
                    pass
            return font
        except (IOError, OSError):
            continue
    print(f"⚠️ Warning: Could not find '{font_name}'. Using default font.")
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

def render_output_image(bg_image_path, quote_text, explanation_text, theme=None, output_filename="daily_quote_output.jpg"):
    """
    Renders the quote and explanation onto the background.
    If theme is provided, it is used as the key in THEME_REGISTRY.
    Otherwise, falls back to using the background filename (for backward compatibility).
    """
    # Determine which config to use
    cfg = None
    if theme and theme in THEME_REGISTRY:
        cfg = THEME_REGISTRY[theme]
        print(f"ℹ️ Using theme config for: {theme}")
    else:
        filename_key = os.path.basename(bg_image_path).strip()
        cfg = THEME_REGISTRY.get(filename_key, THEME_REGISTRY["jdf_general"])
        if filename_key not in THEME_REGISTRY:
            print(f"⚠️ Warning: '{filename_key}' not registered. Falling back to 'jdf_general'.")

    if not os.path.exists(bg_image_path):
        print(f"🚨 Rendering Cancelled: Source asset '{bg_image_path}' not found.")
        return False

    img = Image.open(bg_image_path).convert("RGB")
    draw = ImageDraw.Draw(img)
    W, H = img.size
    print(f"🖼️ Image size: {W}x{H}")  # debug

    quote_font = load_font(GLOBAL_LAYOUT["font_name"], GLOBAL_LAYOUT["quote_font_size"])
    explanation_font = load_font(
        GLOBAL_LAYOUT["font_name"],
        GLOBAL_LAYOUT["explanation_font_size"],
        GLOBAL_LAYOUT["explanation_font_weight"]
    )

    margin_left = int(W * cfg["margin_left_ratio"])
    margin_right = int(W * cfg["margin_right_ratio"])
    max_text_width = W - margin_left - margin_right
    print(f"📐 Margins: left={margin_left}, right={margin_right}")

    clean_quote = quote_text.strip().replace("\n", " ")
    clean_expl = explanation_text.strip().replace("\n", " ")

    quote_lines = wrap_text(clean_quote, quote_font, draw, max_text_width)
    expl_lines = wrap_text(clean_expl, explanation_font, draw, max_text_width)

    quote_block_h = block_height(quote_lines, quote_font, draw, GLOBAL_LAYOUT["line_spacing"])
    expl_block_h = block_height(expl_lines, explanation_font, draw, GLOBAL_LAYOUT["line_spacing"])
    total_content_h = quote_block_h + GLOBAL_LAYOUT["block_gap"] + expl_block_h

    zone_top = int(H * cfg["center_zone_top_ratio"])
    zone_bottom = int(H * cfg["center_zone_bottom_ratio"])
    zone_height = zone_bottom - zone_top
    print(f"📦 Zone: top={zone_top}, bottom={zone_bottom}")

    y_cursor = zone_top + max(0, (zone_height - total_content_h) // 2)

    # Draw quote (supports LEFT, CENTER, RIGHT)
    if quote_lines:
        for line in quote_lines:
            if cfg["quote_align"] == "LEFT":
                x_pos = margin_left
            elif cfg["quote_align"] == "CENTER":
                line_w = measure_text_width(line, quote_font, draw)
                x_pos = (W - line_w) // 2
            else:  # RIGHT
                line_w = measure_text_width(line, quote_font, draw)
                x_pos = W - margin_right - line_w
            draw.text((x_pos, y_cursor), line, font=quote_font, fill=cfg["quote_color"])
            y_cursor += text_height(line, quote_font, draw) + GLOBAL_LAYOUT["line_spacing"]
        y_cursor = (y_cursor - GLOBAL_LAYOUT["line_spacing"]) + GLOBAL_LAYOUT["block_gap"]

    # Draw explanation
    if expl_lines:
        for line in expl_lines:
            if cfg["expl_align"] == "LEFT":
                x_pos = margin_left
            else:  # RIGHT
                line_w = measure_text_width(line, explanation_font, draw)
                x_pos = W - margin_right - line_w
            draw.text((x_pos, y_cursor), line, font=explanation_font, fill=cfg["explanation_color"])
            y_cursor += text_height(line, explanation_font, draw) + GLOBAL_LAYOUT["line_spacing"]

    # Ensure the output directory exists
    os.makedirs(os.path.dirname(output_filename), exist_ok=True)
    img.save(output_filename, quality=95)
    print(f"📷 Composite rendered beautifully at: '{output_filename}'")
    return True
