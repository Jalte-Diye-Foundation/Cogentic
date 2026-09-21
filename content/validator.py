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

# Disallowed empty explanation slogans or non-interpretive one-liners
DISALLOWED_EXPLANATION_SLOGANS = [
    "drop your anchor",
    "do not wait for a grand plan",
    "keep going",
    "be kind",
    "be the change",
    "make a difference",
    "stay positive",
    "stay strong",
    "never give up",
    "spread the word",
    "just do it",
    "sing it with your hands",
    "take action today",
    "find your peace",
    "lead the way",
    "believe in yourself",
]

# Common English stop words to exclude when extracting significant quote tokens
STOP_WORDS = {
    "a", "about", "above", "after", "again", "against", "all", "am", "an", "and",
    "any", "are", "aren't", "as", "at", "be", "because", "been", "before", "being",
    "below", "between", "both", "but", "by", "can", "can't", "cannot", "could",
    "couldn't", "did", "didn't", "do", "does", "doesn't", "doing", "don't", "down",
    "during", "each", "few", "for", "from", "further", "had", "hadn't", "has",
    "hasn't", "have", "haven't", "having", "he", "he'd", "he'll", "he's", "her",
    "here", "here's", "hers", "herself", "him", "himself", "his", "how", "how's",
    "i", "i'd", "i'll", "i'm", "i've", "if", "in", "into", "is", "isn't", "it",
    "it's", "its", "itself", "let's", "me", "more", "most", "mustn't", "my",
    "myself", "no", "nor", "not", "of", "off", "on", "once", "only", "or", "other",
    "ought", "our", "ours", "ourselves", "out", "over", "own", "same", "shan't",
    "she", "she'd", "she'll", "she's", "should", "shouldn't", "so", "some", "such",
    "than", "that", "that's", "the", "their", "theirs", "them", "themselves", "then",
    "there", "there's", "these", "they", "they'd", "they'll", "they're", "they've",
    "this", "those", "through", "to", "too", "under", "until", "up", "very", "was",
    "wasn't", "we", "we'd", "we'll", "we're", "we've", "were", "weren't", "what",
    "what's", "when", "when's", "where", "where's", "which", "while", "who", "who's",
    "whom", "why", "why's", "with", "won't", "would", "wouldn't", "you", "you'd",
    "you'll", "you're", "you've", "your", "yours", "yourself", "yourselves",
}

# Sub-topic / concept clusters for quote-level semantic anchor extraction and divergence checking
QUOTE_SUBTOPIC_CLUSTERS: dict[str, dict[str, Any]] = {
    "climate_math_urgency": {
        "triggers": {"math", "chalk", "calculation", "numbers", "equation", "countdown", "running out", "clock", "timer", "deadline"},
        "anchors": {"math", "calculation", "calculating", "numbers", "urgency", "time", "clock", "countdown", "emissions", "measurable", "choices", "acting", "delay", "action before", "window", "options", "damage"},
        "incompatible_subtopics": {
            "biodiversity_soil_food": {"soil", "biodiversity", "food we eat", "eating", "flora", "fauna", "wildlife", "species", "preserve the soil"},
        },
    },
    "activism_burnout_selfcare": {
        "triggers": {"activism", "activist", "selfcare", "self-care", "tension", "burnout", "movements", "advocacy"},
        "anchors": {"activism", "activist", "selfcare", "self-care", "burnout", "movement", "organizing", "exhaustion", "sustain", "sustainable", "recharge", "wellbeing", "well-being", "advocacy", "advocate", "energy", "caring for yourself", "stay engaged", "emotional commitment"},
        "incompatible_subtopics": {
            "mindful_breathing_only": {"breathing", "breathe", "breaths", "screen", "posture", "inhale", "exhale", "mindful breathing"},
        },
    },
    "renewable_clean_energy": {
        "triggers": {"renewable", "renewables", "forgiveness", "clean energy", "solar", "wind", "fossil", "electricity grid"},
        "anchors": {"renewable", "renewables", "clean energy", "energy", "transition", "power", "solar", "wind", "fossil", "emissions", "carbon", "grid", "electricity", "generation", "sustainable power", "fuel", "fossil fuels"},
        "incompatible_subtopics": {
            "river_litter_waste": {"litter", "rivers", "river", "plastic", "trash", "clean water", "picking up litter", "waterways"},
        },
    },
    "hope_peace_resilience": {
        "triggers": {"hope", "anchor", "drift"},
        "anchors": {"hope", "anchor", "drift", "peace", "resilience", "possibility", "uncertainty", "conflict", "hold onto", "stability", "grounded", "compassion", "harmony", "optimism", "encouragement", "steadfast"},
    },
    "girls_daughters_empowerment": {
        "triggers": {"daughters", "daughter", "girls", "girl"},
        "anchors": {"daughters", "daughter", "girl", "girls", "women", "empowerment", "education", "schooling", "future", "generations", "leadership", "unbreakable", "investing in girls"},
    },
    "books_reading_literacy": {
        "triggers": {"book", "books", "reading", "read", "library", "libraries", "borrow", "pages"},
        "anchors": {"book", "books", "reading", "read", "library", "libraries", "borrow", "pages", "literature", "stories", "empathy", "author", "curiosity", "literacy"},
    },
    "car_free_urban_spaces": {
        "triggers": {"car", "cars", "car-free", "carfree", "streets", "traffic", "pedestrian"},
        "anchors": {"car", "cars", "car-free", "carfree", "streets", "traffic", "pedestrian", "pedestrians", "sidewalk", "walkable", "neighbour", "neighbors", "public space", "mobility"},
    },
    "refugee_displacement_dignity": {
        "triggers": {"refugee", "refugees", "border", "borders", "stateless", "passport", "asylum", "fleeing", "displaced"},
        "anchors": {"refugee", "refugees", "border", "borders", "stateless", "passport", "asylum", "fleeing", "displacement", "displaced", "dignity", "migrant", "migrants", "homeland", "refugee rights"},
    },
    "transparency_open_governance": {
        "triggers": {"transparency", "right to know", "whistleblower", "public records", "disclosure", "information access"},
        "anchors": {"transparency", "right to know", "informed", "records", "openness", "accountability", "governance", "public trust", "information", "freedom of information"},
    },
}

# Semantic domain taxonomies for topic consistency validation
SEMANTIC_DOMAINS: dict[str, set[str]] = {
    "refugees_migration": {
        "refugee", "refugees", "asylum", "displacement", "displaced",
        "migrant", "migrants", "migration", "border", "borders", "stateless",
        "passport", "homeland", "exile", "fleeing", "crossborder", "cross-border",
        "refugeeawareness", "refugeerights", "migrationcrisis",
    },
    "women_gender_empowerment": {
        "woman", "women", "womens", "womans", "girl", "girls", "female",
        "mother", "mothers", "daughter", "daughters", "sister", "sisters",
        "gender", "matriarch", "patriarchy", "womenempowerment", "womeninleadership",
        "genderequity", "equalvoices", "genderequality", "womenlead", "womeninstem",
        "equalpay", "femaleempowerment",
    },
    "climate_environment_nature": {
        "climate", "environment", "environmental", "planet", "earth", "nature",
        "tree", "trees", "forest", "forests", "water", "ocean", "oceans",
        "river", "rivers", "carbon", "emissions", "waste", "plastic", "recycling",
        "soil", "biodiversity", "wildlife", "ecosystem", "ozone", "pollution",
        "sustainable", "sustainability", "conservation", "sapling", "eco",
        "climatecare", "ecoawareness", "savewater", "cleanair", "greenplanet",
        "globalwarming", "renewable", "wetland", "wetlands",
    },
    "mental_health_mindfulness": {
        "mental", "mindfulness", "mindful", "inner", "stillness", "calm",
        "anxiety", "stress", "meditation", "meditate", "breathe", "breathing",
        "breath", "breaths", "pause",
        "burnout", "depression", "emotional", "selfcare", "mentalhealth",
        "selfcompassion", "dailycalm", "mentalpeace", "wellbeing", "well-being",
        "healing",
    },
    "quality_education_literacy": {
        "education", "educate", "educated", "educating", "school", "schools",
        "classroom", "teacher", "teachers", "student", "students", "literacy",
        "illiteracy", "book", "books", "curriculum", "textbook", "curiosity",
        "scholarship", "library", "libraries", "teach", "teaching", "learn",
        "learning", "learner", "learners", "knowledge", "reading", "read",
        "lifelonglearning", "shareknowledge", "qualityeducation",
    },
    "peace_justice_humanity": {
        "peace", "peaceful", "justice", "unjust", "injustice", "harmony",
        "violence", "nonviolence", "war", "conflict", "reconciliation",
        "dialogue", "fairness", "dignity", "treaty", "treaties", "ceasefire",
        "peaceandjustice", "humandignity", "communitydialogue", "ethicalharmony",
    },
    "democracy_civic_rights": {
        "democracy", "democratic", "vote", "voting", "voter", "election",
        "elections", "ballot", "constitution", "republic", "citizen", "citizens",
        "citizenship", "civic", "liberty", "civicduty", "civicawareness",
    },
    "civic_rights_transparency_information": {
        "transparency", "right to know", "righttoknow", "informed citizen", "informed citizens",
        "accountability", "public records", "disclosure", "information access", "freedom of information",
        "whistleblower", "open governance", "transparencyinleadership",
    },
    "health_wellness_nutrition": {
        "health", "healthy", "healthcare", "disease", "illness", "hospital",
        "doctor", "medical", "medicine", "nutrition", "hunger", "hungry",
        "malnutrition", "food", "sanitation", "hygiene", "wellness", "cure",
        "publichealth", "zerohunger", "healthforall", "worldhealthday",
    },
    "rural_development_opportunity": {
        "rural", "village", "villages", "villager", "villagers", "agrarian",
        "farming", "farmer", "farmers", "agriculture", "countryside", "remote areas",
        "rural communities", "urban-rural", "rural development",
    },
    "public_space_urban_mobility": {
        "streets", "street", "car", "cars", "car-free", "carfree", "traffic",
        "pedestrian", "pedestrians", "sidewalk", "sidewalks", "urban mobility",
        "public space", "public spaces", "strangers become neighbours",
    },
    "children_youth": {
        "child", "children", "childhood", "youth", "young", "kids",
        "nextgeneration", "parenting", "boyhood", "girlhood",
    },
    "culture_language_heritage": {
        "language", "indigenous", "culture", "cultural", "heritage",
        "tradition", "mothertongue", "folklore", "art", "arts",
    },
    "science_technology_discovery": {
        "science", "scientific", "scientist", "scientists", "discovery",
        "research", "experiment", "technology", "physics", "chemistry", "biology",
    },
}

# Theme to expected compatible semantic domains
THEME_EXPECTED_DOMAINS: dict[str, set[str]] = {
    "Women Empowerment": {"women_gender_empowerment"},
    "Climate & Environment": {"climate_environment_nature"},
    "Quality Education": {"quality_education_literacy"},
    "Health & Mindfulness": {"mental_health_mindfulness", "health_wellness_nutrition"},
    "Peace & Justice": {"peace_justice_humanity", "democracy_civic_rights", "refugees_migration"},
}

# Domains that indicate distinct specialization that cannot be substituted without cross-bridging
SPECIALIZED_DOMAINS: list[str] = [
    "refugees_migration",
    "women_gender_empowerment",
    "climate_environment_nature",
    "mental_health_mindfulness",
    "quality_education_literacy",
    "peace_justice_humanity",
    "democracy_civic_rights",
    "civic_rights_transparency_information",
    "health_wellness_nutrition",
    "rural_development_opportunity",
    "public_space_urban_mobility",
]

# Configurable similarity thresholds
DEFAULT_SIMILARITY_THRESHOLDS = {
    "quote": 0.65,
    "foundation_connection": 0.70,
    "cta": 0.65,
    "full_description": 0.75,
}


def detect_domain_scores(text: str) -> dict[str, int]:
    """Calculate domain keyword occurrence scores from normalized text, supporting phrases and hashtags."""
    if not text:
        return {}
    normalized = normalize_text(text)
    words = re.findall(r"[a-z0-9]+", normalized)
    word_set = set(words)
    scores: dict[str, int] = {}

    # Identify hashtag tokens specifically if present in raw text
    raw_hashtags = [normalize_text(tag) for tag in re.findall(r"#[A-Za-z0-9_]+", text)]

    for domain, keywords in SEMANTIC_DOMAINS.items():
        score = 0
        for kw in keywords:
            kw_clean = kw.lower().strip()
            if " " in kw_clean or "-" in kw_clean:
                kw_norm = normalize_text(kw_clean)
                if kw_norm and kw_norm in normalized:
                    score += 2
            else:
                # Count exact token matches in text
                score += sum(1 for w in words if w == kw_clean)
                # Count hashtag matches (e.g. #WomenEmpowerment -> womenempowerment contains women)
                for htag in raw_hashtags:
                    if htag != "socialeducation" and len(kw_clean) >= 4 and kw_clean in htag:
                        score += 1
        if score > 0:
            scores[domain] = score

    return scores


def get_primary_topic_label(text: str) -> str:
    """Identify human-readable topic label from text for reporting."""
    scores = detect_domain_scores(text)
    if not scores:
        return "General Social Education & Reflection"
    top_domain = max(scores.items(), key=lambda x: x[1])[0]
    return top_domain.replace("_", " ").title()


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



def extract_quote_anchors(quote: str) -> dict[str, Any]:
    """Extract lightweight semantic anchors and triggered concept clusters from a quote without heavy NLP."""
    norm = normalize_text(quote)
    words = re.findall(r"[a-z0-9]+", norm)
    significant_tokens = {w for w in words if len(w) >= 4 and w not in STOP_WORDS}

    triggered_clusters: list[str] = []
    cluster_anchors: set[str] = set()
    for cluster_name, cluster_data in QUOTE_SUBTOPIC_CLUSTERS.items():
        triggers = cluster_data.get("triggers", set())
        for trigger in triggers:
            if " " in trigger or "-" in trigger:
                if normalize_text(trigger) in norm:
                    triggered_clusters.append(cluster_name)
                    cluster_anchors.update(cluster_data.get("anchors", set()))
                    break
            elif trigger in words:
                triggered_clusters.append(cluster_name)
                cluster_anchors.update(cluster_data.get("anchors", set()))
                break

    return {
        "tokens": significant_tokens,
        "clusters": triggered_clusters,
        "cluster_anchors": cluster_anchors,
    }


def validate_explanation_quality(explanation: str, quote: str = "") -> list[str]:
    """Validate that the explanation is a meaningful 1-2 sentence interpretation of the quote."""
    errors: list[str] = []
    clean_expl = explanation.strip()
    if not clean_expl:
        errors.append("Explanation is empty or missing")
        return errors

    words = clean_expl.split()
    if len(words) < 4 or len(clean_expl) < 20:
        errors.append(
            f"Explanation is too short or a slogan ({len(words)} words, {len(clean_expl)} chars): '{clean_expl}'"
        )
        return errors

    norm_expl = normalize_text(clean_expl)
    for slogan in DISALLOWED_EXPLANATION_SLOGANS:
        norm_slogan = normalize_text(slogan)
        if norm_expl == norm_slogan or norm_expl.startswith(norm_slogan + " "):
            if len(words) <= 7:
                errors.append(f"Explanation is a generic slogan or CTA without interpretation: '{clean_expl}'")
                return errors

    return errors




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

        # Semantic topic consistency validation
        topic_errors = self.validate_topic_consistency(content, theme, event)
        errors.extend(topic_errors)

        # Quote-level semantic alignment validation
        quote_alignment_errors = self.validate_quote_alignment(content, theme, event)
        errors.extend(quote_alignment_errors)

        # Event name relevance validation
        event_name_errors = self.validate_event_name_relevance(
            content.get("event_name", ""), content, theme, event
        )
        errors.extend(event_name_errors)

        return errors

    def validate_event_name_relevance(
        self,
        event_name: str,
        content: dict[str, Any],
        theme: str = "",
        event: dict | None = None,
    ) -> list[str]:
        """Validate that event_name is relevant to the content and does not conflict with the post topic."""
        errors: list[str] = []
        clean_ev_name = str(event_name).strip() if event_name else ""

        # 1. If today is an authoritative Foundation Event day
        if event and event.get("event"):
            expected_name = str(event["event"]).strip()
            if clean_ev_name and normalize_text(clean_ev_name) != normalize_text(expected_name):
                errors.append(
                    f"Foundation Event name mismatch: Expected '{expected_name}' from events.json but got '{clean_ev_name}'"
                )
            return errors

        # 2. If General Awareness or empty, always valid
        if not clean_ev_name or normalize_text(clean_ev_name) == "general awareness":
            return errors

        # 3. Check for topic conflict between event_name and quote / content
        quote = str(content.get("quote", "")).strip()
        explanation = str(content.get("explanation", "")).strip()
        context = str(content.get("context", "")).strip()
        quote_text = f"{quote} {explanation}"
        full_content_text = f"{quote} {explanation} {context}"

        ev_domains = detect_domain_scores(clean_ev_name)
        q_domains = detect_domain_scores(quote_text)
        content_domains = detect_domain_scores(full_content_text)

        specialized_ev = {d: s for d, s in ev_domains.items() if d in SPECIALIZED_DOMAINS and s >= 1}
        specialized_q = {d: s for d, s in q_domains.items() if d in SPECIALIZED_DOMAINS and s >= 1}

        if specialized_ev and specialized_q:
            top_ev_dom = max(specialized_ev.items(), key=lambda x: x[1])[0]
            top_q_dom = max(specialized_q.items(), key=lambda x: x[1])[0]

            # If event domain completely differs from quote domain and has zero support in full content
            if (
                top_ev_dom != top_q_dom
                and content_domains.get(top_ev_dom, 0) == 0
                and q_domains.get(top_ev_dom, 0) == 0
            ):
                ev_label = top_ev_dom.replace("_", " ").title()
                q_label = top_q_dom.replace("_", " ").title()
                errors.append(
                    f"Event Name topic mismatch: Event Name '{clean_ev_name}' ({ev_label}) is unrelated to Quote topic '{q_label}'"
                )

        # 4. Check specific keyword conflicts
        ev_lower = clean_ev_name.lower()
        content_lower = full_content_text.lower()
        if "forest" in ev_lower and not any(w in content_lower for w in ["forest", "tree", "trees", "woodland", "nature", "green", "canopy"]):
            errors.append(f"Event Name '{clean_ev_name}' refers to forests, but content does not discuss forests or trees")
        elif "girl" in ev_lower and not any(w in content_lower for w in ["girl", "daughter", "female", "gender", "she", "her", "women"]):
            errors.append(f"Event Name '{clean_ev_name}' refers to girl child, but content does not discuss girls or gender equality")
        elif "ocean" in ev_lower and not any(w in content_lower for w in ["ocean", "marine", "sea", "coral", "water", "plastic"]):
            errors.append(f"Event Name '{clean_ev_name}' refers to oceans, but content does not discuss marine/water topics")

        return errors

    def validate_quote_alignment(
        self,
        content: dict[str, Any],
        theme: str = "",
        event: dict | None = None,
    ) -> list[str]:
        """Validate quote-level meaning grounding between the quote and its explanation & description."""
        errors: list[str] = []
        quote = str(content.get("quote", "")).strip()
        explanation = str(content.get("explanation", "")).strip()
        context = str(content.get("context", "")).strip()
        foundation_conn = str(content.get("foundation_connection", "")).strip()
        cta = str(content.get("cta", "")).strip()

        # 1. Check explanation quality
        expl_errors = validate_explanation_quality(explanation, quote)
        errors.extend(expl_errors)

        if not quote:
            return errors

        anchors = extract_quote_anchors(quote)
        norm_desc = normalize_text(f"{context} {foundation_conn} {cta}")
        desc_words = set(re.findall(r"[a-z0-9]+", norm_desc))

        # 2. Check triggered subtopic clusters for sub-topic divergence / incompatible topics
        for cluster_name in anchors["clusters"]:
            cluster_data = QUOTE_SUBTOPIC_CLUSTERS.get(cluster_name, {})
            incompatible = cluster_data.get("incompatible_subtopics", {})
            for incomp_name, incomp_terms in incompatible.items():
                incomp_matched = []
                for term in incomp_terms:
                    term_clean = term.lower().strip()
                    if " " in term_clean or "-" in term_clean:
                        if normalize_text(term_clean) in norm_desc:
                            incomp_matched.append(term_clean)
                    elif term_clean in desc_words:
                        incomp_matched.append(term_clean)

                if incomp_matched:
                    # Check if description actually addresses the core quote anchor concepts
                    expected_anchors = cluster_data.get("anchors", set())
                    has_anchor_support = any(
                        (normalize_text(a) in norm_desc if (" " in a or "-" in a) else a in desc_words)
                        for a in expected_anchors
                        if a not in incomp_terms
                    )
                    if not has_anchor_support:
                        q_topic_clean = cluster_name.replace("_", " ")
                        inc_topic_clean = incomp_name.replace("_", " ")
                        errors.append(
                            f"Quote-level semantic mismatch: Quote is specifically about '{q_topic_clean}' but description focuses on '{inc_topic_clean}' instead of explaining the quote's central idea"
                        )

        return errors


    def validate_theme_compatibility(
        self,
        quote_text: str,
        theme: str,
        event: dict | None = None,
    ) -> list[str]:
        """Verify that the quote is semantically compatible with the configured theme."""
        errors: list[str] = []
        if event and event.get("event"):
            # When event is active, EVENT > THEME (event compatibility takes precedence)
            return errors

        expected_domains = THEME_EXPECTED_DOMAINS.get(theme)
        if not expected_domains:
            return errors

        quote_domains = detect_domain_scores(quote_text)
        if not quote_domains:
            return errors

        # Has at least one match in expected domains?
        has_expected_domain = any(dom in expected_domains for dom in quote_domains)

        # Detect top dominant domain in quote
        top_quote_domain = max(quote_domains.items(), key=lambda x: x[1])[0]

        if not has_expected_domain and top_quote_domain in SPECIALIZED_DOMAINS:
            top_label = top_quote_domain.replace("_", " ").title()
            errors.append(
                f"Theme compatibility mismatch: Theme is '{theme}' but quote is about '{top_label}'"
            )

        return errors

    def validate_event_compatibility(
        self,
        quote_text: str,
        event: dict | None = None,
    ) -> list[str]:
        """Verify that the quote is semantically relevant to the active calendar event."""
        errors: list[str] = []
        if not event or not event.get("event"):
            return errors

        event_name = event["event"]
        event_domains = detect_domain_scores(event_name)
        quote_domains = detect_domain_scores(quote_text)

        # If event maps to known semantic domains
        if event_domains:
            top_event_domain = max(event_domains.items(), key=lambda x: x[1])[0]
            if top_event_domain in SPECIALIZED_DOMAINS:
                # Check if quote has zero tokens of the event domain and is dominated by another domain
                if quote_domains:
                    top_quote_domain = max(quote_domains.items(), key=lambda x: x[1])[0]
                    if (
                        top_quote_domain in SPECIALIZED_DOMAINS
                        and top_quote_domain != top_event_domain
                        and quote_domains.get(top_event_domain, 0) == 0
                    ):
                        ev_label = top_event_domain.replace("_", " ").title()
                        q_label = top_quote_domain.replace("_", " ").title()
                        errors.append(
                            f"Event relevance mismatch: Event is '{event_name}' ({ev_label}) but quote is about '{q_label}'"
                        )

        return errors

    def validate_topic_consistency(
        self,
        content: dict[str, Any],
        theme: str,
        event: dict | None = None,
    ) -> list[str]:
        """Validate that all content fields share the same semantic topic and do not diverge."""
        errors: list[str] = []
        quote = str(content.get("quote", "")).strip()
        explanation = str(content.get("explanation", "")).strip()
        context = str(content.get("context", "")).strip()
        foundation_conn = str(content.get("foundation_connection", "")).strip()
        cta = str(content.get("cta", "")).strip()
        hashtags = content.get("hashtags", [])
        tag_text = " ".join(hashtags) if isinstance(hashtags, list) else str(hashtags)

        quote_text = f"{quote} {explanation}"

        # 1. Event compatibility check (EVENT > THEME)
        event_errors = self.validate_event_compatibility(quote_text, event)
        errors.extend(event_errors)

        # 2. Theme compatibility check (when no event is active)
        theme_errors = self.validate_theme_compatibility(quote_text, theme, event)
        errors.extend(theme_errors)

        # 3. Detect domain signals in Quote + Explanation
        quote_domains = detect_domain_scores(quote_text)

        # 4. Detect domain signals in Description (context + foundation_connection + cta)
        desc_text = f"{context} {foundation_conn} {cta}"
        desc_domains = detect_domain_scores(desc_text)

        # 5. Detect domain signals in Hashtags
        tag_domains = detect_domain_scores(tag_text)

        # Find dominant specialized domains in Quote
        specialized_q_scores = {d: s for d, s in quote_domains.items() if d in SPECIALIZED_DOMAINS and s >= 1}
        specialized_d_scores = {d: s for d, s in desc_domains.items() if d in SPECIALIZED_DOMAINS and s >= 1}
        specialized_t_scores = {d: s for d, s in tag_domains.items() if d in SPECIALIZED_DOMAINS and s >= 1}

        # Check for Quote vs Description topic divergence
        if specialized_q_scores and specialized_d_scores:
            top_q_dom = max(specialized_q_scores.items(), key=lambda x: x[1])[0]
            top_d_dom = max(specialized_d_scores.items(), key=lambda x: x[1])[0]

            # If top quote domain and top description domain are different and share no cross-domain grounding
            if (
                top_q_dom != top_d_dom
                and desc_domains.get(top_q_dom, 0) == 0
                and quote_domains.get(top_d_dom, 0) == 0
                and specialized_d_scores[top_d_dom] >= 1
            ):
                q_label = top_q_dom.replace("_", " ").title()
                d_label = top_d_dom.replace("_", " ").title()
                errors.append(
                    f"Semantic topic mismatch: Quote is about '{q_label}' but description discusses '{d_label}'"
                )

        # Check for Quote vs Hashtags topic divergence
        if specialized_q_scores and specialized_t_scores:
            top_q_dom = max(specialized_q_scores.items(), key=lambda x: x[1])[0]
            top_t_dom = max(specialized_t_scores.items(), key=lambda x: x[1])[0]

            if (
                top_q_dom != top_t_dom
                and tag_domains.get(top_q_dom, 0) == 0
                and quote_domains.get(top_t_dom, 0) == 0
                and specialized_t_scores[top_t_dom] >= 1
            ):
                q_label = top_q_dom.replace("_", " ").title()
                t_label = top_t_dom.replace("_", " ").title()
                errors.append(
                    f"Hashtag topic mismatch: Hashtags contain '{t_label}' tags unrelated to Quote topic '{q_label}'"
                )

        # Check for Event day topic mismatch (event vs description)
        if event and event.get("event"):
            event_name = event["event"]
            event_domains = detect_domain_scores(event_name)
            specialized_ev_scores = {d: s for d, s in event_domains.items() if d in SPECIALIZED_DOMAINS and s >= 1}
            if specialized_ev_scores and specialized_d_scores:
                top_ev_dom = max(specialized_ev_scores.items(), key=lambda x: x[1])[0]
                top_d_dom = max(specialized_d_scores.items(), key=lambda x: x[1])[0]
                if (
                    top_ev_dom != top_d_dom
                    and desc_domains.get(top_ev_dom, 0) == 0
                    and quote_domains.get(top_d_dom, 0) == 0
                ):
                    ev_label = top_ev_dom.replace("_", " ").title()
                    d_label = top_d_dom.replace("_", " ").title()
                    errors.append(
                        f"Event topic mismatch: Event is about '{event_name}' ({ev_label}) but description discusses '{d_label}'"
                    )

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
