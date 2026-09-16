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
You are a strict, senior Quality Control Editor for Jalte Diye Foundation.
Evaluate the following complete daily social education content package.

{foundation_context}

Theme: "{theme}"
{event_info}

Content to evaluate:
{json.dumps(content, indent=2)}

Evaluation Criteria:
1. Relevance: Content must strongly align with the theme "{theme}" (and event if specified).
2. Grounded Foundation Connection: The connection must realistically link to Jalte Diye Foundation's actual mission of social education, awareness, empathy, and community responsibility. Reject any fabricated claims of physical facilities, funding amounts, or fake partnerships.
3. Clarity & Quality: Insightful, non-cliché writing.
4. Actionability: Practical, constructive CTA.
5. Non-Repetitive: The quote must NOT be repeated inside context/foundation_connection/CTA. No canned formulaic phrasing.
6. Hashtag Relevance: 3-6 specific, relevant hashtags starting with '#'.

Score on a strict scale of 1 to 10 (where 10 is exemplary and 1 is generic, repetitive, or flawed).
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
