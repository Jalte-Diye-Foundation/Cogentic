import os
from PIL import Image, ImageDraw, ImageFont

# --- ENGINE CONFIGURATION REGISTRY FOR ALL 5 THEMES ---
THEME_REGISTRY = {
    "climate_action.jpg": {
        "quote_color": "#15803d",        # Deep Forest Green Accent
        "explanation_color": "#166534",  # Muted Pine Green
        "quote_align": "RIGHT",
        "expl_align": "LEFT",
        "margin_left_ratio": 0.22,       # Protect left icons
        "margin_right_ratio": 0.22,      # Protect right hanging elements
        "center_zone_top_ratio": 0.31,   # Moved higher to optimize open space
        "center_zone_bottom_ratio": 0.69, # Safely avoids the bottom right globe/hand icon
        "quote_font_size": 48,
        "explanation_font_size": 26,
    },
    "jdf_general.jpg": {
        "quote_color": "#8c6239",        # Light Brown Theme Accent
        "explanation_color": "#a17850",  # Muted Light Brown Subtext
        "quote_align": "RIGHT",
        "expl_align": "LEFT",
        "margin_left_ratio": 0.20,
        "margin_right_ratio": 0.20,
        "center_zone_top_ratio": 0.30,   # Lifted higher up the canvas
        "center_zone_bottom_ratio": 0.70, # Keeps text away from bottom elements
        "quote_font_size": 48,
        "explanation_font_size": 26,
    },
    "reduced_inequalities.jpg": {
        "quote_color": "#dd1c4b",        # SDG 10 Deep Magenta Crimson
        "explanation_color": "#b9123c",  
        "quote_align": "RIGHT",
        "expl_align": "LEFT",
        "margin_left_ratio": 0.24,       # Generous padding to clear large SDG blocks
        "margin_right_ratio": 0.22,
        "center_zone_top_ratio": 0.40,   # Sits lower below the main header graphic
        "center_zone_bottom_ratio": 0.74,
        "quote_font_size": 46,           
        "explanation_font_size": 25,
    },
    "quality_education.jpg": {
        "quote_color": "#b91c1c",        # SDG 4 Cherry Red
        "explanation_color": "#b91c1c",  
        "quote_align": "LEFT",
        "expl_align": "RIGHT",
        "margin_left_ratio": 0.22,       # Protect left graduation cap icon
        "margin_right_ratio": 0.22,      # Protect right hanging icons/logos
        "center_zone_top_ratio": 0.38,   # Sits safely below header square
        "center_zone_bottom_ratio": 0.74, # Ends safely above bottom books/lightbulb
        "quote_font_size": 48,
        "explanation_font_size": 26,
    },
    "peace_justice.jpg": {
        "quote_color": "#00689d",        # SDG 16 Peace Blue
        "explanation_color": "#005580",  
        "quote_align": "LEFT",
        "expl_align": "RIGHT",
        "margin_left_ratio": 0.22,       
        "margin_right_ratio": 0.24,      # Avoid dove / structural scales on the right
        "center_zone_top_ratio": 0.33,   # Lifted slightly to center better with background
        "center_zone_bottom_ratio": 0.70, # Avoids spilling onto the balance scales
        "quote_font_size": 48,
        "explanation_font_size": 26,
    }
}

GLOBAL_LAYOUT = {
    "font_name": "Raleway-ExtraLight.ttf",
    "line_spacing": 12,
    "block_gap": 35,                 # Tight structural space between elements
}

def load_font(font_name, size):
    """Safely searches system paths and local folders to compile typography."""
    search_paths = [
        os.path.join(os.path.dirname(os.path.abspath(__file__)), font_name),
        os.path.join(os.path.dirname(os.path.abspath(__file__)), "fonts", font_name),
        os.path.join("C:/Windows/Fonts", font_name),
        font_name,
    ]
    for path in search_paths:
        try:
            return ImageFont.truetype(path, size)
        except (IOError, OSError):
            continue
    return ImageFont.load_default()

def measure_text_width(text, font, draw):
    if not text: return 0
    bb = draw.textbbox((0, 0), text, font=font)
    return bb[2] - bb[0]

def wrap_text(text, font, draw, max_width):
    """Wraps lines cleanly word-by-word so text boundaries never clip."""
    words = text.split()
    lines, current = [], []
    for word in words:
        test = " ".join(current + [word])
        if measure_text_width(test, font, draw) <= max_width:
            current.append(word)
        else:
            if current: lines.append(" ".join(current))
            current = [word]
    if current: lines.append(" ".join(current))
    return lines

def text_height(text, font, draw):
    bb = draw.textbbox((0, 0), text, font=font)
    return bb[3] - bb[1]

def block_height(lines, font, draw, line_spacing):
    if not lines: return 0
    return sum(text_height(line, font, draw) + line_spacing for line in lines) - line_spacing

# --- UNIFIED COMPOSITING INTERFACE ---
def render_output_image(bg_image_path, quote_text, explanation_text, output_filename="daily_quote_output.jpg"):
    """
    Renders quote and explanation assets dynamically onto 1 of 5 selected backgrounds.
    Calculates margins, colors, and text directions automatically by detecting filename keys.
    """
    # Sanitize and extract the exact asset filename from path strings
    filename_key = os.path.basename(bg_image_path).strip()
    
    if filename_key not in THEME_REGISTRY:
        print(f"⚠️ Warning: '{filename_key}' not directly registered. Defaulting to general layouts.")
        cfg = THEME_REGISTRY["jdf_general.jpg"]
    else:
        cfg = THEME_REGISTRY[filename_key]

    if not os.path.exists(bg_image_path):
        print(f"🚨 Rendering Cancelled: Source asset layout path '{bg_image_path}' was not found.")
        return False

    # Initialize Canvas Environment
    img = Image.open(bg_image_path).convert("RGB")
    draw = ImageDraw.Draw(img)
    W, H = img.size

    # Load Shared Project Typography
    quote_font = load_font(GLOBAL_LAYOUT["font_name"], cfg["quote_font_size"])
    explanation_font = load_font(GLOBAL_LAYOUT["font_name"], cfg["explanation_font_size"])

    # Compute Structural Boundaries
    margin_left = int(W * cfg["margin_left_ratio"])
    margin_right = int(W * cfg["margin_right_ratio"])
    max_text_width = W - margin_left - margin_right

    # Format Word Blocks & Height Properties
    quote_lines = wrap_text(quote_text, quote_font, draw, max_text_width)
    expl_lines = wrap_text(explanation_text, explanation_font, draw, max_text_width)

    quote_block_h = block_height(quote_lines, quote_font, draw, GLOBAL_LAYOUT["line_spacing"])
    expl_block_h = block_height(expl_lines, explanation_font, draw, GLOBAL_LAYOUT["line_spacing"])

    # Stack both elements cleanly together to get total structural footprint
    total_content_h = quote_block_h + GLOBAL_LAYOUT["block_gap"] + expl_block_h

    # Extract Safe Middle Pocket Ranges
    zone_top = int(H * cfg["center_zone_top_ratio"])
    zone_bottom = int(H * cfg["center_zone_bottom_ratio"])
    zone_height = zone_bottom - zone_top

    # Dynamically find the absolute center coordinate for the text stack
    y_cursor = zone_top + max(0, (zone_height - total_content_h) // 2)

    # Phase 1: Draw Quote Lines
    for line in quote_lines:
        if cfg["quote_align"] == "LEFT":
            x_pos = margin_left
        else: # RIGHT Align
            line_w = measure_text_width(line, quote_font, draw)
            x_pos = W - margin_right - line_w

        draw.text((x_pos, y_cursor), line, font=quote_font, fill=cfg["quote_color"])
        y_cursor += text_height(line, quote_font, draw) + GLOBAL_LAYOUT["line_spacing"]

    # Deduct structural trailing spacing loop bleed, then drop by the layout gap
    y_cursor = (y_cursor - GLOBAL_LAYOUT["line_spacing"]) + GLOBAL_LAYOUT["block_gap"]

    # Phase 2: Draw Explanation Lines
    for line in expl_lines:
        if cfg["expl_align"] == "LEFT":
            x_pos = margin_left
        else: # RIGHT Align
            line_w = measure_text_width(line, explanation_font, draw)
            x_pos = W - margin_right - line_w

        draw.text((x_pos, y_cursor), line, font=explanation_font, fill=cfg["explanation_color"])
        y_cursor += text_height(line, explanation_font, draw) + GLOBAL_LAYOUT["line_spacing"]

    # Save Composite Graphic File
    img.save(output_filename, quality=95)
    print(f"📷 [{filename_key}] Composite rendered cleanly at: '{output_filename}'")
    return True
