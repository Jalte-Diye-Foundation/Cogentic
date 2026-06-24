import os
from PIL import Image, ImageDraw, ImageFont

# --- RECONFIGURED LAYOUT PARAMS (Tuned to fit the middle open pocket safely) ---
RENDER_CONFIG = {
    "background_path": "quality_education.jpg",
    
    # Typography Asset Configurations
    "quote_font_name": "Raleway-ExtraLight.ttf",
    "explanation_font_name": "Raleway-ExtraLight.ttf",

    "quote_font_size": 48,           # Slightly scaled down to prevent overflowing bounds
    "explanation_font_size": 26,
    "explanation_font_weight": 300,  # Legible light font weight

    # Custom Color Coding
    "quote_color": "#b91c1c",        # Primary Crimson Red Accent
    "explanation_color": "#b91c1c",  

    # Layout Boundaries (Expanded horizontal padding to protect background illustrations)
    "margin_left_ratio": 0.22,       # Pushes text completely clear of the graduation cap icon
    "margin_right_ratio": 0.22,      # Pushes text clear of the right hanging icons/logos

    # The absolute safe vertical bounding box for the entire middle text column
    "center_zone_top_ratio": 0.38,   # Sits safely below the "Quality Education" header square
    "center_zone_bottom_ratio": 0.74, # Ends safely above the bottom books and lightbulb logo

    "line_spacing": 12,              # Spacing between individual lines of text
    "block_gap": 35,                 # The exact tight gap separating the quote from explanation
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
    Assembles quotes cleanly inside the clear middle workspace.
    Quotes are left-aligned, explanations are right-aligned, and both are stacked tightly.
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

    # Wrap both blocks first to calculate total structural height
    quote_lines = wrap_text(quote_text, quote_font, draw, max_text_width)
    expl_lines = wrap_text(explanation_text, explanation_font, draw, max_text_width)

    quote_block_h = block_height(quote_lines, quote_font, draw, RENDER_CONFIG["line_spacing"])
    expl_block_h = block_height(expl_lines, explanation_font, draw, RENDER_CONFIG["line_spacing"])

    # Total combined vertical space required by the text blocks combined
    total_content_h = quote_block_h + RENDER_CONFIG["block_gap"] + expl_block_h

    # Define safe workspace dimensions
    zone_top = int(H * RENDER_CONFIG["center_zone_top_ratio"])
    zone_bottom = int(H * RENDER_CONFIG["center_zone_bottom_ratio"])
    zone_height = zone_bottom - zone_top

    # Center the entire combined text block inside the blank vertical middle area
    y_cursor = zone_top + max(0, (zone_height - total_content_h) // 2)

    # Phase 1: Draw Quote Lines (LEFT-ALIGNED)
    for line in quote_lines:
        draw.text((margin_left, y_cursor), line, font=quote_font, fill=RENDER_CONFIG["quote_color"])
        y_cursor += text_height(line, quote_font, draw) + RENDER_CONFIG["line_spacing"]

    # Remove the extra line spacing added on the final loop cycle, then add the tight block gap
    y_cursor = (y_cursor - RENDER_CONFIG["line_spacing"]) + RENDER_CONFIG["block_gap"]

    # Phase 2: Draw Explanation Lines (RIGHT-ALIGNED)
    for line in expl_lines:
        line_w = measure_text_width(line, explanation_font, draw)
        right_aligned_x = W - margin_right - line_w
        
        draw.text((right_aligned_x, y_cursor), line, font=explanation_font, fill=RENDER_CONFIG["explanation_color"])
        y_cursor += text_height(line, explanation_font, draw) + RENDER_CONFIG["line_spacing"]

    # Save Output
    img.save(output_filename, quality=95)
    print(f"📷 Corrected layout image rendered beautifully at: '{output_filename}'")
    return True
