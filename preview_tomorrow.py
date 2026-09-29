"""
Preview tomorrow's generated content (quote, explanation, long_explanation, hashtags).
Calls Gemini but saves nothing — no image, no files, no logs.

Usage:
    python preview_tomorrow.py
    python preview_tomorrow.py --date 2026-09-05   # preview a specific date
"""

import argparse
import json
import os
import sys
from datetime import date, timedelta

def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--date", default=None, help="Date to preview (YYYY-MM-DD). Defaults to tomorrow.")
    args = parser.parse_args()

    project_root = os.path.dirname(os.path.abspath(__file__))
    config_path = os.path.join(project_root, "config.json")

    with open(config_path, "r", encoding="utf-8") as f:
        config = json.load(f)

    # Determine target date
    if args.date:
        target_date = date.fromisoformat(args.date)
    else:
        target_date = date.today() + timedelta(days=1)

    target_mmdd = target_date.strftime("%m-%d")

    from scheduler.daily_runner import select_theme
    theme, today_event = select_theme(config, project_root, target_date)

    print(f"📅 Date       : {target_date}")
    if today_event:
        print(f"🎉 Event      : {today_event['event']}")
    else:
        print(f"🎉 Event      : General Awareness")
    print(f"🎨 Theme      : {theme}")

    print()
    print("⏳ Calling Gemini to generate content preview...")
    print()

    # Initialise generator
    from content.generator import ContentGenerator
    try:
        generator = ContentGenerator(config, project_root)
    except ValueError as e:
        print(f"❌ {e}")
        print("Set the GEMINI_API_KEY environment variable and try again.")
        sys.exit(1)

    content = generator.generate(theme, today_event)

    print("=" * 60)
    print(f"  PREVIEW FOR {target_date}")
    print("=" * 60)
    print(f"\n📌 Theme       : {theme}")
    print(f"\n💬 Quote\n   {content['quote']}")
    print(f"\n📝 Explanation (image)\n   {content['explanation']}")
    print(f"\n📖 Long Explanation (webpage)")
    long_expl = content.get("long_explanation", "")
    if long_expl:
        # Print each sentence on its own line for readability
        import re
        sentences = re.split(r'(?<=[.!?])\s+', long_expl)
        for s in sentences:
            print(f"   {s}")
    else:
        print("   (not generated — Gemini may not have returned this field yet)")
    print(f"\n#️⃣  Hashtags\n   {' '.join(content['hashtags']) if isinstance(content['hashtags'], list) else content['hashtags']}")
    print("\n" + "=" * 60)

if __name__ == "__main__":
    main()
