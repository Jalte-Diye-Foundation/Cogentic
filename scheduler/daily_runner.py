"""Daily automated content pipeline for Cogentic AI."""

from __future__ import annotations

import json
import logging
import os
import random
import time
import traceback
from datetime import date, datetime, timezone, timedelta
from typing import Any

from content.generator import ContentGenerator
from content.evaluator import ContentEvaluator
from content.fallback import FallbackProvider, is_quote_used, mark_quote_used
from content.validator import ContentValidator
from rendering.poster_generator import PosterGenerator

logger = logging.getLogger(__name__)

# Indian Standard Time (UTC+05:30)
IST = timezone(timedelta(hours=5, minutes=30))


def get_current_ist_date() -> date:
    """Return the current calendar date in Indian Standard Time (IST)."""
    return datetime.now(IST).date()


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


def load_events(project_root: str) -> dict[str, Any]:
    """Load events from events.json (repo root)."""
    events_file = os.path.join(project_root, "events.json")
    if not os.path.exists(events_file):
        return {}
    with open(events_file, "r", encoding="utf-8") as f:
        return json.load(f)


def get_today_event(project_root: str, target_date: date | None = None) -> dict[str, Any] | None:
    """Return today's event if one exists."""
    events = load_events(project_root)
    d = target_date or get_current_ist_date()
    today = d.strftime("%m-%d")
    return events.get(today)


def select_theme(
    config: dict[str, Any],
    project_root: str,
    target_date: date | None = None,
    recent_themes: list[str] | None = None,
) -> tuple[str, dict[str, Any] | None]:
    """Select today's theme. Event days take priority; non-event days use evergreen themes."""
    today_event = get_today_event(project_root, target_date)
    if today_event:
        logger.info("Today's event: %s (Theme: %s)", today_event["event"], today_event["theme"])
        return today_event["theme"], today_event

    # Normal theme rotation - strictly evergreen themes (exclude 'Foundation Events')
    all_themes = list(config["themes"].keys())
    evergreen_themes = [t for t in all_themes if t != "Foundation Events"]

    if recent_themes is None:
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
                        if theme and theme != "Foundation Events":
                            recent_themes.append(theme)
                    except Exception:
                        pass

    available = [t for t in evergreen_themes if t not in recent_themes]
    if not available:
        available = evergreen_themes

    selected = random.choice(available)
    logger.info("Recent themes: %s", recent_themes)
    logger.info("Selected evergreen theme: %s", selected)
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
        raise FileNotFoundError(f"No background images found in theme folder: {theme_folder}")

    selected = random.choice(candidates)
    logger.info("Selected background: %s", selected)
    return selected, theme_config["layout"]


def generate_with_evaluation(
    theme: str,
    today_event: dict | None,
    config: dict[str, Any],
    project_root: str,
    generator: ContentGenerator,
    evaluator: ContentEvaluator,
    fallback: FallbackProvider,
    validator: ContentValidator | None = None,
) -> tuple[dict[str, Any], str]:
    """Run generation, multi-level validation, evaluation, retries, and optional fallback."""
    max_retries = config["quality"]["max_retries"]
    retry_delay = config["quality"]["retry_delay_seconds"]
    used_quotes_log = os.path.join(project_root, config["paths"]["used_quotes_log"])
    validator = validator or ContentValidator()
    recent_history = generator.get_recent_history(limit=15)
    source = "gemini"

    try:
        for attempt in range(1, max_retries + 1):
            logger.info("Generation attempt %s/%s for theme '%s'", attempt, max_retries, theme)
            draft = generator.generate(theme, today_event)
            logger.info("Draft quote: %s", draft["quote"][:120])

            # Level 0: Quick used quote check
            if is_quote_used(draft["quote"], used_quotes_log):
                logger.warning("Quote already in used_quotes_log.txt; retrying (attempt %s).", attempt)
                if attempt < max_retries:
                    time.sleep(retry_delay)
                continue

            # Level 1 & Level 2 Validation
            is_valid, val_errors, sim_scores = validator.validate_full(
                draft, theme, today_event, recent_history
            )
            if not is_valid:
                logger.warning(
                    "Content failed validation on attempt %s: %s (Sim scores: %s)",
                    attempt,
                    val_errors,
                    sim_scores,
                )
                if attempt < max_retries:
                    time.sleep(retry_delay)
                continue

            # AI Quality Evaluation
            evaluation = evaluator.evaluate(theme, draft, today_event)
            score = evaluation.get("score", 0)
            reasoning = evaluation.get("reasoning", "")
            logger.info("Evaluation score: %s/10 | Reasoning: %s", score, reasoning)

            if evaluator.passed(evaluation):
                logger.info("Content passed quality control on attempt %s.", attempt)
                mark_quote_used(draft["quote"], used_quotes_log)
                draft["evaluator_score"] = score
                draft["evaluator_reasoning"] = reasoning
                draft["similarity_scores"] = sim_scores
                return draft, source

            logger.warning("Content rejected by evaluator on attempt %s (score: %s).", attempt, score)
            if attempt < max_retries:
                time.sleep(retry_delay)

        logger.warning(
            "Failed to generate acceptable content after %s attempts; using CSV fallback.",
            max_retries,
        )
        content = fallback.get_fallback_quote(theme, today_event)
        source = "csv_fallback"
        return content, source

    except Exception as exc:
        logger.error("Pipeline error during generation/evaluation: %s", exc)
        logger.error("Traceback:\n%s", traceback.format_exc())
        content = fallback.get_fallback_quote(theme, today_event)
        source = "csv_fallback_error"
        return content, source


def run_daily_pipeline(
    config_path: str | None = None,
    project_root: str | None = None,
    target_date: date | str | None = None,
) -> dict[str, Any]:
    """Execute the full daily content pipeline and return run metadata."""
    project_root = project_root or os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    config_path = config_path or os.path.join(project_root, "config.json")
    config = load_config(config_path)

    log_file = os.path.join(project_root, config["paths"]["log_file"])
    setup_logging(log_file)
    logger.info("Starting daily Cogentic content pipeline.")

    if isinstance(target_date, str):
        today_date = date.fromisoformat(target_date)
    elif isinstance(target_date, date):
        today_date = target_date
    else:
        today_date = get_current_ist_date()
    today_str = today_date.isoformat()

    # One post per day guard
    archive_check_dir = os.path.join(project_root, "website_assets", "archive", today_str)
    if os.path.exists(archive_check_dir) and os.listdir(archive_check_dir):
        logger.info(
            "Archived post for today (%s) already exists at %s. Skipping generation.",
            today_str,
            archive_check_dir,
        )
        return {
            "date": today_str,
            "theme": None,
            "background": None,
            "content_source": None,
            "quote": None,
            "explanation": None,
            "poster_path": None,
            "skipped": True,
            "skip_reason": "already_archived_today",
        }

    theme, today_event = select_theme(config, project_root, today_date)
    background_path, layout_name = select_background(theme, config, project_root)

    generator = ContentGenerator(config, project_root)
    evaluator = ContentEvaluator(config, client=generator.client)
    fallback = FallbackProvider(config, project_root)
    validator = ContentValidator()
    poster_generator = PosterGenerator(config, project_root)

    content, content_source = generate_with_evaluation(
        theme,
        today_event,
        config,
        project_root,
        generator,
        evaluator,
        fallback,
        validator,
    )
    logger.info("Final content source: %s", content_source)
    logger.info("Final quote: %s", content["quote"])
    logger.info("Final explanation: %s", content["explanation"])

    output_dir = os.path.join(project_root, config["paths"]["output_dir"], today_str)
    output_filename = config["poster"]["output_filename"]
    output_path = os.path.join(output_dir, output_filename)
    os.makedirs(output_dir, exist_ok=True)

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
            "context": content.get("context", ""),
            "foundation_connection": content.get("foundation_connection", ""),
            "cta": content.get("cta", ""),
            "long_explanation": content.get("long_explanation", ""),
            "caption": content.get("caption", ""),
            "hashtags": content.get("hashtags", []),
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
        "context": content.get("context", ""),
        "foundation_connection": content.get("foundation_connection", ""),
        "cta": content.get("cta", ""),
        "long_explanation": content.get("long_explanation", ""),
        "caption": content.get("caption", ""),
        "hashtags": content.get("hashtags", []),
        "poster_path": output_path,
        "event": today_event["event"] if today_event else None,
    }

    logger.info("Daily pipeline completed successfully.")
    return result
