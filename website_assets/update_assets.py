"""Copy the latest generated poster and metadata for website consumption."""

from __future__ import annotations

import json
import logging
import os
import shutil
from datetime import datetime, timezone, timedelta
from typing import Any

logger = logging.getLogger(__name__)

IST = timezone(timedelta(hours=5, minutes=30))


def load_config(config_path: str) -> dict[str, Any]:
    with open(config_path, "r", encoding="utf-8") as handle:
        return json.load(handle)


def update_website_assets(
    pipeline_result: dict[str, Any],
    config: dict[str, Any] | None = None,
    project_root: str | None = None,
    config_path: str | None = None,
) -> dict[str, str]:
    """Copy the daily poster to website_assets/latest/ and write metadata.json."""
    project_root = project_root or os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    config_path = config_path or os.path.join(project_root, "config.json")
    config = config or load_config(config_path)

    website_config = config["website"]
    latest_dir = os.path.join(project_root, config["paths"]["website_latest_dir"])
    os.makedirs(latest_dir, exist_ok=True)

    poster_source = pipeline_result["poster_path"]
    poster_dest = os.path.join(latest_dir, website_config["poster_filename"])
    shutil.copy2(poster_source, poster_dest)
    logger.info("Website asset updated: %s -> %s", poster_source, poster_dest)

    today_str = pipeline_result.get("date") or datetime.now(IST).date().isoformat()
    archive_dir = os.path.join(project_root, "website_assets", "archive", today_str)
    os.makedirs(archive_dir, exist_ok=True)
    archive_dest = os.path.join(archive_dir, website_config["poster_filename"])
    shutil.copy2(poster_source, archive_dest)
    logger.info("Website asset archived: %s -> %s", poster_source, archive_dest)

    content = pipeline_result.get("content", {})
    quote_val = content.get("quote") or pipeline_result.get("quote", "")
    expl_val = content.get("explanation") or pipeline_result.get("explanation", "")
    context_val = content.get("context") or pipeline_result.get("context", "")
    conn_val = content.get("foundation_connection") or pipeline_result.get("foundation_connection", "")
    cta_val = content.get("cta") or pipeline_result.get("cta", "")
    long_expl_val = content.get("long_explanation") or pipeline_result.get("long_explanation", "")
    caption_val = content.get("caption") or pipeline_result.get("caption", "")
    hashtags_val = content.get("hashtags") or pipeline_result.get("hashtags", [])
    event_val = pipeline_result.get("event")
    event_name_val = content.get("event_name") or pipeline_result.get("event_name") or (event_val if event_val else "General Awareness")

    metadata = {
        "date": today_str,
        "theme": pipeline_result.get("theme", ""),
        "event_name": event_name_val,
        "quote": quote_val,
        "explanation": expl_val,
        "long_explanation": long_expl_val,
        "caption": caption_val,
        "hashtags": hashtags_val,
        "image": website_config["image_url_path"],
        "source": website_config["source_label"],
        "event": event_val,
    }

    metadata_path = os.path.join(latest_dir, website_config["metadata_filename"])
    with open(metadata_path, "w", encoding="utf-8") as handle:
        json.dump(metadata, handle, indent=2, ensure_ascii=False)
        handle.write("\n")
    logger.info("Website metadata written: %s", metadata_path)

    archive_metadata_path = os.path.join(archive_dir, website_config["metadata_filename"])
    with open(archive_metadata_path, "w", encoding="utf-8") as handle:
        json.dump(metadata, handle, indent=2, ensure_ascii=False)
        handle.write("\n")
    logger.info("Archived metadata written: %s", archive_metadata_path)

    return {
        "poster_path": poster_dest,
        "metadata_path": metadata_path,
    }


def main() -> None:
    """Standalone entry point for GitHub Actions website asset update step."""
    import sys

    project_root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    config_path = os.path.join(project_root, "config.json")
    config = load_config(config_path)

    log_file = os.path.join(project_root, config["paths"]["log_file"])
    os.makedirs(os.path.dirname(log_file), exist_ok=True)
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s | %(levelname)s | %(name)s | %(message)s",
        handlers=[
            logging.FileHandler(log_file, encoding="utf-8"),
            logging.StreamHandler(sys.stdout),
        ],
    )

    today = datetime.now(IST).date().isoformat()
    output_dir = os.path.join(project_root, config["paths"]["output_dir"], today)
    poster_filename = config["poster"]["output_filename"]
    poster_path = os.path.join(output_dir, poster_filename)
    metadata_sidecar = os.path.join(output_dir, "metadata.json")

    if not os.path.exists(poster_path):
        logger.error("Poster not found for website update: %s", poster_path)
        sys.exit(1)

    pipeline_result: dict[str, Any] = {"poster_path": poster_path, "theme": ""}
    if os.path.exists(metadata_sidecar):
        with open(metadata_sidecar, "r", encoding="utf-8") as handle:
            sidecar = json.load(handle)
        pipeline_result.update(sidecar)
        pipeline_result["content"] = {
            "quote": sidecar.get("quote", ""),
            "explanation": sidecar.get("explanation", ""),
            "context": sidecar.get("context", ""),
            "foundation_connection": sidecar.get("foundation_connection", ""),
            "cta": sidecar.get("cta", ""),
            "long_explanation": sidecar.get("long_explanation", ""),
            "caption": sidecar.get("caption", ""),
            "hashtags": sidecar.get("hashtags", []),
        }

    update_website_assets(pipeline_result, config=config, project_root=project_root)
    logger.info("Website asset update completed.")


if __name__ == "__main__":
    main()
