import os
from PIL import Image, ImageDraw, ImageFont

# --- ENGINE CONFIGURATION PARAMS (Matching quality_education_text.jpg) ---
RENDER_CONFIG = {
    "background_path": "quality_education.jpg",
    
    # Typography Asset Configurations
    "quote_font_name": "georgia.ttf",
    "explanation_font_name": "Raleway-VariableFont_wght.ttf",

    "quote_font_size": 60,
    "explanation_font_size": 32,
    "explanation_font_weight": 300, # Clean, legible light font weight

    # Custom Color Coding
    "quote_color": "#b91c1c",        # Primary Crimson Red Accent
    "explanation_color": "#9f1239",  # Deep Rose Soft Secondary Hue

    # Layout Boundaries & Safe Zones (Horizontal padding)
    "margin_left_ratio": 0.15,
    "margin_right_ratio": 0.15,

    # Vertical distribution areas to avoid clipping background graphics
    "quote_top_ratio": 0.35,
    "quote_bottom_ratio": 0.55,
    
    "expl_top_ratio": 0.57,
    "expl_bottom_ratio": 0.82,

    "line_spacing": 14,
}

def load_font(font_name, size, weight=None):
    """Safely searches system paths and local folders to compile typography."""
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
                try: font.set_variation_by_axes([weight])
                except Exception: pass
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

# --- MAIN CALLABLE INTERFACE ---
def render_output_image(bg_image_path, quote_text, explanation_text, output_filename="daily_quote_output.jpg"):
    """
    Assembles generated quote text layouts safely onto the asset background layer.
    
    Arguments:
        bg_image_path (str): File path to your quality_education.jpg background template.
        quote_text (str): The quote string provided by your AI Core.
        explanation_text (str): The multi-sentence subtext explanation.
        output_filename (str): The targeted save path for the finalized JPG graphic.
    """
    if not os.path.exists(bg_image_path):
        print(f"🚨 Rendering Cancelled: Source base image asset '{bg_image_path}' was not found.")
        return False

    # Initialize Canvas Environment
    img = Image.open(bg_image_path).convert("RGB")
    draw = ImageDraw.Draw(img)
    W, H = img.size

    # Extract Typography Handles
    quote_font = load_font(RENDER_CONFIG["quote_font_name"], RENDER_CONFIG["quote_font_size"])
    explanation_font = load_font(RENDER_CONFIG["explanation_font_name"], RENDER_CONFIG["explanation_font_size"], RENDER_CONFIG["explanation_font_weight"])

    # Compute Structural Boundaries
    margin_left = int(W * RENDER_CONFIG["margin_left_ratio"])
    margin_right = int(W * RENDER_CONFIG["margin_right_ratio"])
    max_text_width = W - margin_left - margin_right

    # Phase 1: Wrap and draw the main Quote (Centered alignment)
    quote_lines = wrap_text(quote_text, quote_font, draw, max_text_width)
    q_top = int(H * RENDER_CONFIG["quote_top_ratio"])
    q_bottom = int(H * RENDER_CONFIG["quote_bottom_ratio"])
    q_zone_h = q_bottom - q_top
    q_height = block_height(quote_lines, quote_font, draw, RENDER_CONFIG["line_spacing"])
    
    y_cursor = q_top + max(0, (q_zone_h - q_height) // 2)
    for line in quote_lines:
        line_w = measure_text_width(line, quote_font, draw)
        draw.text(((W - line_w) // 2, y_cursor), line, font=quote_font, fill=RENDER_CONFIG["quote_color"])
        y_cursor += text_height(line, quote_font, draw) + RENDER_CONFIG["line_spacing"]

    # Phase 2: Wrap and draw the Explanation Block (Centered alignment)
    expl_lines = wrap_text(explanation_text, explanation_font, draw, max_text_width)
    e_top = int(H * RENDER_CONFIG["expl_top_ratio"])
    e_bottom = int(H * RENDER_CONFIG["expl_bottom_ratio"])
    e_zone_h = e_bottom - e_top
    e_height = block_height(expl_lines, explanation_font, draw, RENDER_CONFIG["line_spacing"])

    y_cursor = e_top + max(0, (e_zone_h - e_height) // 2)
    for line in expl_lines:
        line_w = measure_text_width(line, explanation_font, draw)
        draw.text(((W - line_w) // 2, y_cursor), line, font=explanation_font, fill=RENDER_CONFIG["explanation_color"])
        y_cursor += text_height(line, explanation_font, draw) + RENDER_CONFIG["line_spacing"]

    # Save Output
    img.save(output_filename, quality=95)
    print(f"📷 Composite image rendered nicely at: '{output_filename}'")
    return True
