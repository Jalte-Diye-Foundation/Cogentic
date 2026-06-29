import os
from PIL import Image, ImageDraw, ImageFont
from test import main

# --- ENGINE CONFIGURATION REGISTRY FOR ALL 5 THEMES ---
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
        "quote_align": "RIGHT",
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
    "quote_font_size": 36,
    "explanation_font_size": 22,
    "explanation_font_weight": 300,
    "line_spacing": 16,
    "block_gap": 45,
}

def load_font(font_name, size, weight=None):
    """ Safely searches system paths and local folders to compile typography with correct weight axes."""
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
    print(f"⚠️ Warning: Could not find '{font_name}'. Falling back to default canvas font.")
    return ImageFont.load_default()

def measure_text_width(text, font, draw):
    if not text: return 0
    bb = draw.textbbox((0, 0), text, font=font)
    return bb[2] - bb[0]

def wrap_text(text, font, draw, max_width):
    """ Wraps lines cleanly word-by-word so text boundaries never clip."""
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
def render_output_image(bg_image_path, quote_text, explanation_text, domain, output_filename="daily_quote_output.jpg"):
    """
    Renders quotes and explanations cleanly onto any of the 5 background options.
    Uses custom per-theme geometry configs to tailor positioning and alignments perfectly.
    """
    filename_key = os.path.basename(bg_image_path).strip()
    
    if domain not in THEME_REGISTRY:
        print(f"⚠️ Warning: '{domain}' not directly registered. Defaulting to general layouts.")
        cfg = THEME_REGISTRY["jdf_general"]
    else:
        cfg = THEME_REGISTRY[domain]

    if not os.path.exists(bg_image_path):
        print(f"🚨 Rendering Cancelled: Source asset layout path '{bg_image_path}' was not found.")
        return False

    # Initialize Canvas Environment
    img = Image.open(bg_image_path).convert("RGB")
    draw = ImageDraw.Draw(img)
    W, H = img.size

    # Load shared typography with exact explicit weights matching your base code
    quote_font = load_font(GLOBAL_LAYOUT["font_name"], GLOBAL_LAYOUT["quote_font_size"])
    explanation_font = load_font(
        GLOBAL_LAYOUT["font_name"], 
        GLOBAL_LAYOUT["explanation_font_size"], 
        GLOBAL_LAYOUT["explanation_font_weight"]
    )

    # Compute Structural Boundaries
    margin_left = int(W * cfg["margin_left_ratio"])
    margin_right = int(W * cfg["margin_right_ratio"])
    max_text_width = W - margin_left - margin_right

    # Clean input raw strings to eliminate layout-breaking boundary anomalies from APIs
    clean_quote = quote_text.strip().replace("\n", " ")
    clean_expl = explanation_text.strip().replace("\n", " ")

    # Format Word Blocks & Height Properties
    quote_lines = wrap_text(clean_quote, quote_font, draw, max_text_width)
    expl_lines = wrap_text(clean_expl, explanation_font, draw, max_text_width)

    quote_block_h = block_height(quote_lines, quote_font, draw, GLOBAL_LAYOUT["line_spacing"])
    expl_block_h = block_height(expl_lines, explanation_font, draw, GLOBAL_LAYOUT["line_spacing"])

    # Combine metrics for clean structural vertical stack handling
    total_content_h = quote_block_h + GLOBAL_LAYOUT["block_gap"] + expl_block_h

    # Extract Middle Pocket Bounds (Now customized individually per background theme)
    zone_top = int(H * cfg["center_zone_top_ratio"])
    zone_bottom = int(H * cfg["center_zone_bottom_ratio"])
    zone_height = zone_bottom - zone_top

    # Calculate absolute centering coordinate position inside this theme's unique pocket
    y_cursor = zone_top + max(0, (zone_height - total_content_h) // 2)

    # Phase 1: Draw Quote Lines
    for line in quote_lines:
        cleaned_line = line.strip()  # Strip every individual wrapped iteration string
        if not cleaned_line: continue
        
        if cfg["quote_align"] == "LEFT":
            x_pos = margin_left
        else: # RIGHT Align
            line_w = measure_text_width(cleaned_line, quote_font, draw)
            x_pos = W - margin_right - line_w

        draw.text((x_pos, y_cursor), cleaned_line, font=quote_font, fill=cfg["quote_color"])
        # Increment using a clean line baseline step to ensure uniform line spacing
        y_cursor += text_height(cleaned_line, quote_font, draw) + GLOBAL_LAYOUT["line_spacing"]

    # Clear loop bleeding margin, then apply fixed separation spacing block gap
    y_cursor = (y_cursor - GLOBAL_LAYOUT["line_spacing"]) + GLOBAL_LAYOUT["block_gap"]

    # Phase 2: Draw Explanation Lines
    for line in expl_lines:
        cleaned_line = line.strip()  # Strip iteration step to preserve flush alignments
        if not cleaned_line: continue
        
        if cfg["expl_align"] == "LEFT":
            x_pos = margin_left
        else: # RIGHT Align
            line_w = measure_text_width(cleaned_line, explanation_font, draw)
            x_pos = W - margin_right - line_w

        draw.text((x_pos, y_cursor), cleaned_line, font=explanation_font, fill=cfg["explanation_color"])
        y_cursor += text_height(cleaned_line, explanation_font, draw) + GLOBAL_LAYOUT["line_spacing"]

    # Save Output Asset
    img.save(output_filename, quality=95)
    print(f"📷 [{filename_key}] Composite rendered beautifully at: '{output_filename}'")
    return True

if __name__ == "__main__":
    # Get generated content from test.py
    data = main()

    domain = data["domain"]
    quote = data["quote"]
    explanation = data["explanation"]

    # Map domains to background images
    DOMAIN_BACKGROUND_MAP = {
        "Peace & Justice": "themes/peace/bg1.png",
        "Health & Mindfulness": "themes/health/bg1.png",
        "Social Education": "themes/education/bg1.png",
        "Climate & Environment": "themes/climate/bg1.png",
        "Foundation Events": "themes/events/bg1.png",
        "Women Empowerment": "themes/women/women.png",
    }
    
    bg_image = DOMAIN_BACKGROUND_MAP.get(
        domain,
        "jdf_general.jpg"
    )

    print(f"Domain      : {domain}")
    print(f"Quote       : {quote}")
    print(f"Explanation : {explanation}")
    print(f"Background  : {bg_image}")

    render_output_image(
        bg_image_path=bg_image,
        quote_text=quote,
        explanation_text=explanation,
        domain=domain,
        output_filename="daily_quote_output.jpg"
    )
