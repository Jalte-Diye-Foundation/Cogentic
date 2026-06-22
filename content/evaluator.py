"""AI quality evaluation for generated content."""

from __future__ import annotations

import json
import logging
from typing import Any

from google import genai
from google.genai import types

logger = logging.getLogger(__name__)


class ContentEvaluator:
    """Evaluates generated content quality using the Gemini API."""

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
                raise ValueError(
                    f"Gemini API key not found. Set the {api_key_env} environment variable."
                )
            self._client = genai.Client(api_key=api_key)
        self._model = config["gemini"]["model"]
        self._passing_score = config["quality"]["passing_score"]

    @property
    def passing_score(self) -> int:
        return self._passing_score

    def evaluate(self, theme: str, content: dict[str, str]) -> dict[str, Any]:
        """Score content on alignment, clarity, and emotional impact."""
        prompt = f"""
    You are a strict Quality Control Editor for a social education foundation.
    Evaluate the following quote and explanation based on its alignment with the theme "{theme}",
    its clarity, and its emotional impact.

    Content to evaluate:
    {json.dumps(content)}

    Score it on a scale of 1 to 10 (where 10 is breathtakingly profound and 1 is generic/confusing).
    Return ONLY a valid JSON object with this exact schema:
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
