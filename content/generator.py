"""Gemini-powered quote, explanation, and dynamic description generation."""

from __future__ import annotations

import glob
import json
import logging
import os
from typing import Any

from google import genai
from google.genai import types

from content.foundation_context import get_foundation_prompt_context

logger = logging.getLogger(__name__)


def build_structured_long_explanation(
    context: str,
    foundation_connection: str,
    cta: str,
    hashtags: list[str],
) -> str:
    """Assemble the web-facing long explanation from structured components.

    Does NOT repeat the quote or event sentence.
    """
    sections = [
        context.strip(),
        f"**How this connects with our mission:**\n{foundation_connection.strip()}",
        f"**Take Action:**\n{cta.strip()}",
    ]
    if hashtags:
        tag_line = " ".join(hashtags)
        sections.append(tag_line)
    return "\n\n".join(s for s in sections if s)


def build_social_caption(
    quote: str,
    context: str,
    foundation_connection: str,
    cta: str,
    hashtags: list[str],
) -> str:
    """Assemble a clean social media caption without redundant duplication."""
    sections = [
        f'"{quote.strip()}"',
        context.strip(),
        foundation_connection.strip(),
        cta.strip(),
    ]
    if hashtags:
        sections.append(" ".join(hashtags))
    return "\n\n".join(s for s in sections if s)


class ContentGenerator:
    """Generates theme-specific quote and structured description content using Gemini."""

    def __init__(self, config: dict[str, Any], project_root: str) -> None:
        self._config = config
        self._project_root = project_root
        gemini_config = config["gemini"]
        api_key_env = gemini_config.get("api_key_env", "GEMINI_API_KEY")
        api_key = os.environ.get(api_key_env)
        if not api_key:
            logger.warning("Gemini API key not found (%s). AI generation will fall back to CSV/emergency.", api_key_env)
            self._client = None
        else:
            try:
                self._client = genai.Client(api_key=api_key)
            except Exception as exc:
                logger.warning("Failed to initialize Gemini client: %s. Will fall back to CSV/emergency.", exc)
                self._client = None
        self._model = gemini_config["model"]

    @property
    def client(self) -> genai.Client:
        return self._client

    def get_recent_history(self, limit: int = 15) -> list[dict[str, Any]]:
        """Load recent posts from website_assets/archive to avoid repetition."""
        archive_dir = os.path.join(self._project_root, "website_assets", "archive")
        history: list[dict[str, Any]] = []

        if os.path.exists(archive_dir):
            files = sorted(glob.glob(os.path.join(archive_dir, "*", "metadata.json")))
            for file in files[-limit:]:
                try:
                    with open(file, "r", encoding="utf-8") as f:
                        data = json.load(f)
                        history.append(data)
                except Exception:
                    logger.warning("Failed to read history from %s", file)
        return history

    def get_recent_quotes(self) -> list[str]:
        """Load recently generated quotes to avoid repetition."""
        history = self.get_recent_history(limit=15)
        return [h.get("quote", "").strip() for h in history if h.get("quote")]

    def generate(self, theme: str, event: dict | None = None) -> dict[str, Any]:
        """Generate a complete daily content package for the given theme/event."""
        if self._client is None:
            logger.warning("Gemini client is unavailable; triggering fallback.")
            raise RuntimeError("Gemini API client not initialized (missing API key or init error).")

        recent_history = self.get_recent_history(limit=10)
        recent_quotes = [h.get("quote", "").strip() for h in recent_history if h.get("quote")]
        recent_ctas = [h.get("cta", "").strip() for h in recent_history if h.get("cta")]
        recent_hashtags = [" ".join(h.get("hashtags", [])) for h in recent_history if h.get("hashtags")]

        recent_quotes_text = "\n".join(f"- {q}" for q in recent_quotes) if recent_quotes else "None recorded."
        recent_ctas_text = "\n".join(f"- {c}" for c in recent_ctas) if recent_ctas else "None recorded."
        recent_hashtags_text = "\n".join(f"- {t}" for t in recent_hashtags) if recent_hashtags else "None recorded."

        foundation_context = get_foundation_prompt_context()

        if event:
            event_instruction = f"""
Today's Special Calendar Event:
Event Name: {event['event']}

Generate content specifically celebrating/observing this event within the context of social education.
- The quote, context, foundation connection, and CTA must directly address '{event['event']}'.
- Include hashtags specific to '{event['event']}'.
"""
        else:
            event_instruction = """
This is an evergreen theme day (NO special event).
- Do NOT mention or invent any holiday, calendar observance, or special event day.
- Focus purely on the timeless theme.
"""

        prompt = f"""
You are the lead content writer and educational strategist for Jalte Diye Foundation.
Your goal is to create an inspiring, educational, and non-repetitive daily reflection.

{foundation_context}

Theme: {theme}
{event_instruction}

Previous Recent Quotes (DO NOT REPEAT):
{recent_quotes_text}

Previous Recent CTAs (DO NOT REPEAT):
{recent_ctas_text}

Previous Recent Hashtag Sets (DO NOT REPEAT):
{recent_hashtags_text}

Required Output Schema:
Return ONLY valid JSON matching this exact structure:
{{
    "quote": "10 to 20 word inspirational quote on the theme/event (for poster)",
    "explanation": "Short 2-sentence explanation for the poster image (maximum 35 words)",
    "context": "Why this topic matters to society, ethics, or human growth (2 to 3 sentences, 40 to 70 words). Do NOT repeat the quote here.",
    "foundation_connection": "Explain how today's topic specifically connects to Jalte Diye Foundation's mission of social education, awareness, empathy, or community responsibility (2 to 4 sentences, 40 to 80 words). Be dynamic and topic-specific. DO NOT use canned formulaic phrases like 'At Jalte Diye Foundation, we believe...'. DO NOT invent fake programs or statistics.",
    "cta": "One concrete, practical action step the reader or community can take today (1 to 2 sentences, 20 to 40 words)",
    "hashtags": ["#DynamicTag1", "#DynamicTag2", "#DynamicTag3", "#DynamicTag4"]
}}

Key Instructions:
1. Tone: Warm, insightful, educational, reflective, and empowering.
2. Distinctiveness: Every section must be unique. Never repeat the quote inside the context, foundation connection, or CTA.
3. Groundedness: Do not invent fake charity programs, numbers of beneficiaries, or partnerships.
4. Hashtags: Provide 3 to 6 valid hashtags starting with '#'. At least 2 must be strongly topic/event-specific. Avoid generic hashtag spam.
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
            context = str(parsed.get("context", "")).strip()
            foundation_conn = str(parsed.get("foundation_connection", "")).strip()
            cta = str(parsed.get("cta", "")).strip()
            raw_hashtags = parsed.get("hashtags", [])

            # Format and sanitize hashtags
            if isinstance(raw_hashtags, str):
                raw_hashtags = raw_hashtags.split()
            hashtags = []
            for tag in raw_hashtags:
                tag_str = str(tag).strip()
                if tag_str:
                    if not tag_str.startswith("#"):
                        tag_str = f"#{tag_str}"
                    hashtags.append(tag_str)

            # Safety word-count trims if model generated slightly over length
            quote_words = quote.split()
            if len(quote_words) > 20:
                quote = " ".join(quote_words[:20])

            explanation_words = explanation.split()
            if len(explanation_words) > 35:
                explanation = " ".join(explanation_words[:35])

            if not quote or not explanation or not context or not foundation_conn or not cta:
                raise ValueError("Gemini response missing one or more required fields.")

            long_explanation = build_structured_long_explanation(
                context=context,
                foundation_connection=foundation_conn,
                cta=cta,
                hashtags=hashtags,
            )

            caption = build_social_caption(
                quote=quote,
                context=context,
                foundation_connection=foundation_conn,
                cta=cta,
                hashtags=hashtags,
            )

            return {
                "quote": quote,
                "explanation": explanation,
                "context": context,
                "foundation_connection": foundation_conn,
                "cta": cta,
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
