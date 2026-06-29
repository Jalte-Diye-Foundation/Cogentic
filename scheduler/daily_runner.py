"""Daily automated content pipeline for Cogentic AI."""

from __future__ import annotations

import json
import logging
import os
import random
import time
import traceback
from datetime import date
from typing import Any

from content.generator import ContentGenerator, HASHTAGS_MAP
from content.evaluator import ContentEvaluator
from content.fallback import FallbackProvider, is_quote_used, mark_quote_used
from content.generator import ContentGenerator
from rendering.poster_generator import PosterGenerator

logger = logging.getLogger(__name__)


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


def select_theme(config: dict[str, Any]) -> str:
    themes = list(config["themes"].keys())
    selected = random.choice(themes)
    logger.info("Selected theme: %s", selected)
    return selected


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
    return selected, theme_config["layout"]


def generate_with_evaluation(
    theme: str,
    config: dict[str, Any],
    project_root: str,
    generator: ContentGenerator,
    evaluator: ContentEvaluator,
    fallback: FallbackProvider,
) -> tuple[dict[str, str], str]:
    """Run generation, evaluation, retries, and optional CSV fallback."""
    max_retries = config["quality"]["max_retries"]
    retry_delay = config["quality"]["retry_delay_seconds"]
    used_quotes_log = os.path.join(project_root, config["paths"]["used_quotes_log"])
    source = "gemini"

    try:
        for attempt in range(1, max_retries + 1):
            logger.info("Generation attempt %s/%s", attempt, max_retries)
            draft = generator.generate(theme)
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
        content = fallback.get_fallback_quote(theme)
        source = "csv_fallback"
        return content, source

    except Exception as exc:
        logger.error("Pipeline error during generation/evaluation: %s", exc)
        logger.error("Traceback:\n%s", traceback.format_exc())
        content = fallback.get_fallback_quote(theme)
        source = "csv_fallback_error"
        return content, source


def run_daily_pipeline(
    config_path: str | None = None,
    project_root: str | None = None,
) -> dict[str, Any]:
    """Execute the full daily content pipeline and return run metadata."""
    project_root = project_root or os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    config_path = config_path or os.path.join(project_root, "config.json")
    config = load_config(config_path)

    log_file = os.path.join(project_root, config["paths"]["log_file"])
    setup_logging(log_file)
    logger.info("Starting daily Cogentic content pipeline.")

    theme = select_theme(config)
    background_path, layout_name = select_background(theme, config, project_root)

    generator = ContentGenerator(config, project_root)
    evaluator = ContentEvaluator(config, client=generator.client)
    fallback = FallbackProvider(config, project_root)
    poster_generator = PosterGenerator(config, project_root)

    content, content_source = generate_with_evaluation(
        theme, config, project_root, generator, evaluator, fallback
    )
    logger.info("Final content source: %s", content_source)
    logger.info("Final quote: %s", content["quote"])
    logger.info("Final explanation: %s", content["explanation"])

    today = date.today().isoformat()
    output_dir = os.path.join(project_root, config["paths"]["output_dir"], today)
    output_filename = config["poster"]["output_filename"]
    output_path = os.path.join(output_dir, output_filename)

       try:
        poster_generator.render(
            quote=content["quote"],
            explanation=content["explanation"],
            background_path=background_path,
            output_path=output_path,
            layout_name=layout_name,   # kept for compatibility
            theme=theme,               # pass the theme here
        )
        logger.info("Poster creation succeeded: %s", output_path)

        metadata = {
    "date": today,
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
        "theme": theme,
        "background": background_path,
        "content_source": content_source,
        "quote": content["quote"],
        "explanation": content["explanation"],
        "poster_path": output_path,
    }

    logger.info("Daily pipeline completed successfully.")
    return result
