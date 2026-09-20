"""AI quality evaluation for generated content."""

from __future__ import annotations

import json
import logging
from typing import Any

from google import genai
from google.genai import types

from content.foundation_context import get_foundation_prompt_context

logger = logging.getLogger(__name__)


class ContentEvaluator:
    """Evaluates full generated content packages using the Gemini API."""

    def __init__(self, config: dict[str, Any], client: genai.Client | None = None) -> None:
        self._config = config
        if client is not None:
            self._client = client
        else:
            import os

            gemini_config = config["gemini"]
            api_key_env = gemini_config.get("api_key_env", "GEMINI_API_KEY")
            api_key = os.environ.get(api_key_env)
            if not api_key:
                logger.warning("Gemini API key not found for evaluator.")
                self._client = None
            else:
                try:
                    self._client = genai.Client(api_key=api_key)
                except Exception as exc:
                    logger.warning("Failed to initialize Gemini evaluator client: %s", exc)
                    self._client = None
        self._model = config["gemini"]["model"]
        self._passing_score = config["quality"]["passing_score"]

    @property
    def passing_score(self) -> int:
        return self._passing_score

    def evaluate(self, theme: str, content: dict[str, Any], event: dict | None = None) -> dict[str, Any]:
        """Score the complete content package on alignment, clarity, impact, grounding, and lack of repetition."""
        if self._client is None:
            raise RuntimeError("Gemini API client unavailable for evaluation.")

        foundation_context = get_foundation_prompt_context()
        event_info = f"Special Event: {event['event']}" if event else "Evergreen Theme (No Event)"

        prompt = f"""
You are a senior Quality Control Editor and Human Style Reviewer for Jalte Diye Foundation.
Evaluate the following complete daily social education content package.

{foundation_context}

Theme: "{theme}"
{event_info}

Content to evaluate:
{json.dumps(content, indent=2)}

Evaluation Criteria (Score 1-10):
1. Human Naturalness & Warmth: Does it sound like a thoughtful, caring human content writer rather than a corporate press release or robotic AI?
2. Conversational Readability: Simple, clear, and relatable language. Free of corporate NGO buzzwords ('fostering', 'cultivating', 'essential foundations', 'collective responsibility', 'holistic development', etc.).
3. Grounded & Dynamic Foundation Connection: Specifically answers why THIS topic matters to Jalte Diye Foundation's social education and empathy values. No boilerplate templates like 'At Jalte Diye Foundation, we believe...'. No fake programs or statistics.
4. Everyday Relevance: Context connects the theme to ordinary human experiences (conversations, family, work, community, habits).
5. Practical, Realistic CTA: Gives a concrete, doable action step rather than an empty slogan like 'be the change'.
6. Distinctiveness & Zero Repetition: The quote is NOT repeated in the text; sections do not repeat the same sentences or canned formulas.
7. Hashtag Relevance: 3-6 relevant, specific hashtags starting with '#' matching the quote's actual topic.
8. Cross-Section Semantic Topic Consistency: The entire post (quote, explanation, context, foundation connection, CTA, and hashtags) MUST address the exact same specific topic. A description that is well-written on its own but discusses a different topic than the quote (e.g. a women's empowerment essay attached to a refugee quote) MUST FAIL with a score of 1 to 4.

Score on a strict scale of 1 to 10:
- Score 8-10: Warm, human, natural, grounded, insightful, and 100% topic-consistent across all sections.
- Score 6-7: Acceptable but slightly formal or generic.
- Score 1-5: Robotic, academic textbook style, corporate buzzword-stuffed, repetitive, contains fabricated NGO claims, or has a TOPIC MISMATCH between quote and description.

Return ONLY valid JSON matching this schema:
{{"score": 8, "reasoning": "..."}}
"""
        try:
            response = self._client.models.generate_content(
                model=self._model,
                contents=prompt,
                config=types.GenerateContentConfig(
                    response_mime_type="application/json",
                ),
            )
            evaluation = json.loads(response.text)
            score = evaluation.get("score", 0)
            reasoning = evaluation.get("reasoning", "No reasoning provided.")
            try:
                score = int(score)
            except (TypeError, ValueError):
                logger.warning("Non-numeric score from evaluator; defaulting to 0.")
                score = 0
            return {"score": score, "reasoning": str(reasoning)}
        except json.JSONDecodeError as exc:
            logger.exception("Failed to parse Gemini evaluation response as JSON.")
            raise ValueError("Invalid JSON returned by Gemini evaluation.") from exc
        except Exception:
            logger.exception("Gemini content evaluation failed for theme: %s", theme)
            raise

    def passed(self, evaluation: dict[str, Any]) -> bool:
        return int(evaluation.get("score", 0)) >= self._passing_score
