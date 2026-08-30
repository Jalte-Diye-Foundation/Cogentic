"""
Run this to generate test images for every theme so you can check text alignment.
Output goes to: output/alignment_test/

Usage:
    python test_alignment.py
    python test_alignment.py --debug    # draws red/blue zone+margin guides
"""

import os, sys, glob, argparse
from image_gen import render_output_image, THEME_REGISTRY

SAMPLE_QUOTE = "Education is the most powerful weapon which you can use to change the world."
SAMPLE_EXPL  = "When people are educated they gain the knowledge and skills needed to improve their lives and the lives of others around them."

THEME_BG_MAP = {
    "Climate & Environment": "themes/climate/bg1.png",
    "Health & Mindfulness":  "themes/health/bg1.png",
    "Women Empowerment":     "themes/women/bg1.png",
    "Social Education":      "themes/education/bg1.png",
    "Quality Education":     "themes/education/bg1.png",
    "Peace & Justice":       "themes/peace/bg1.png",
    "Foundation Events":     "themes/events/bg1.png",
    "jdf_general":           "themes/health/bg1.png",
}

def find_bg(theme):
    """Return the mapped bg path, or search for any .png/.jpg in the theme folder."""
    path = THEME_BG_MAP.get(theme)
    if path and os.path.exists(path):
        return path
    # fallback: scan all theme folders for first image
    for folder in glob.glob("themes/*/"):
        for ext in ("*.png", "*.jpg", "*.jpeg"):
            imgs = glob.glob(os.path.join(folder, ext))
            if imgs:
                return imgs[0]
    return None

def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--debug", action="store_true", help="Draw zone/margin guide lines")
    parser.add_argument("--quote", default=SAMPLE_QUOTE, help="Custom quote text")
    parser.add_argument("--expl", default=SAMPLE_EXPL, help="Custom explanation text")
    parser.add_argument("--theme", default=None, help="Test a single theme only (e.g. 'Peace & Justice')")
    args = parser.parse_args()

    if args.debug:
        os.environ["DEBUG_LAYOUT"] = "1"
    else:
        os.environ.pop("DEBUG_LAYOUT", None)

    out_dir = os.path.join("output", "alignment_test")
    os.makedirs(out_dir, exist_ok=True)

    print(f"\n{'='*55}")
    print(f"  Alignment Test — {'DEBUG mode ON' if args.debug else 'normal mode'}")
    print(f"  Output folder: {out_dir}")
    print(f"{'='*55}\n")

    themes_to_test = [args.theme] if args.theme else list(THEME_REGISTRY.keys())

    for theme in themes_to_test:
        bg = find_bg(theme)
        if not bg:
            print(f"⚠️  Skipping '{theme}' — no background image found")
            continue
        safe_name = theme.replace(" ", "_").replace("&", "and")
        out_path = os.path.join(out_dir, f"{safe_name}.jpg")
        print(f"▶  {theme}")
        render_output_image(bg, args.quote, args.expl, theme=theme, output_filename=out_path)
        print()

    print(f"✅ Done. Open the images in: {os.path.abspath(out_dir)}\n")

if __name__ == "__main__":
    main()
