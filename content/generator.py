"""Gemini-powered quote and explanation generation."""

from __future__ import annotations
import glob

import json
import logging
import os
from typing import Any

from google import genai
from google.genai import types

HASHTAGS_MAP = {
    "Peace & Justice": "#Cogentic #JalteDiyeFoundation #PeaceAndJustice #SocialCohesion #EthicalAI",
    "Health & Mindfulness": "#Cogentic #JalteDiyeFoundation #Mindfulness #MentalWellbeing #HolisticHealth",
    "Quality Education": "#Cogentic #JalteDiyeFoundation #SocialEducation #CriticalThinking #QualityEducation",
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

    def get_recent_quotes(self) -> list[str]:
        """Load recently generated quotes to avoid repetition.

        Reads from website_assets/archive, which is committed back to the
        repo every day by the workflow. The local output/ folder is NOT
        committed, so a fresh checkout always sees it empty — using it
        here meant Gemini had no real memory of what was posted before,
        which is part of why quotes were repeating across days.
        """
        archive_dir = os.path.join(self._project_root, "website_assets", "archive")
        quotes = []

        if os.path.exists(archive_dir):
            files = sorted(
                glob.glob(os.path.join(archive_dir, "*", "metadata.json"))
            )

            for file in files[-15:]:
                try:
                    with open(file, "r", encoding="utf-8") as f:
                        data = json.load(f)
                        quote = data.get("quote", "").strip()
                        if quote:
                            quotes.append(quote)
                except Exception:
                    logger.warning("Failed to read %s", file)

        return quotes

    def generate(self, theme: str, event: dict | None = None) -> dict[str, str]:
        """Generate a quote and explanation for the given theme."""

        recent_quotes = self.get_recent_quotes()

        if recent_quotes:
            recent_quotes_text = "\n".join(
                f"- {quote}" for quote in recent_quotes
            )
        else:
            recent_quotes_text = "No previous quotes available."

        # NOTE: this used to be nested inside the "no recent quotes" branch
        # above, which was both a syntax error (bad indentation) and a logic
        # bug (event_instruction was undefined whenever recent_quotes was
        # non-empty). It's now computed unconditionally, as intended.
        if event:
            event_instruction = f"""
Today's Special Event:
{event['event']}

Generate content specifically for this event.

Do NOT generate generic content.

The quote, explanation and hashtags must clearly relate to {event['event']}.
"""
        else:
            event_instruction = ""

        prompt = f"""
You are the official content writer for Jalte Diye Foundation.

{event_instruction}

Theme:
{theme}

Previous Quotes:
{recent_quotes_text}

Requirements:

- Never repeat previous quotes.
- Never repeat wording.
- Never repeat sentence structure.
- Generate ONE inspirational quote.
- Quote length: 10–20 words.
- Generate ONE short explanation (for the image).
- Exactly two sentences.
- Maximum 35 words.
- Generate ONE detailed explanation (for the webpage).
- 8 to 10 sentences.
- 150 to 200 words.
- Conversational, insightful, blog-style writing.
- Expands on the quote and theme with real-world relevance.
- Generate 4–6 hashtags.

Return ONLY JSON.

{{
    "quote": "",
    "explanation": "",
    "long_explanation": "",
    "hashtags": []
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

            parsed = json.loads(response.text)

            quote = str(parsed.get("quote", "")).strip()
            explanation = str(parsed.get("explanation", "")).strip()
            long_explanation = str(parsed.get("long_explanation", "")).strip()

            # Safety limit for quote (maximum 20 words)
            quote_words = quote.split()
            if len(quote_words) > 20:
                quote = " ".join(quote_words[:20])

            # Safety limit for explanation (maximum 35 words)
            explanation_words = explanation.split()
            if len(explanation_words) > 35:
                explanation = " ".join(explanation_words[:35])

            # Safety limit for long_explanation (maximum 220 words)
            long_expl_words = long_explanation.split()
            if len(long_expl_words) > 220:
                long_explanation = " ".join(long_expl_words[:220])

            if not quote or not explanation:
                raise ValueError(
                    "Gemini response missing quote or explanation fields."
                )

            hashtags = parsed.get("hashtags", [])

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
                "long_explanation": long_explanation,
                "caption": caption,
                "hashtags": hashtags,
            }

        except json.JSONDecodeError as exc:
            logger.exception("Failed to parse Gemini generation response as JSON.")
            raise ValueError("Invalid JSON returned by Gemini generation.") from exc

        except Exception:
            logger.exception("Gemini content generation failed for theme: %s", theme)
            raise
