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

    # Check for event on that date
    events_path = os.path.join(project_root, "events.json")
    with open(events_path, "r", encoding="utf-8") as f:
        events = json.load(f)

    today_event = events.get(target_mmdd)

    # Determine theme using same logic as daily_runner
    if today_event:
        theme = today_event["theme"]
        print(f"📅 Date       : {target_date}")
        print(f"🎉 Event      : {today_event['event']}")
        print(f"🎨 Theme      : {theme}")
    else:
        # Read recent themes from archive to avoid repeats
        archive_dir = os.path.join(project_root, "website_assets", "archive")
        recent_themes = []
        if os.path.exists(archive_dir):
            for folder in sorted(os.listdir(archive_dir))[-5:]:
                meta_path = os.path.join(archive_dir, folder, "metadata.json")
                if os.path.exists(meta_path):
                    try:
                        with open(meta_path, "r", encoding="utf-8") as f:
                            data = json.load(f)
                        t = data.get("theme")
                        if t:
                            recent_themes.append(t)
                    except Exception:
                        pass

        all_themes = list(config["themes"].keys())
        available = [t for t in all_themes if t not in recent_themes] or all_themes

        print(f"📅 Date           : {target_date}")
        print(f"🎨 Theme (random pool): {available}")
        print(f"   (one of the above will be picked at runtime)")
        # Pick first available for preview
        theme = available[0]
        print(f"   Previewing with : {theme}")
        today_event = None

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
