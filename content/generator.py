"""Gemini-powered quote and explanation generation."""

from __future__ import annotations

import json
import logging
import os
from typing import Any

from google import genai
import content
from google.genai import types

HASHTAGS_MAP = {
    "Peace & Justice": "#Cogentic #JalteDiyeFoundation #PeaceAndJustice #SocialCohesion #EthicalAI",
    "Health & Mindfulness": "#Cogentic #JalteDiyeFoundation #Mindfulness #MentalWellbeing #HolisticHealth",
    "Social Education": "#Cogentic #JalteDiyeFoundation #SocialEducation #CriticalThinking #QualityEducation",
    "Climate & Environment": "#Cogentic #JalteDiyeFoundation #ClimateAction #Sustainability #EcoResponsibility",
    "Women Empowerment": "#Cogentic #JalteDiyeFoundation #WomenEmpowerment #Equality #Inspiration",
    "Foundation Events": "#Cogentic #JalteDiyeFoundation #CommunityImpact #SocialChange #Events"
}

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

    def generate(self, theme: str) -> dict[str, str]:
        """Generate a quote and explanation for the given theme."""
        prompt = f"""
You are the official content writer for Jalte Diye Foundation.

Generate a fresh and inspiring social media post for the theme "{theme}".

Requirements:

- Generate ONE original quote.
- Quote must be between 10 and 20 words.
- Make it inspirational and easy to read.

- Generate ONE explanation.
- Exactly TWO sentences.
- Maximum 35 words total.
- Do not repeat the quote.
- Keep it simple and suitable for a square social media poster.

- Generate 4 to 6 relevant hashtags.

Return ONLY valid JSON.

{{
    "quote": "...",
    "explanation": "...",
    "hashtags": [
        "#...",
        "#..."
    ]
}}
"""

        try:
            response = self._client.models.generate_content(
                model=self._model,
                contents=prompt,
                config=types.GenerateContentConfig(
                    response_mime_type="application/json",
                ),
            )

            content = json.loads(response.text)

            quote = str(content.get("quote", "")).strip()
            explanation = str(content.get("explanation", "")).strip()

            # Safety limit for quote (maximum 20 words)
            quote_words = quote.split()
            if len(quote_words) > 20:
                quote = " ".join(quote_words[:20])

            # Safety limit for explanation (maximum 35 words)
            explanation_words = explanation.split()
            if len(explanation_words) > 35:
                explanation = " ".join(explanation_words[:35])

            if not quote or not explanation:
                raise ValueError(
                    "Gemini response missing quote or explanation fields."
                )

            hashtags = content.get("hashtags", [])

            # If Gemini returns hashtags as a string
            if isinstance(hashtags, str):
                hashtags = hashtags.split()

            hashtags_text = " ".join(hashtags)

            caption = (
                f"{quote}\n\n"
                f"{explanation}\n\n"
                f"{hashtags_text}"
            )

            return {
                "quote": quote,
                "explanation": explanation,
                "caption": caption,
                "hashtags": hashtags,
            }

        except json.JSONDecodeError as exc:
            logger.exception("Failed to parse Gemini generation response as JSON.")
            raise ValueError("Invalid JSON returned by Gemini generation.") from exc

        except Exception:
            logger.exception("Gemini content generation failed for theme: %s", theme)
            raise