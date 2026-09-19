"""Content validation engine for Cogentic AI descriptions.

Implements two levels of repetition and quality validation:
- Level 1: Deterministic checks (exact matching, schema conformity,
           hashtag validation, template repetition, unsupported claims).
- Level 2: Similarity checks (token overlap, Jaccard, n-gram Cosine
           similarity against recent history).
"""

from __future__ import annotations

import math
import re
import string
from collections import Counter
from typing import Any

# Disallowed fabricated claim keywords / patterns
UNSUPPORTED_CLAIM_PATTERNS = [
    r"\bwe have (built|opened|constructed|funded)\b",
    r"\bwe distributed\b",
    r"\bwe (donated|raised) \$?\d+",
    r"\bwe provided food to \d+",
    r"\bour (\d+|hundreds of|thousands of) volunteers across",
    r"\bour (shelters|hospitals|schools|branches|clinics)\b",
    r"\bpartnered with (unicef|unesco|who|the government)\b",
    r"\bover \d+ beneficiaries\b",
    r"\bour feeding program\b",
    r"\bour medical camps\b",
]

# Cliché template / canned opening patterns that must not be repeated across posts
CANNED_OPENINGS = [
    "at jalte diye foundation, this reflection on",
    "at jalte diye foundation, we believe",
    "showing up for our community, listening first",
    "turning good intentions into real, visible action",
    "we believe lasting change comes from small, consistent efforts",
    "a shared meal, an open conversation, a helping hand extended",
    "as always, we invite you to join us",
    "serves as a reminder that",
    "this serves as a reminder",
    "it is important to remember that",
    "together, we can build a better",
]

# Overly abstract corporate / NGO buzzwords to monitor for density
CORPORATE_NGO_BUZZWORDS = [
    "fostering",
    "cultivating",
    "essential foundations",
    "collective responsibility",
    "positive social impact",
    "constructive social awareness",
    "holistic development",
    "mutual dignity",
    "ethical transformation",
    "meaningful change begins",
    "pivotal role",
    "beacon of hope",
    "catalyst for change",
]

# Disallowed empty slogan CTAs without concrete action
EMPTY_SLOGAN_CTAS = [
    "be the change",
    "make a difference",
    "spread awareness",
    "join us in creating positive change",
    "take meaningful action today",
]

# Configurable similarity thresholds
DEFAULT_SIMILARITY_THRESHOLDS = {
    "quote": 0.65,
    "foundation_connection": 0.70,
    "cta": 0.65,
    "full_description": 0.75,
}


def normalize_text(text: str) -> str:
    """Normalize text by lowercasing, stripping punctuation, and collapsing whitespace."""
    if not text:
        return ""
    # Lowercase
    text = text.lower()
    # Remove punctuation except word characters and whitespace
    text = text.translate(str.maketrans("", "", string.punctuation))
    # Collapse multiple whitespaces
    return re.sub(r"\s+", " ", text).strip()


def get_ngrams(words: list[str], n: int = 2) -> list[tuple[str, ...]]:
    """Return n-grams from a list of words."""
    if len(words) < n:
        return [tuple(words)] if words else []
    return [tuple(words[i : i + n]) for i in range(len(words) - n + 1)]


def cosine_similarity(text1: str, text2: str, n: int = 2) -> float:
    """Calculate n-gram cosine similarity between two texts."""
    norm1 = normalize_text(text1)
    norm2 = normalize_text(text2)
    if not norm1 or not norm2:
        return 0.0
    if norm1 == norm2:
        return 1.0

    words1 = norm1.split()
    words2 = norm2.split()

    ngrams1 = get_ngrams(words1, n)
    ngrams2 = get_ngrams(words2, n)

    vec1 = Counter(ngrams1)
    vec2 = Counter(ngrams2)

    intersection = set(vec1.keys()) & set(vec2.keys())
    numerator = sum(vec1[x] * vec2[x] for x in intersection)

    sum1 = sum(val**2 for val in vec1.values())
    sum2 = sum(val**2 for val in vec2.values())
    denominator = math.sqrt(sum1) * math.sqrt(sum2)

    if not denominator:
        return 0.0
    return float(numerator) / denominator


def jaccard_similarity(text1: str, text2: str) -> float:
    """Calculate token-level Jaccard similarity."""
    set1 = set(normalize_text(text1).split())
    set2 = set(normalize_text(text2).split())
    if not set1 or not set2:
        return 0.0
    intersection = set1 & set2
    union = set1 | set2
    return len(intersection) / len(union) if union else 0.0


class ContentValidator:
    """Validates generated daily content against repetition, quality, and grounding rules."""

    def __init__(
        self,
        similarity_thresholds: dict[str, float] | None = None,
    ) -> None:
        self.thresholds = similarity_thresholds or DEFAULT_SIMILARITY_THRESHOLDS

    def validate_hashtags(self, hashtags: list[str], theme: str, event: dict | None = None) -> list[str]:
        """Validate hashtag format, count, and uniqueness."""
        errors: list[str] = []
        if not isinstance(hashtags, list) or len(hashtags) < 3 or len(hashtags) > 6:
            errors.append(f"Hashtags count must be between 3 and 6 (got {len(hashtags) if isinstance(hashtags, list) else 0})")
            return errors

        clean_tags = []
        for tag in hashtags:
            if not isinstance(tag, str) or not tag.startswith("#"):
                errors.append(f"Invalid hashtag format: '{tag}' (must start with #)")
                continue
            cleaned = tag.strip()
            if len(cleaned) <= 1:
                errors.append(f"Empty hashtag: '{tag}'")
                continue
            if not re.match(r"^#[A-Za-z0-9_]+$", cleaned):
                errors.append(f"Hashtag contains invalid characters: '{cleaned}'")
                continue
            clean_tags.append(cleaned.lower())

        if len(clean_tags) != len(set(clean_tags)):
            errors.append("Duplicate hashtags found within post")

        return errors

    def validate_deterministic(
        self,
        content: dict[str, Any],
        theme: str,
        event: dict | None = None,
        recent_history: list[dict[str, Any]] | None = None,
    ) -> list[str]:
        """Level 1 Deterministic checks."""
        errors: list[str] = []
        recent_history = recent_history or []

        quote = str(content.get("quote", "")).strip()
        context = str(content.get("context", "")).strip()
        foundation_conn = str(content.get("foundation_connection", "")).strip()
        cta = str(content.get("cta", "")).strip()
        hashtags = content.get("hashtags", [])

        # Field presence
        if not quote:
            errors.append("Missing or empty 'quote'")
        if not context:
            errors.append("Missing or empty 'context'")
        if not foundation_conn:
            errors.append("Missing or empty 'foundation_connection'")
        if not cta:
            errors.append("Missing or empty 'cta'")

        # Hashtag validation
        tag_errors = self.validate_hashtags(hashtags, theme, event)
        errors.extend(tag_errors)

        # Markdown formatting check (no literal markdown asterisks allowed in fields)
        for field_name, field_val in [
            ("quote", quote),
            ("explanation", str(content.get("explanation", ""))),
            ("context", context),
            ("foundation_connection", foundation_conn),
            ("cta", cta),
            ("long_explanation", str(content.get("long_explanation", ""))),
        ]:
            if "**" in field_val or "__" in field_val:
                errors.append(f"Detected literal markdown asterisks or formatting in '{field_name}'")

        # Long explanation separation check (must not embed hashtags, avoiding downstream duplication)
        long_expl = str(content.get("long_explanation", "")).strip()
        if long_expl and "#" in long_expl:
            errors.append("Long explanation must not contain hashtags (hashtags are maintained separately)")

        # Repetition within post: Quote appearing in other sections
        quote_norm = normalize_text(quote)
        if quote_norm:
            for field_name, field_val in [("context", context), ("foundation_connection", foundation_conn), ("cta", cta)]:
                field_norm = normalize_text(field_val)
                if quote_norm in field_norm:
                    errors.append(f"Quote text repeated inside '{field_name}'")

        # Event handling verification
        event_name = event.get("event") if event else None
        if event_name:
            event_norm = normalize_text(event_name)
            # Event post should mention or reflect the event
            combined_text_norm = normalize_text(f"{quote} {context} {foundation_conn} {cta}")
            if event_norm not in combined_text_norm:
                # If exact name not in text, check key words
                event_keywords = [w for w in event_norm.split() if len(w) > 3]
                if event_keywords and not any(kw in combined_text_norm for kw in event_keywords):
                    errors.append(f"Event post does not reflect today's event: '{event_name}'")
        else:
            # Non-event day: Must NOT contain event-specific announcements
            combined_text_lower = f"{quote} {context} {foundation_conn} {cta}".lower()
            if "observing " in combined_text_lower or "today we celebrate " in combined_text_lower:
                errors.append("Non-event day contains event observation phrasing")

        # Unsupported claims detection
        combined_text = f"{context} {foundation_conn} {cta}"
        for pattern in UNSUPPORTED_CLAIM_PATTERNS:
            if re.search(pattern, combined_text, re.IGNORECASE):
                errors.append(f"Detected unsupported Foundation claim matching pattern: {pattern}")

        # Template repetition detection (canned phrases)
        combined_text_lower = f"{context} {foundation_conn} {cta}".lower()
        for canned in CANNED_OPENINGS:
            if canned in combined_text_lower:
                errors.append(f"Detected canned template phrase: '{canned}'")

        # History comparison: Exact duplicates
        curr_quote_norm = normalize_text(quote)
        curr_context_norm = normalize_text(context)
        curr_conn_norm = normalize_text(foundation_conn)
        curr_cta_norm = normalize_text(cta)
        curr_tag_set = set(t.lower() for t in hashtags if isinstance(t, str))

        for prev in recent_history:
            prev_quote_norm = normalize_text(prev.get("quote", ""))
            prev_context_norm = normalize_text(prev.get("context", ""))
            prev_conn_norm = normalize_text(prev.get("foundation_connection", ""))
            prev_cta_norm = normalize_text(prev.get("cta", ""))
            prev_tag_set = set(t.lower() for t in prev.get("hashtags", []) if isinstance(t, str))

            if curr_quote_norm and curr_quote_norm == prev_quote_norm:
                errors.append(f"Exact duplicate quote found in history: '{quote[:60]}...'")
            if curr_context_norm and curr_context_norm == prev_context_norm:
                errors.append("Exact duplicate context found in history")
            if curr_conn_norm and curr_conn_norm == prev_conn_norm:
                errors.append("Exact duplicate foundation_connection found in history")
            if curr_cta_norm and curr_cta_norm == prev_cta_norm:
                errors.append("Exact duplicate CTA found in history")
            if curr_tag_set and curr_tag_set == prev_tag_set:
                errors.append("Identical hashtag set found in recent history")

        # Humanization and natural tone validation
        human_errors = self.validate_humanization(content, recent_history)
        errors.extend(human_errors)

        return errors

    def validate_humanization(
        self,
        content: dict[str, Any],
        recent_history: list[dict[str, Any]] | None = None,
    ) -> list[str]:
        """Validate that writing feels human, warm, conversational, and not filled with corporate NGO buzzwords."""
        errors: list[str] = []
        recent_history = recent_history or []

        context = str(content.get("context", "")).strip()
        foundation_conn = str(content.get("foundation_connection", "")).strip()
        cta = str(content.get("cta", "")).strip()
        combined_text_lower = f"{context} {foundation_conn} {cta}".lower()

        # 1. Check corporate/NGO buzzword density
        found_buzzwords = [bw for bw in CORPORATE_NGO_BUZZWORDS if bw in combined_text_lower]
        if len(found_buzzwords) >= 3:
            errors.append(f"Excessive corporate/NGO buzzword density ({len(found_buzzwords)} detected: {', '.join(found_buzzwords)})")

        # 2. Check for empty slogan CTAs without concrete everyday action
        cta_norm = normalize_text(cta)
        for empty_slogan in EMPTY_SLOGAN_CTAS:
            if cta_norm == normalize_text(empty_slogan):
                errors.append(f"CTA is a generic slogan without concrete action: '{cta}'")

        # 3. Check opening variety against recent history (avoid formulaic repeated openings)
        curr_conn_words = normalize_text(foundation_conn).split()
        if len(curr_conn_words) >= 4:
            curr_opening_4 = " ".join(curr_conn_words[:4])
            for prev in recent_history[-5:]:
                prev_conn_words = normalize_text(prev.get("foundation_connection", "")).split()
                if len(prev_conn_words) >= 4:
                    prev_opening_4 = " ".join(prev_conn_words[:4])
                    if curr_opening_4 == prev_opening_4:
                        errors.append(f"Repeated formulaic Foundation opening across consecutive posts: '{curr_opening_4}'")
                        break

        return errors

    def validate_similarity(
        self,
        content: dict[str, Any],
        recent_history: list[dict[str, Any]],
    ) -> tuple[list[str], dict[str, float]]:
        """Level 2 Similarity checks."""
        errors: list[str] = []
        max_similarities: dict[str, float] = {
            "quote": 0.0,
            "foundation_connection": 0.0,
            "cta": 0.0,
            "full_description": 0.0,
        }

        if not recent_history:
            return errors, max_similarities

        curr_quote = content.get("quote", "")
        curr_conn = content.get("foundation_connection", "")
        curr_cta = content.get("cta", "")
        curr_full = f"{content.get('context', '')} {curr_conn} {curr_cta}"

        for prev in recent_history:
            prev_quote = prev.get("quote", "")
            prev_conn = prev.get("foundation_connection", "")
            prev_cta = prev.get("cta", "")
            prev_full = f"{prev.get('context', '')} {prev_conn} {prev_cta}"

            sim_q = cosine_similarity(curr_quote, prev_quote, n=2)
            sim_conn = cosine_similarity(curr_conn, prev_conn, n=2)
            sim_cta = cosine_similarity(curr_cta, prev_cta, n=2)
            sim_full = cosine_similarity(curr_full, prev_full, n=2)

            max_similarities["quote"] = max(max_similarities["quote"], sim_q)
            max_similarities["foundation_connection"] = max(max_similarities["foundation_connection"], sim_conn)
            max_similarities["cta"] = max(max_similarities["cta"], sim_cta)
            max_similarities["full_description"] = max(max_similarities["full_description"], sim_full)

            if sim_q > self.thresholds["quote"]:
                errors.append(
                    f"Quote similarity ({sim_q:.2f}) exceeds threshold ({self.thresholds['quote']})"
                )
            if sim_conn > self.thresholds["foundation_connection"]:
                errors.append(
                    f"Foundation connection similarity ({sim_conn:.2f}) exceeds threshold ({self.thresholds['foundation_connection']})"
                )
            if sim_cta > self.thresholds["cta"]:
                errors.append(
                    f"CTA similarity ({sim_cta:.2f}) exceeds threshold ({self.thresholds['cta']})"
                )
            if sim_full > self.thresholds["full_description"]:
                errors.append(
                    f"Full description similarity ({sim_full:.2f}) exceeds threshold ({self.thresholds['full_description']})"
                )

        return errors, max_similarities

    def validate_full(
        self,
        content: dict[str, Any],
        theme: str,
        event: dict | None = None,
        recent_history: list[dict[str, Any]] | None = None,
    ) -> tuple[bool, list[str], dict[str, float]]:
        """Run full Level 1 and Level 2 validation."""
        recent_history = recent_history or []
        errors = self.validate_deterministic(content, theme, event, recent_history)
        sim_errors, sim_scores = self.validate_similarity(content, recent_history)
        all_errors = errors + sim_errors
        return len(all_errors) == 0, all_errors, sim_scores
