"""
Comprehensive Test Suite for Cogentic AI Pipeline.
Validates poster alignment, dynamic typography scaling, date-aware event selection,
CSV fallback mechanics, and website asset updates.
"""

from __future__ import annotations

import json
import os
import shutil
import tempfile
from datetime import datetime, timezone, timedelta
from PIL import Image, ImageDraw

from image_gen import (
    load_font,
    wrap_text,
    block_height,
    measure_text_height,
    measure_text_width,
    calculate_adaptive_layout,
    render_output_image,
    THEME_REGISTRY,
    GLOBAL_LAYOUT,
)
from content.fallback import FallbackProvider
from scheduler.daily_runner import (
    select_theme,
    get_today_event,
    load_events,
    EVERGREEN_THEMES,
)
from website_assets.update_assets import update_website_assets


def test_poster_alignment_no_overflow():
    """Test that all combinations of quote lengths, explanation lengths, themes, and dimensions never overflow."""
    print("\n--- TEST 1: Poster Alignment & Zero-Overflow Validation ---")
    themes = [
        "Peace & Justice",
        "Climate & Environment",
        "Quality Education",
        "Women Empowerment",
        "Health & Mindfulness",
        "Foundation Events",
    ]

    test_cases = [
        ("Short", "Peace begins with a smile.", "A simple smile can break walls."),
        (
            "Medium",
            "True peace is not the absence of tension, it is the presence of justice.",
            "Justice requires continuous commitment and unwavering courage in every single community across all nations.",
        ),
        (
            "Long",
            "Education is the most powerful weapon which you can use to change the world and elevate every single human soul to its highest potential.",
            "When young minds are ignited with curiosity, wisdom, and moral responsibility, the ripples transform societies for generations to come across all nations.",
        ),
        (
            "Very Long Expl",
            "Where understanding grows, war finds no soil.",
            "In every corner of our shared earth, when communities choose dialogue over division, empathy over estrangement, and mutual respect over mistrust, the fragile seeds of enduring peace take root and blossom into a shared sanctuary of dignity and hope for all children.",
        ),
        (
            "Multi-line",
            "Look closely at nature,\nand you will understand\neverything better.",
            "Every leaf carries a lesson in resilience, harmony, and renewal.\nCherish the ground beneath your feet.",
        ),
    ]

    dimensions = [(1080, 1080), (1080, 1350)]
    failures = []

    for theme in themes:
        cfg = THEME_REGISTRY[theme]
        for W, H in dimensions:
            img = Image.new("RGB", (W, H))
            draw = ImageDraw.Draw(img)
            for q_name, q_text, exp_text in test_cases:
                (
                    q_font,
                    e_font,
                    q_lines,
                    e_lines,
                    line_spacing,
                    block_gap,
                    total_h,
                    zone_top,
                    zone_bottom,
                ) = calculate_adaptive_layout(
                    quote_text=q_text,
                    explanation_text=exp_text,
                    W=W,
                    H=H,
                    cfg=cfg,
                    draw=draw,
                    font_name=GLOBAL_LAYOUT["font_name"],
                )

                y_cursor = zone_top + max(0, (zone_bottom - zone_top - total_h) // 2)
                end_y = y_cursor + total_h
                overflow = end_y - zone_bottom

                if overflow > 0:
                    failures.append(
                        f"FAILED: {theme} ({W}x{H}) [{q_name}] Overflow: +{overflow}px"
                    )
                else:
                    assert y_cursor >= zone_top, f"y_cursor ({y_cursor}) < zone_top ({zone_top})"
                    assert end_y <= zone_bottom, f"end_y ({end_y}) > zone_bottom ({zone_bottom})"

    assert len(failures) == 0, f"Alignment test failures: {failures}"
    print(f"✓ All {len(themes) * len(dimensions) * len(test_cases)} layout variations passed with ZERO overflow.")


def test_date_aware_event_selection():
    """Test date-aware theme selection and seasonal event handling."""
    print("\n--- TEST 2: Date-Aware Event Selection Validation ---")
    project_root = os.path.dirname(os.path.abspath(__file__))
    config_path = os.path.join(project_root, "config.json")
    with open(config_path, "r", encoding="utf-8") as f:
        config = json.load(f)

    # 1. Test August 5 (Non-event day): Should NEVER select Lohri or Foundation Events
    august_5 = datetime(2026, 8, 5, 10, 0, tzinfo=timezone(timedelta(hours=5, minutes=30)))
    for _ in range(20):
        theme, event = select_theme(config, project_root, current_dt=august_5)
        assert event is None, f"Expected no event on August 5, got {event}"
        assert theme in EVERGREEN_THEMES, f"Expected evergreen theme on August 5, got {theme}"
        assert theme != "Foundation Events", "Foundation Events must not be selected on non-event days"
    print("✓ August 5 correctly selected evergreen themes across 20 iterations without selecting Foundation Events.")

    # 2. Test January 13 (Lohri): Must select Lohri event
    jan_13 = datetime(2026, 1, 13, 10, 0, tzinfo=timezone(timedelta(hours=5, minutes=30)))
    theme_lohri, event_lohri = select_theme(config, project_root, current_dt=jan_13)
    assert event_lohri is not None, "Expected Lohri event on Jan 13"
    assert event_lohri["event"] == "Lohri", f"Expected Lohri, got {event_lohri}"
    assert theme_lohri == "Foundation Events", f"Expected Foundation Events theme, got {theme_lohri}"
    print("✓ January 13 correctly selected Lohri event.")

    # 3. Test August 15 (Independence Day): Must select Independence Day event
    aug_15 = datetime(2026, 8, 15, 10, 0, tzinfo=timezone(timedelta(hours=5, minutes=30)))
    theme_ind, event_ind = select_theme(config, project_root, current_dt=aug_15)
    assert event_ind is not None, "Expected Independence Day on Aug 15"
    assert event_ind["event"] == "Independence Day", f"Expected Independence Day, got {event_ind}"
    print("✓ August 15 correctly selected Independence Day.")


def test_date_aware_csv_fallback():
    """Test that CSV fallback respects active events and avoids out-of-season rows."""
    print("\n--- TEST 3: CSV Fallback Date-Awareness Validation ---")
    project_root = os.path.dirname(os.path.abspath(__file__))
    config_path = os.path.join(project_root, "config.json")
    with open(config_path, "r", encoding="utf-8") as f:
        config = json.load(f)

    with tempfile.TemporaryDirectory() as temp_dir:
        test_config = dict(config)
        test_config["paths"] = dict(config["paths"])
        test_log_path = os.path.join(temp_dir, "test_used_quotes.txt")
        test_config["paths"]["used_quotes_log"] = os.path.relpath(test_log_path, project_root)

        fp = FallbackProvider(test_config, project_root)

        # 1. Fallback for Health & Mindfulness (quotes.csv with no header row)
        hm_quote = fp.get_fallback_quote("Health & Mindfulness")
        assert hm_quote["quote"], "Health & Mindfulness fallback quote should not be empty"
        assert hm_quote["explanation"], "Health & Mindfulness fallback explanation should not be empty"
        print("✓ Health & Mindfulness correctly parsed quote from headerless quotes.csv.")

        # 2. Fallback on Non-event day (Foundation Events requested): Must NOT return Lohri
        no_event_quote = fp.get_fallback_quote("Foundation Events", today_event=None, current_date_str="2026-08-05")
        assert "Lohri" not in no_event_quote["quote"] and "Lohri" not in no_event_quote["explanation"], (
            f"Non-event fallback returned Lohri quote: {no_event_quote}"
        )
        print("✓ Non-event day fallback safely avoided returning out-of-season Lohri.")

        # 3. Fallback on Independence Day: Should return Independence Day quote from Event_quotes.csv
        ind_event = {"event": "Independence Day", "theme": "Foundation Events"}
        ind_quote = fp.get_fallback_quote("Foundation Events", today_event=ind_event, current_date_str="2026-08-15")
        assert ind_quote["quote"], "Independence Day fallback quote should not be empty"
        assert "Independence Day" in ind_quote["explanation"] or "freedom" in ind_quote["quote"].lower(), (
            f"Expected Independence Day quote, got: {ind_quote}"
        )
        print("✓ Independence Day fallback matched the specific August 15 event.")

        # 4. Fallback on Lohri: Should return Lohri quote from Event_quotes.csv
        lohri_event = {"event": "Lohri", "theme": "Foundation Events"}
        lohri_quote = fp.get_fallback_quote("Foundation Events", today_event=lohri_event, current_date_str="2026-01-13")
        assert "Lohri" in lohri_quote["quote"] or "Lohri" in lohri_quote["explanation"], (
            f"Expected Lohri quote, got: {lohri_quote}"
        )
        print("✓ Lohri fallback correctly returned Lohri quote on Jan 13 event day.")


def test_website_asset_update():
    """Test website asset update and archiving."""
    print("\n--- TEST 4: Website Asset Update & Archiving Validation ---")
    project_root = os.path.dirname(os.path.abspath(__file__))
    config_path = os.path.join(project_root, "config.json")
    with open(config_path, "r", encoding="utf-8") as f:
        config = json.load(f)

    with tempfile.TemporaryDirectory() as temp_dir:
        test_poster_path = os.path.join(temp_dir, "test_poster.jpg")
        img = Image.new("RGB", (1080, 1080), color=(50, 100, 150))
        img.save(test_poster_path)

        pipeline_result = {
            "date": "2026-08-30",
            "theme": "Peace & Justice",
            "poster_path": test_poster_path,
            "content": {
                "quote": "Peace begins with a smile.",
                "explanation": "A simple smile can break walls.",
                "caption": "Peace begins with a smile.\n\nA simple smile can break walls.",
                "hashtags": ["#Peace", "#Cogentic"],
            },
            "event": None,
        }

        res = update_website_assets(
            pipeline_result=pipeline_result,
            config=config,
            project_root=project_root,
        )

        assert os.path.exists(res["poster_path"]), f"Latest poster not found at {res['poster_path']}"
        assert os.path.exists(res["metadata_path"]), f"Latest metadata not found at {res['metadata_path']}"

        with open(res["metadata_path"], "r", encoding="utf-8") as f:
            saved_metadata = json.load(f)

        assert saved_metadata["theme"] == "Peace & Justice"
        assert saved_metadata["quote"] == "Peace begins with a smile."
        assert saved_metadata["date"] == "2026-08-30"

        # Check archive
        archive_metadata = os.path.join(project_root, "website_assets", "archive", "2026-08-30", "metadata.json")
        assert os.path.exists(archive_metadata), f"Archived metadata not found at {archive_metadata}"
        print("✓ Website asset update and archival successfully verified.")


def run_all_tests():
    print("============================================================")
    print("RUNNING COGENTIC COMPLETE AUDIT & FIX TEST SUITE")
    print("============================================================")
    test_poster_alignment_no_overflow()
    test_date_aware_event_selection()
    test_date_aware_csv_fallback()
    test_website_asset_update()
    print("\n============================================================")
    print("ALL TESTS COMPLETED SUCCESSFULLY!")
    print("============================================================")


if __name__ == "__main__":
    run_all_tests()
