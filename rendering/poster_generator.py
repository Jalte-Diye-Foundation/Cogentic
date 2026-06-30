"""Poster generator that delegates to the proven image_gen module."""

from __future__ import annotations

import logging
import os
from typing import Any

from image_gen import render_output_image

logger = logging.getLogger(__name__)

class PosterGenerator:
    def __init__(self, config: dict[str, Any], project_root: str):
        self.config = config
        self.project_root = project_root

    def render(
        self,
        quote: str,
        explanation: str,
        background_path: str,
        output_path: str,
        layout_name: str,          # kept for compatibility
        theme: str | None = None,
    ) -> str:
        success = render_output_image(
            bg_image_path=background_path,
            quote_text=quote,
            explanation_text=explanation,
            theme=theme,
            output_filename=output_path,
        )
        if not success:
            raise RuntimeError(f"Poster rendering failed for {background_path}")
        logger.info(f"Poster saved: {output_path}")
        return output_path
