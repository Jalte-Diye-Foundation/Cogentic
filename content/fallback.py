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
        "context": "Fostering peace and justice begins with how we treat those around us in everyday interactions. When communities cultivate fairness and open dialogue, trust replaces division.",
        "foundation_connection": "Jalte Diye Foundation emphasizes ethical living and constructive social awareness as essential foundations for community harmony and mutual dignity.",
        "cta": "Engage in active listening today and seek common ground in conversations where perspectives differ.",
        "hashtags": ["#PeaceAndJustice", "#EthicalLiving", "#CommunityDialogue", "#SocialEducation"],
    },
    "Climate & Environment": {
        "context": "Our natural ecosystems sustain every facet of human life and culture. Thoughtful environmental stewardship ensures that future generations inherit a thriving planet.",
        "foundation_connection": "Through social education, Jalte Diye Foundation seeks to deepen community awareness around sustainability and responsible ecological choices.",
        "cta": "Take one conscious action today to conserve energy, minimize waste, or support local green initiatives.",
        "hashtags": ["#ClimateAction", "#Sustainability", "#EnvironmentalCare", "#JalteDiyeFoundation"],
    },
    "Quality Education": {
        "context": "Education is the cornerstone of personal agency and collective societal advancement. Accessible learning unlocks human potential and nurtures critical thinking.",
        "foundation_connection": "Jalte Diye Foundation champions lifelong learning and accessible social knowledge to empower every individual to contribute meaningfully to society.",
        "cta": "Share an educational resource, mentor a curious learner, or dedicate time to learning a new skill today.",
        "hashtags": ["#QualityEducation", "#LifelongLearning", "#KnowledgeSharing", "#SocialEmpowerment"],
    },
    "Women Empowerment": {
        "context": "True societal progress requires equal opportunities, dignity, and active representation for women across all spheres of life.",
        "foundation_connection": "Jalte Diye Foundation actively supports awareness around gender equity, inclusion, and the vital leadership of women in community development.",
        "cta": "Amplify women's voices in your workplace and community, and support women-led initiatives.",
        "hashtags": ["#WomenEmpowerment", "#GenderEquality", "#EqualOpportunity", "#CommunityLeadership"],
    },
    "Health & Mindfulness": {
        "context": "Mental peace and physical well-being form the basis of our resilience and empathy toward others. Mindful living nurtures holistic health.",
        "foundation_connection": "At Jalte Diye Foundation, we believe that emotional well-being and mindful reflection are fundamental to positive social and interpersonal engagement.",
        "cta": "Take five quiet minutes today for mindful breathing and check in on a friend or colleague's well-being.",
        "hashtags": ["#HealthAndMindfulness", "#MentalWellness", "#MindfulLiving", "#SelfCare"],
    },
    "Foundation Events": {
        "context": "Commemorative observances remind us of shared human history, cultural milestones, and our collective responsibility to one another.",
        "foundation_connection": "Jalte Diye Foundation observes these occasions to encourage community reflection, cultural appreciation, and shared civic values.",
        "cta": "Take time to reflect on the meaning of today's observance and share its core lesson with someone near you.",
        "hashtags": ["#CommunityCelebration", "#CivicAwareness", "#SocialValues", "#JalteDiyeFoundation"],
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
