"""Daily automated content pipeline for Cogentic AI."""

from __future__ import annotations

import json
import logging
import os
import random
import time
import traceback
from datetime import datetime, timezone, timedelta
from typing import Any

from content.generator import ContentGenerator
from content.evaluator import ContentEvaluator
from content.fallback import FallbackProvider, is_quote_used, mark_quote_used
from rendering.poster_generator import PosterGenerator

logger = logging.getLogger(__name__)

# Evergreen themes for standard daily rotation when no specific calendar event occurs
EVERGREEN_THEMES = [
    "Peace & Justice",
    "Climate & Environment",
    "Quality Education",
    "Women Empowerment",
    "Health & Mindfulness",
]


def get_ist_now() -> datetime:
    """Return the current datetime in Indian Standard Time (IST = UTC+5:30)."""
    try:
        import zoneinfo
        return datetime.now(zoneinfo.ZoneInfo("Asia/Kolkata"))
    except Exception:
        # Fallback to fixed timezone offset UTC+5:30
        ist_tz = timezone(timedelta(hours=5, minutes=30))
        return datetime.now(ist_tz)


def load_config(config_path: str) -> dict[str, Any]:
    with open(config_path, "r", encoding="utf-8") as handle:
        return json.load(handle)


def setup_logging(log_file: str) -> None:
    log_dir = os.path.dirname(log_file)
    if log_dir:
        os.makedirs(log_dir, exist_ok=True)

    root_logger = logging.getLogger()
    root_logger.setLevel(logging.INFO)

    formatter = logging.Formatter(
        "%(asctime)s | %(levelname)s | %(name)s | %(message)s",
        datefmt="%Y-%m-%d %H:%M:%S",
    )

    file_handler = logging.FileHandler(log_file, encoding="utf-8")
    file_handler.setFormatter(formatter)
    file_handler.setLevel(logging.INFO)

    stream_handler = logging.StreamHandler()
    stream_handler.setFormatter(formatter)
    stream_handler.setLevel(logging.INFO)

    root_logger.handlers.clear()
    root_logger.addHandler(file_handler)
    root_logger.addHandler(stream_handler)


def load_events(project_root: str) -> dict:
    """Load events from events.json (repo root)."""
    events_file = os.path.join(project_root, "events.json")

    if not os.path.exists(events_file):
        return {}

    with open(events_file, "r", encoding="utf-8") as f:
        return json.load(f)


def get_today_event(project_root: str, current_dt: datetime | None = None) -> dict[str, Any] | None:
    """Return today's event if one exists for the current IST date."""
    events = load_events(project_root)
    dt = current_dt or get_ist_now()
    mm_dd = dt.strftime("%m-%d")
    return events.get(mm_dd)


def select_theme(
    config: dict[str, Any],
    project_root: str,
    current_dt: datetime | None = None,
) -> tuple[str, dict[str, Any] | None]:
    """
    Select today's theme.
    Event days take priority.
    On non-event days, rotates strictly among evergreen themes (avoiding recent repeats).
    """
    dt = current_dt or get_ist_now()

    # 1. Check if today is a designated event day
    today_event = get_today_event(project_root, current_dt=dt)
    if today_event:
        selected_theme = today_event.get("theme", "Foundation Events")
        logger.info("Today's event detected: '%s' | Theme: '%s'", today_event["event"], selected_theme)
        return selected_theme, today_event

    # 2. Normal evergreen theme rotation (exclude 'Foundation Events')
    configured_themes = list(config.get("themes", {}).keys())
    candidate_themes = [t for t in EVERGREEN_THEMES if t in configured_themes]
    if not candidate_themes:
        candidate_themes = [t for t in configured_themes if t != "Foundation Events"]
    if not candidate_themes:
        candidate_themes = configured_themes

    # Read recent theme history from website_assets/archive
    archive_dir = os.path.join(project_root, "website_assets", "archive")
    recent_themes = []

    if os.path.exists(archive_dir):
        folders = sorted(os.listdir(archive_dir))
        for folder in folders[-5:]:
            metadata_path = os.path.join(archive_dir, folder, "metadata.json")
            if os.path.exists(metadata_path):
                try:
                    with open(metadata_path, "r", encoding="utf-8") as f:
                        data = json.load(f)
                    theme = data.get("theme")
                    if theme and theme in candidate_themes:
                        recent_themes.append(theme)
                except Exception:
                    pass

    available = [t for t in candidate_themes if t not in recent_themes]
    if not available:
        available = candidate_themes

    selected = random.choice(available)
    logger.info("Recent evergreen themes: %s", recent_themes)
    logger.info("Selected theme for today: %s", selected)
    return selected, None


def select_background(theme: str, config: dict[str, Any], project_root: str) -> tuple[str, str]:
    theme_config = config["themes"][theme]
    theme_folder = os.path.join(project_root, theme_config["folder"])
    extensions = {
        ext.lower()
        for ext in config["poster"].get(
            "supported_background_extensions",
            [".jpg", ".jpeg", ".png", ".webp"],
        )
    }

    if not os.path.isdir(theme_folder):
        raise FileNotFoundError(f"Theme folder not found: {theme_folder}")

    candidates = [
        os.path.join(theme_folder, filename)
        for filename in os.listdir(theme_folder)
        if os.path.splitext(filename)[1].lower() in extensions
    ]

    if not candidates:
        raise FileNotFoundError(
            f"No background images found in theme folder: {theme_folder}"
        )

    selected = random.choice(candidates)
    logger.info("Selected background: %s", selected)
    return selected, theme_config.get("layout", "left_explanation")


def generate_with_evaluation(
    theme: str,
    today_event: dict | None,
    config: dict[str, Any],
    project_root: str,
    generator: ContentGenerator,
    evaluator: ContentEvaluator,
    fallback: FallbackProvider,
    current_date_str: str | None = None,
) -> tuple[dict[str, str], str]:
    """Run generation, evaluation, retries, and date-aware CSV fallback."""
    max_retries = config["quality"]["max_retries"]
    retry_delay = config["quality"]["retry_delay_seconds"]
    used_quotes_log = os.path.join(project_root, config["paths"]["used_quotes_log"])
    source = "gemini"

    try:
        for attempt in range(1, max_retries + 1):
            logger.info("Generation attempt %s/%s", attempt, max_retries)
            draft = generator.generate(theme, today_event)
            logger.info("Draft quote: %s", draft["quote"][:120])

            if is_quote_used(draft["quote"], used_quotes_log):
                logger.warning(
                    "Generated quote already used; treating attempt %s as rejected.",
                    attempt,
                )
                if attempt < max_retries:
                    time.sleep(retry_delay)
                continue

            evaluation = evaluator.evaluate(theme, draft)
            score = evaluation.get("score", 0)
            reasoning = evaluation.get("reasoning", "")
            logger.info("Evaluation score: %s/10 | Reasoning: %s", score, reasoning)

            if evaluator.passed(evaluation):
                logger.info("Content passed quality control on attempt %s.", attempt)
                mark_quote_used(draft["quote"], used_quotes_log)
                return draft, source

            logger.warning("Content rejected on attempt %s.", attempt)
            if attempt < max_retries:
                time.sleep(retry_delay)

        logger.warning(
            "Failed to generate acceptable content after %s attempts; using CSV fallback.",
            max_retries,
        )
        content = fallback.get_fallback_quote(
            theme,
            today_event=today_event,
            current_date_str=current_date_str,
        )
        source = "csv_fallback"
        return content, source

    except Exception as exc:
        logger.error("Pipeline error during generation/evaluation: %s", exc)
        logger.error("Traceback:\n%s", traceback.format_exc())
        content = fallback.get_fallback_quote(
            theme,
            today_event=today_event,
            current_date_str=current_date_str,
        )
        source = "csv_fallback_error"
        return content, source


def run_daily_pipeline(
    config_path: str | None = None,
    project_root: str | None = None,
    current_dt: datetime | None = None,
) -> dict[str, Any]:
    """Execute the full daily content pipeline and return run metadata."""
    project_root = project_root or os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    config_path = config_path or os.path.join(project_root, "config.json")
    config = load_config(config_path)

    log_file = os.path.join(project_root, config["paths"]["log_file"])
    setup_logging(log_file)
    logger.info("Starting daily Cogentic content pipeline.")

    dt = current_dt or get_ist_now()
    today_str = dt.strftime("%Y-%m-%d")

    theme, today_event = select_theme(config, project_root, current_dt=dt)
    background_path, layout_name = select_background(theme, config, project_root)

    generator = ContentGenerator(config, project_root)
    evaluator = ContentEvaluator(config, client=generator.client)
    fallback = FallbackProvider(config, project_root)
    poster_generator = PosterGenerator(config, project_root)

    content, content_source = generate_with_evaluation(
        theme=theme,
        today_event=today_event,
        config=config,
        project_root=project_root,
        generator=generator,
        evaluator=evaluator,
        fallback=fallback,
        current_date_str=today_str,
    )
    logger.info("Final content source: %s", content_source)
    logger.info("Final quote: %s", content["quote"])
    logger.info("Final explanation: %s", content["explanation"])

    output_dir = os.path.join(project_root, config["paths"]["output_dir"], today_str)
    output_filename = config["poster"]["output_filename"]
    output_path = os.path.join(output_dir, output_filename)

    os.makedirs(output_dir, exist_ok=True)
    if os.path.exists(output_path):
        logger.info("Poster for today (%s) already exists at %s. Skipping generation.", today_str, output_path)
        return {
            "date": today_str,
            "theme": theme,
            "background": background_path,
            "content_source": content_source,
            "quote": content["quote"],
            "explanation": content["explanation"],
            "poster_path": output_path,
            "skipped": True,
            "event": today_event["event"] if today_event else None,
        }

    try:
        poster_generator.render(
            quote=content["quote"],
            explanation=content["explanation"],
            background_path=background_path,
            output_path=output_path,
            layout_name=layout_name,
            theme=theme,
        )
        logger.info("Poster creation succeeded: %s", output_path)

        metadata = {
            "date": today_str,
            "theme": theme,
            "quote": content["quote"],
            "explanation": content["explanation"],
            "caption": (
                content.get("caption")
                or f'{content["quote"]}\n\n{content["explanation"]}'
            ),
            "hashtags": (
                content.get("hashtags")
                or "#Cogentic #JalteDiyeFoundation"
            ),
            "image": output_filename,
            "source": "Cogentic AI",
            "event": today_event["event"] if today_event else None,
        }
        metadata_path = os.path.join(output_dir, "metadata.json")

        with open(metadata_path, "w", encoding="utf-8") as f:
            json.dump(metadata, f, indent=2, ensure_ascii=False)

        logger.info("Metadata saved: %s", metadata_path)

    except Exception as exc:
        logger.error("Poster creation failed: %s", exc)
        logger.error("Traceback:\n%s", traceback.format_exc())
        raise

    result = {
        "date": today_str,
        "theme": theme,
        "background": background_path,
        "content_source": content_source,
        "quote": content["quote"],
        "explanation": content["explanation"],
        "poster_path": output_path,
        "event": today_event["event"] if today_event else None,
    }

    logger.info("Daily pipeline completed successfully.")
    return result
