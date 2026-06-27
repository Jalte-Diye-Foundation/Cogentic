"""Gemini-powered quote and explanation generation."""

from __future__ import annotations

import json
import logging
import os
from typing import Any

from google import genai
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
    You are an expert social media copywriter for the Jalte Diye Foundation.
    Create an original, highly inspiring quote and a matching 2-sentence explanation
    specifically tailored to the theme: "{theme}".

    Return ONLY a valid JSON object with this exact schema:
    {{"quote": "...", "explanation": "..."}}
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

            if not quote or not explanation:
                raise ValueError("Gemini response missing quote or explanation fields.")

            hashtags = HASHTAGS_MAP.get(theme, "")

            caption = (
                f"{quote}\n\n"
                f"{explanation}\n\n"
                f"{hashtags}"
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