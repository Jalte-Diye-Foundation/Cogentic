"""LinkedIn publishing integration for Cogentic AI daily content."""

from __future__ import annotations

import json
import logging
import os
from typing import Any

logger = logging.getLogger(__name__)


def load_config(config_path: str) -> dict[str, Any]:
    with open(config_path, "r", encoding="utf-8") as handle:
        return json.load(handle)


def _read_latest_metadata(project_root: str, config: dict[str, Any]) -> dict[str, Any]:
    website_config = config["website"]
    latest_dir = os.path.join(project_root, config["paths"]["website_latest_dir"])
    metadata_path = os.path.join(latest_dir, website_config["metadata_filename"])
    if not os.path.exists(metadata_path):
        raise FileNotFoundError(f"Metadata not found: {metadata_path}")
    with open(metadata_path, "r", encoding="utf-8") as handle:
        return json.load(handle)


def _build_post_text(metadata: dict[str, Any]) -> str:
    caption = metadata.get("caption", "").strip()
    quote = metadata.get("quote", "").strip()
    explanation = metadata.get("explanation", "").strip()
    hashtags = metadata.get("hashtags", [])

    parts: list[str] = []
    if caption:
        parts.append(caption)
    elif quote:
        parts.append(f'"{quote}"')
        if explanation:
            parts.append(explanation)

    if hashtags:
        tag_line = " ".join(
            tag if tag.startswith("#") else f"#{tag.lstrip('#')}" for tag in hashtags
        )
        parts.append(tag_line)

    return "\n\n".join(part for part in parts if part)


def publish_to_linkedin(
    config: dict[str, Any] | None = None,
    project_root: str | None = None,
    config_path: str | None = None,
) -> dict[str, Any]:
    """
    Publish the latest Cogentic poster and caption to LinkedIn.

    Reads website_assets/latest/poster.jpg and metadata.json, then posts
    when LINKEDIN_ACCESS_TOKEN is configured.

    LinkedIn API integration points (to be wired when credentials are available):
      1. Register/upload image asset via LinkedIn Images API
      2. Create UGC post via POST /v2/ugcPosts with author URN and asset URN
    """
    project_root = project_root or os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    config_path = config_path or os.path.join(project_root, "config.json")
    config = config or load_config(config_path)

    linkedin_config = config["linkedin"]
    token_env = linkedin_config.get("access_token_env", "LINKEDIN_ACCESS_TOKEN")
    access_token = os.getenv(token_env, "").strip()

    website_config = config["website"]
    latest_dir = os.path.join(project_root, config["paths"]["website_latest_dir"])
    poster_path = os.path.join(latest_dir, website_config["poster_filename"])

    if not access_token:
        message = "LinkedIn publishing skipped: token not configured"
        logger.info(message)
        print(message)
        return {"status": "skipped", "reason": "missing_token"}

    if not os.path.exists(poster_path):
        message = f"LinkedIn publishing skipped: poster not found at {poster_path}"
        logger.warning(message)
        print(message)
        return {"status": "skipped", "reason": "missing_poster"}

    metadata = _read_latest_metadata(project_root, config)
    post_text = _build_post_text(metadata)

    logger.info("LinkedIn post prepared (%s characters).", len(post_text))
    logger.info("Poster for upload: %s", poster_path)

    # ------------------------------------------------------------------
    # LinkedIn API call will be implemented here when credentials are set.
    #
    # Example flow:
    #   headers = {"Authorization": f"Bearer {access_token}", "Content-Type": "application/json"}
    #   1. Upload image:
    #        POST {api_base_url}/assets?action=registerUpload
    #   2. PUT binary image to returned upload URL
    #   3. Create post:
    #        POST {api_base_url}/ugcPosts
    #        body includes author, lifecycleState, specificContent, visibility
    # ------------------------------------------------------------------
    api_base_url = linkedin_config.get("api_base_url", "https://api.linkedin.com/v2")
    logger.info(
        "LinkedIn API ready (token configured). Base URL: %s", api_base_url
    )
    print(
        "LinkedIn publishing ready: token configured, API integration pending deployment."
    )

    return {
        "status": "ready",
        "poster_path": poster_path,
        "post_text_preview": post_text[:280],
        "api_base_url": api_base_url,
    }


def main() -> None:
    """Standalone entry point for GitHub Actions LinkedIn publishing step."""
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

    result = publish_to_linkedin(config=config, project_root=project_root)
    logger.info("LinkedIn publishing step finished: %s", result.get("status"))


if __name__ == "__main__":
    main()
