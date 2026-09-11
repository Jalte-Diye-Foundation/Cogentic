"""Gemini-powered quote and explanation generation."""

from __future__ import annotations
import glob

import json
import logging
import os
from typing import Any

from google import genai
from google.genai import types

logger = logging.getLogger(__name__)


class ContentGenerator:
    """Generates theme-specific quote content using the Gemini API."""

    def __init__(self, config: dict[str, Any], project_root: str) -> None:
        self._config = config
        self._project_root = project_root
        gemini_config = config["gemini"]
        api_key_env = gemini_config.get("api_key_env", "GEMINI_API_KEY")
        api_key = os.environ.get(api_key_env)
        if not api_key:
            raise ValueError(
                f"Gemini API key not found. Set the {api_key_env} environment variable."
            )
        self._client = genai.Client(api_key=api_key)
        self._model = gemini_config["model"]

    @property
    def client(self) -> genai.Client:
        return self._client

    def generate(self, theme: str) -> dict[str, Any]:
        """Generate a quote, short explanation, and long explanation for the given theme."""
        hashtags = HASHTAGS_MAP.get(theme, "#Cogentic #JalteDiyeFoundation")
        prompt = f"""
    You are an expert social media copywriter and content strategist for the Jalte Diye Foundation.
    Create original content specifically tailored to the theme: "{theme}".

    Provide:
    1. "quote": An original, highly inspiring quote.
    2. "explanation": A matching 2-sentence concise explanation (for poster image rendering).
    3. "long_explanation": A detailed, 10-12 line in-depth explanation expanding on the quote and short explanation. Connect this message deeply to the vision and social education mission of the Jalte Diye Foundation, and conclude with these relevant hashtags: {hashtags}

    Return ONLY a valid JSON object with this exact schema:
    {{"quote": "...", "explanation": "...", "long_explanation": "..."}}
    """
        try:
            response = self._client.models.generate_content(
                model=self._model,
                contents=prompt,
                config=types.GenerateContentConfig(
                    response_mime_type="application/json",
                ),
            )

            quote = str(content.get("quote", "")).strip()
            explanation = str(content.get("explanation", "")).strip()
            long_explanation = str(content.get("long_explanation", "")).strip()

            if not quote or not explanation:
                raise ValueError(
                    "Gemini response missing quote or explanation fields."
                )

            if not long_explanation:
                long_explanation = (
                    f"{explanation}\n\n"
                    f"At Jalte Diye Foundation, we believe that education and awareness under the theme of '{theme}' "
                    f"serve as the catalyst for meaningful social change. By reflecting on this message, we empower individuals "
                    f"and communities to drive sustainable impact.\n\n"
                    f"{hashtags}"
                )

            hashtags_list = [tag.strip() for tag in hashtags.split() if tag.strip()]

            caption = (
                f"{quote}\n\n"
                f"{explanation}\n\n"
                f"{hashtags_text}"
            )

            return {
                "quote": quote,
                "explanation": explanation,
                "long_explanation": long_explanation,
                "caption": caption,
                "hashtags": hashtags_list,
            }

        except json.JSONDecodeError as exc:
            logger.exception("Failed to parse Gemini generation response as JSON.")
            raise ValueError("Invalid JSON returned by Gemini generation.") from exc

        except Exception:
            logger.exception("Gemini content generation failed for theme: %s", theme)
            raise
