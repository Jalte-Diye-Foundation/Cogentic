"""CSV fallback content and duplicate quote tracking."""

from __future__ import annotations

import csv
import logging
import os
from typing import Any

from content.generator import build_social_caption, build_structured_long_explanation

logger = logging.getLogger(__name__)

# Dynamic theme-specific synthesis for fallback scenarios (avoiding fixed canned repetition)
THEME_FALLBACK_TEMPLATES = {
    "Peace & Justice": {
        "context": "Peace isn't just about treaties signed in distant capitals. It shows up every day in the way we listen, disagree with patience, and treat people when things get tense.",
        "foundation_connection": "For us at Jalte Diye Foundation, social education starts with simple fairness and empathy. When we choose understanding over judgment, we make our neighborhoods safer and kinder for everyone.",
        "cta": "Have one conversation today where you listen fully before preparing your reply.",
        "hashtags": ["#PeaceAndJustice", "#DailyKindness", "#CommunityDialogue", "#SocialEducation"],
    },
    "Climate & Environment": {
        "context": "The choices we make in our daily routines—what we consume, what we throw away, and what we care for—shape the neighborhood our kids will grow up in.",
        "foundation_connection": "At Jalte Diye Foundation, our environmental focus is about practical everyday responsibility. Caring for the planet isn't an abstract theory; it's a series of small, thoughtful habits we practice together.",
        "cta": "Pick one small habit today to reduce waste—like carrying a reusable water bottle or cloth bag.",
        "hashtags": ["#ClimateCare", "#DailyHabits", "#EcoAwareness", "#JalteDiyeFoundation"],
    },
    "Quality Education": {
        "context": "Real learning happens far beyond school walls. It happens whenever someone asks a good question, learns from a mistake, or shares a skill with a friend.",
        "foundation_connection": "Education is at the very core of Jalte Diye Foundation. We believe that when knowledge is shared freely and kindly, it gives people the confidence to shape their own lives.",
        "cta": "Share one interesting thing you learned recently with someone who might enjoy hearing it.",
        "hashtags": ["#QualityEducation", "#LifelongLearning", "#ShareKnowledge", "#SocialEducation"],
    },
    "Women Empowerment": {
        "context": "Every family and community thrives when women have the space to speak, make decisions, and lead without fear or artificial barriers.",
        "foundation_connection": "Promoting gender equity and mutual respect is a vital part of Jalte Diye Foundation's social education efforts. Real progress happens when women's ideas and voices are genuinely heard and supported.",
        "cta": "Make space today to support and encourage a woman's voice or idea in your workplace or family circle.",
        "hashtags": ["#WomenEmpowerment", "#EqualVoices", "#CommunityRespect", "#SocialEducation"],
    },
    "Health & Mindfulness": {
        "context": "Taking care of your mental peace isn't selfish—it's what gives you the patience and empathy to show up well for the people who rely on you.",
        "foundation_connection": "Emotional well-being and mindfulness are central to Jalte Diye Foundation's holistic view of social education. Calm, grounded individuals build more caring and supportive communities.",
        "cta": "Take a quiet five-minute pause today to breathe deeply and check in on how you're feeling.",
        "hashtags": ["#HealthAndMindfulness", "#MentalPeace", "#SelfCare", "#DailyCalm"],
    },
    "Foundation Events": {
        "context": "Special calendar days give us a welcome reason to pause our busy routines and remember the values that bring our communities together.",
        "foundation_connection": "Jalte Diye Foundation observes these occasions to encourage reflection, community conversations, and shared appreciation for our common humanity.",
        "cta": "Take two minutes today to learn about today's observance and share one thoughtful takeaway with a friend.",
        "hashtags": ["#CommunityObservance", "#CivicAwareness", "#SharedValues", "#JalteDiyeFoundation"],
    },
}


def load_used_quotes(log_path: str) -> set[str]:
    """Load previously used quotes from the persistent log file."""
    if not os.path.exists(log_path):
        return set()
    with open(log_path, "r", encoding="utf-8") as handle:
        return {line.strip() for line in handle if line.strip()}


def is_quote_used(quote: str, log_path: str) -> bool:
    """Return True if the quote has already been used."""
    normalized = quote.strip()
    if not normalized:
        return False
    return normalized in load_used_quotes(log_path)


def mark_quote_used(quote: str, log_path: str) -> None:
    """Append a quote to the used-quotes log to prevent future reuse."""
    normalized = quote.strip()
    if not normalized:
        return
    os.makedirs(os.path.dirname(log_path) or ".", exist_ok=True)
    with open(log_path, "a", encoding="utf-8") as handle:
        handle.write(normalized + "\n")
    logger.info("Marked quote as used: %s", normalized[:80])


class FallbackProvider:
    """Provides unused quotes from theme-specific CSV files with structured fallback descriptions."""

    def __init__(self, config: dict[str, Any], project_root: str) -> None:
        self._config = config
        self._project_root = project_root
        self._used_quotes_log = self._resolve_path(config["paths"]["used_quotes_log"])
        self._emergency = config["emergency_failsafe"]

    def _resolve_path(self, relative_path: str) -> str:
        return os.path.join(self._project_root, relative_path)

    def get_fallback_quote(self, theme: str, event: dict | None = None) -> dict[str, Any]:
        """Pull an unused quote from the CSV mapped to the given theme."""
        logger.warning("Triggering CSV fallback for theme: %s", theme)
        theme_config = self._config["themes"].get(theme)
        if not theme_config:
            logger.error("No theme configuration found for: %s", theme)
            return self._emergency_failsafe(theme, event)

        csv_file = self._resolve_path(theme_config["csv_fallback"])
        if not os.path.exists(csv_file):
            logger.error("Missing CSV fallback file for %s: %s", theme, csv_file)
            return self._emergency_failsafe(theme, event)

        used_quotes = load_used_quotes(self._used_quotes_log)
        event_name = event["event"] if event else None
        fallback_content = self._read_unused_csv_quote(csv_file, used_quotes, event_name)
        if fallback_content:
            mark_quote_used(fallback_content["quote"], self._used_quotes_log)
            # Assemble structured metadata
            tpl = THEME_FALLBACK_TEMPLATES.get(theme, THEME_FALLBACK_TEMPLATES["Foundation Events"])
            context = tpl["context"]
            foundation_conn = tpl["foundation_connection"]
            cta = tpl["cta"]
            hashtags = list(tpl["hashtags"])
            if event_name:
                event_tag = f"#{event_name.replace(' ', '').replace('&', 'And').replace('-', '')}"
                if event_tag not in hashtags:
                    hashtags.insert(0, event_tag)

            fallback_content["context"] = context
            fallback_content["foundation_connection"] = foundation_conn
            fallback_content["cta"] = cta
            fallback_content["hashtags"] = hashtags
            fallback_content["long_explanation"] = build_structured_long_explanation(
                context=context,
                foundation_connection=foundation_conn,
                cta=cta,
                hashtags=hashtags,
            )
            fallback_content["caption"] = build_social_caption(
                quote=fallback_content["quote"],
                context=context,
                foundation_connection=foundation_conn,
                cta=cta,
                hashtags=hashtags,
            )
            logger.info("Retrieved fallback quote from CSV: %s", csv_file)
            return fallback_content

        logger.critical("No unused quotes remain in CSV: %s", csv_file)
        return self._emergency_failsafe(theme, event)

    def _read_unused_csv_quote(
        self, csv_file: str, used_quotes: set[str], event_name: str | None = None
    ) -> dict[str, str] | None:
        with open(csv_file, "r", encoding="utf-8-sig") as handle:
            raw_rows = [row for row in csv.reader(handle) if row and any(c.strip() for c in row)]
            if not raw_rows:
                return None

            first_non_empty = [cell.strip().lower() for cell in raw_rows[0]]
            has_headers = "quote" in first_non_empty

            if has_headers:
                headers = first_non_empty
                quote_idx = headers.index("quote")
                caption_idx = headers.index("caption") if "caption" in headers else -1
                occasion_idx = headers.index("occasion") if "occasion" in headers else -1
                data_rows = raw_rows[1:]
            else:
                # Headerless 2-column CSV (e.g. quotes.csv: [quote, caption])
                quote_idx = 0
                caption_idx = 1 if len(raw_rows[0]) > 1 else -1
                occasion_idx = -1
                data_rows = raw_rows

        if event_name and occasion_idx != -1:
            candidate_rows = [
                r for r in data_rows
                if len(r) > occasion_idx and r[occasion_idx].strip().lower() == event_name.lower()
            ]
            if not candidate_rows:
                logger.warning("No CSV rows for event '%s'; using generic fallback row.", event_name)
                candidate_rows = data_rows
        else:
            candidate_rows = data_rows

        for row in candidate_rows:
            if not row or len(row) <= quote_idx:
                continue

            row_quote = row[quote_idx].strip()
            row_explanation = ""
            if caption_idx != -1 and len(row) > caption_idx:
                row_explanation = row[caption_idx].strip()
            elif occasion_idx != -1 and len(row) > occasion_idx:
                occasion_val = row[occasion_idx].strip()
                if event_name and occasion_val.lower() == event_name.lower():
                    row_explanation = f"Observing {occasion_val}."

            if row_quote and row_quote not in used_quotes:
                return {
                    "quote": row_quote.replace('"', ""),
                    "explanation": row_explanation.replace('"', ""),
                }
        return None

    def _emergency_failsafe(self, theme: str = "", event: dict | None = None) -> dict[str, Any]:
        logger.warning("Using emergency hardcoded failsafe quote.")
        quote = self._emergency["quote"]
        explanation = self._emergency["explanation"]
        tpl = THEME_FALLBACK_TEMPLATES.get(theme, THEME_FALLBACK_TEMPLATES["Foundation Events"])
        context = tpl["context"]
        foundation_conn = tpl["foundation_connection"]
        cta = tpl["cta"]
        hashtags = list(tpl["hashtags"])
        if event and event.get("event"):
            event_name = event["event"]
            hashtags.insert(0, f"#{event_name.replace(' ', '')}")

        return {
            "quote": quote,
            "explanation": explanation,
            "context": context,
            "foundation_connection": foundation_conn,
            "cta": cta,
            "hashtags": hashtags,
            "long_explanation": build_structured_long_explanation(
                context=context,
                foundation_connection=foundation_conn,
                cta=cta,
                hashtags=hashtags,
            ),
            "caption": build_social_caption(
                quote=quote,
                context=context,
                foundation_connection=foundation_conn,
                cta=cta,
                hashtags=hashtags,
            ),
        }
