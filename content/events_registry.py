"""Event discovery and awareness calendar registry for Cogentic AI.

Implements the event-discovery-first architecture:
1. Priority 1: Existing Foundation Event from events.json
2. Priority 2: Recognized Awareness Day matching (Date Match + Theme Relevance)
3. Priority 3: No Relevant Event -> "General Awareness"
"""

from __future__ import annotations

import json
import logging
import os
from dataclasses import dataclass, field
from datetime import date
from typing import Any

logger = logging.getLogger(__name__)


@dataclass(frozen=True)
class AwarenessEvent:
    """Data structure for a recognized awareness/event day."""

    name: str
    date_mmdd: str
    relevant_themes: tuple[str, ...]
    keywords: tuple[str, ...] = ()
    description: str = ""
    subtopic_cluster: str = ""


# Comprehensive registry of recognized international & national awareness days
AWARENESS_EVENTS_REGISTRY: list[AwarenessEvent] = [
    # --- Health & Mindfulness ---
    AwarenessEvent(
        name="World Heart Day",
        date_mmdd="09-29",
        relevant_themes=("Health & Mindfulness",),
        keywords=(
            "heart",
            "cardiovascular",
            "cardiac",
            "artery",
            "pulse",
            "blood pressure",
            "heartbeat",
            "circulation",
            "healthy heart",
            "cholesterol",
        ),
        description="Focuses on cardiovascular health, heart disease prevention, and daily heart care.",
        subtopic_cluster="cardiovascular_heart_health",
    ),
    AwarenessEvent(
        name="World Mental Health Day",
        date_mmdd="10-10",
        relevant_themes=("Health & Mindfulness",),
        keywords=(
            "mental health",
            "mindfulness",
            "inner stillness",
            "emotional balance",
            "therapy",
            "mental calm",
            "stress relief",
            "psychological",
            "well-being",
        ),
        description="Raises global awareness of mental health issues and emotional well-being.",
        subtopic_cluster="mental_health_mindfulness",
    ),
    AwarenessEvent(
        name="World Health Day",
        date_mmdd="04-07",
        relevant_themes=("Health & Mindfulness",),
        keywords=(
            "health",
            "wellness",
            "healthcare",
            "well-being",
            "healthy body",
            "vitality",
            "prevention",
        ),
        description="Marks the founding of the WHO and promotes universal access to health and wellness.",
        subtopic_cluster="mental_health_mindfulness",
    ),
    AwarenessEvent(
        name="International Day of Yoga",
        date_mmdd="06-21",
        relevant_themes=("Health & Mindfulness",),
        keywords=(
            "yoga",
            "mindfulness",
            "asana",
            "meditation",
            "breath",
            "pranayama",
            "inner balance",
            "harmony",
        ),
        description="Promotes yoga and mindful physical harmony for physical and mental health.",
        subtopic_cluster="mental_health_mindfulness",
    ),
    AwarenessEvent(
        name="World Diabetes Day",
        date_mmdd="11-14",
        relevant_themes=("Health & Mindfulness",),
        keywords=(
            "diabetes",
            "blood sugar",
            "metabolic",
            "insulin",
            "nutrition",
            "healthy living",
            "active lifestyle",
        ),
        description="Focuses on diabetes management, healthy diets, and active daily habits.",
        subtopic_cluster="mental_health_mindfulness",
    ),
    # --- Women Empowerment ---
    AwarenessEvent(
        name="International Women's Day",
        date_mmdd="03-08",
        relevant_themes=("Women Empowerment",),
        keywords=(
            "women",
            "gender equality",
            "female",
            "women rights",
            "empower women",
            "break the bias",
            "equal opportunity",
        ),
        description="Celebrates women's achievements and advocates for gender equality worldwide.",
        subtopic_cluster="women_gender_empowerment",
    ),
    AwarenessEvent(
        name="International Day of the Girl Child",
        date_mmdd="10-11",
        relevant_themes=("Women Empowerment", "Quality Education"),
        keywords=(
            "girl child",
            "girls education",
            "daughters",
            "empower girls",
            "girls rights",
            "educate daughters",
        ),
        description="Focuses on the empowerment and education of girls globally.",
        subtopic_cluster="women_gender_empowerment",
    ),
    AwarenessEvent(
        name="National Daughter's Day",
        date_mmdd="09-27",
        relevant_themes=("Women Empowerment",),
        keywords=(
            "daughter",
            "daughters",
            "daughters day",
            "girl child",
            "cherish daughters",
            "empowering daughters",
        ),
        description="Celebrates the love, dignity, and empowerment of daughters.",
        subtopic_cluster="women_gender_empowerment",
    ),
    AwarenessEvent(
        name="International Day of Women and Girls in Science",
        date_mmdd="02-11",
        relevant_themes=("Women Empowerment", "Quality Education"),
        keywords=(
            "women in science",
            "stem",
            "girls in science",
            "scientific research",
            "female researchers",
        ),
        description="Promotes full and equal access for women and girls in science and technology.",
        subtopic_cluster="women_gender_empowerment",
    ),
    AwarenessEvent(
        name="International Day for the Elimination of Violence against Women",
        date_mmdd="11-25",
        relevant_themes=("Women Empowerment", "Peace & Justice"),
        keywords=(
            "safety for women",
            "end violence",
            "gender justice",
            "dignity of women",
            "safe spaces",
        ),
        description="Raises awareness against gender-based violence and promotes safety and dignity.",
        subtopic_cluster="women_gender_empowerment",
    ),
    # --- Quality Education ---
    AwarenessEvent(
        name="International Literacy Day",
        date_mmdd="09-08",
        relevant_themes=("Quality Education",),
        keywords=(
            "literacy",
            "reading",
            "books",
            "learn to read",
            "foundational learning",
            "knowledge",
        ),
        description="Highlights the importance of literacy as a matter of dignity and human rights.",
        subtopic_cluster="quality_education_literacy",
    ),
    AwarenessEvent(
        name="World Teachers' Day",
        date_mmdd="10-05",
        relevant_themes=("Quality Education",),
        keywords=(
            "teachers",
            "educators",
            "mentors",
            "teaching",
            "guiding minds",
            "gratitude to teachers",
        ),
        description="Honors teachers and their contribution to youth development and education.",
        subtopic_cluster="quality_education_literacy",
    ),
    AwarenessEvent(
        name="Teacher's Day",
        date_mmdd="09-05",
        relevant_themes=("Quality Education",),
        keywords=(
            "teachers",
            "mentors",
            "gurus",
            "educators",
            "lighting a fire",
            "learning",
        ),
        description="Celebrates teachers, mentors, and educators in India and globally.",
        subtopic_cluster="quality_education_literacy",
    ),
    AwarenessEvent(
        name="International Day of Education",
        date_mmdd="01-24",
        relevant_themes=("Quality Education",),
        keywords=(
            "education",
            "learning for all",
            "schooling",
            "inclusive education",
            "empowering minds",
        ),
        description="Celebrates the role of education for peace and development.",
        subtopic_cluster="quality_education_literacy",
    ),
    AwarenessEvent(
        name="World Book and Copyright Day",
        date_mmdd="04-23",
        relevant_themes=("Quality Education",),
        keywords=(
            "books",
            "reading",
            "literature",
            "authors",
            "open a book",
            "library",
        ),
        description="Promotes the joy of reading and respect for knowledge and literature.",
        subtopic_cluster="quality_education_literacy",
    ),
    # --- Climate & Environment ---
    AwarenessEvent(
        name="World Environment Day",
        date_mmdd="06-05",
        relevant_themes=("Climate & Environment",),
        keywords=(
            "environment",
            "nature",
            "ecosystem",
            "planet earth",
            "sustainability",
            "conservation",
            "green habits",
        ),
        description="Encourages worldwide awareness and action for the protection of the environment.",
        subtopic_cluster="climate_environment_nature",
    ),
    AwarenessEvent(
        name="Earth Day",
        date_mmdd="04-22",
        relevant_themes=("Climate & Environment",),
        keywords=(
            "earth",
            "mother earth",
            "planet",
            "protecting nature",
            "ecological balance",
            "climate action",
        ),
        description="Demonstrates support for environmental protection and planetary preservation.",
        subtopic_cluster="climate_environment_nature",
    ),
    AwarenessEvent(
        name="World Ozone Day",
        date_mmdd="09-16",
        relevant_themes=("Climate & Environment",),
        keywords=(
            "ozone layer",
            "atmosphere",
            "climate",
            "protecting the sky",
            "clean air",
            "environmental protection",
        ),
        description="Commemorates the preservation of the ozone layer and climate action.",
        subtopic_cluster="climate_environment_nature",
    ),
    AwarenessEvent(
        name="World Environmental Health Day",
        date_mmdd="09-26",
        relevant_themes=("Climate & Environment", "Health & Mindfulness"),
        keywords=(
            "environmental health",
            "clean air",
            "clean water",
            "healthy surroundings",
            "eco-health",
        ),
        description="Focuses on the link between a healthy environment and human wellness.",
        subtopic_cluster="climate_environment_nature",
    ),
    AwarenessEvent(
        name="World Nature Conservation Day",
        date_mmdd="07-28",
        relevant_themes=("Climate & Environment",),
        keywords=(
            "nature conservation",
            "protect forests",
            "water conservation",
            "wildlife",
            "natural resources",
        ),
        description="Acknowledges that a healthy environment is foundation for a stable society.",
        subtopic_cluster="climate_environment_nature",
    ),
    # --- Peace & Justice ---
    AwarenessEvent(
        name="International Day of Peace",
        date_mmdd="09-21",
        relevant_themes=("Peace & Justice", "Foundation Events"),
        keywords=(
            "peace",
            "non-violence",
            "harmony",
            "reconciliation",
            "justice",
            "truce",
            "compassion",
        ),
        description="Dedicated to world peace, ceasing hostilities, and spreading non-violence.",
        subtopic_cluster="peace_nonviolence_justice",
    ),
    AwarenessEvent(
        name="International Day of Non-Violence",
        date_mmdd="10-02",
        relevant_themes=("Peace & Justice", "Foundation Events"),
        keywords=(
            "non-violence",
            "gandhi jayanti",
            "peace",
            "ahimsa",
            "truth",
            "justice",
            "harmony",
        ),
        description="Commemorates the birthday of Mahatma Gandhi and spreads the message of non-violence.",
        subtopic_cluster="peace_nonviolence_justice",
    ),
    AwarenessEvent(
        name="Human Rights Day",
        date_mmdd="12-10",
        relevant_themes=("Peace & Justice",),
        keywords=(
            "human rights",
            "dignity",
            "equality",
            "justice for all",
            "shared humanity",
            "freedom",
        ),
        description="Commemorates the Universal Declaration of Human Rights.",
        subtopic_cluster="human_dignity_rights",
    ),
    AwarenessEvent(
        name="World Day of Social Justice",
        date_mmdd="02-20",
        relevant_themes=("Peace & Justice", "Foundation Events"),
        keywords=(
            "social justice",
            "equal rights",
            "fairness",
            "dignity",
            "opportunity",
            "inclusion",
        ),
        description="Promotes social justice, poverty eradication, and fair treatment for all.",
        subtopic_cluster="human_dignity_rights",
    ),
    AwarenessEvent(
        name="World Refugee Day",
        date_mmdd="06-20",
        relevant_themes=("Peace & Justice",),
        keywords=(
            "refugees",
            "displacement",
            "shared humanity",
            "dignity",
            "shelter",
            "compassion",
        ),
        description="Honors the courage and resilience of people forced to flee their homelands.",
        subtopic_cluster="refugees_migration",
    ),
]


def load_foundation_events(project_root: str) -> dict[str, Any]:
    """Load Foundation Events from events.json."""
    events_file = os.path.join(project_root, "events.json")
    if not os.path.exists(events_file):
        return {}
    try:
        with open(events_file, "r", encoding="utf-8") as f:
            return json.load(f)
    except Exception as exc:
        logger.error("Failed to load events.json from %s: %s", events_file, exc)
        return {}


def get_awareness_events_for_date(target_date: date) -> list[AwarenessEvent]:
    """Find all recognized awareness events occurring strictly on the given calendar date."""
    target_mmdd = target_date.strftime("%m-%d")
    return [ev for ev in AWARENESS_EVENTS_REGISTRY if ev.date_mmdd == target_mmdd]


def find_matching_awareness_event(
    target_date: date,
    theme: str,
) -> AwarenessEvent | None:
    """Check if target_date has a recognized awareness event matching the selected theme.

    Strict Constraints:
    1. Date Match: Event MUST occur on target_date (MM-DD).
    2. Theme Relevance: The event's relevant_themes MUST include the selected theme.
    """
    target_mmdd = target_date.strftime("%m-%d")
    events_on_date = [ev for ev in AWARENESS_EVENTS_REGISTRY if ev.date_mmdd == target_mmdd]

    for ev in events_on_date:
        if theme in ev.relevant_themes:
            return ev
    return None


def resolve_event_and_theme_for_date(
    target_date: date,
    project_root: str,
    selected_theme: str | None = None,
) -> tuple[str, dict[str, Any] | None, str]:
    """Determine the theme, event context dict, and event_name for a given target date.

    Implements the 3-tier priority sequence:
    Priority 1: Foundation Event from events.json
      -> Theme: "Foundation Events" (or configured theme in events.json)
      -> Event Dict: Foundation Event metadata
      -> Event Name: Exact event name from events.json

    Priority 2: Recognized Awareness Day matching (Date Match + Theme Relevance)
      -> Theme: Selected Theme
      -> Event Dict: Awareness Event metadata
      -> Event Name: Exact Awareness Event Name (e.g. "World Heart Day")

    Priority 3: No Relevant Event
      -> Theme: Selected Theme
      -> Event Dict: None
      -> Event Name: "General Awareness"

    Returns:
        (theme, event_dict, event_name)
    """
    target_mmdd = target_date.strftime("%m-%d")
    foundation_events = load_foundation_events(project_root)

    # Priority 1: Foundation Event
    if target_mmdd in foundation_events:
        f_entry = foundation_events[target_mmdd]
        event_name = f_entry.get("event", "").strip()
        theme = f_entry.get("theme", "Foundation Events")
        event_dict = {
            "event": event_name,
            "theme": theme,
            "csv_row": f_entry.get("csv_row", event_name),
            "is_foundation_event": True,
            "is_awareness_day": False,
        }
        logger.info("Found Priority 1 Foundation Event for %s: %s (Theme: %s)", target_mmdd, event_name, theme)
        return theme, event_dict, event_name

    # If no theme was provided, this function assumes theme selection will be resolved by caller
    if not selected_theme:
        return "", None, "General Awareness"

    # Priority 2: Recognized Awareness Day for target_date + selected_theme
    awareness_event = find_matching_awareness_event(target_date, selected_theme)
    if awareness_event:
        event_name = awareness_event.name
        event_dict = {
            "event": event_name,
            "theme": selected_theme,
            "keywords": list(awareness_event.keywords),
            "description": awareness_event.description,
            "subtopic_cluster": awareness_event.subtopic_cluster,
            "is_foundation_event": False,
            "is_awareness_day": True,
        }
        logger.info(
            "Found Priority 2 Awareness Event for %s with Theme '%s': %s",
            target_mmdd,
            selected_theme,
            event_name,
        )
        return selected_theme, event_dict, event_name

    # Priority 3: No Relevant Event
    logger.info("No relevant event for %s with Theme '%s' -> General Awareness", target_mmdd, selected_theme)
    return selected_theme, None, "General Awareness"

def get_event_for_date(date_str: str, project_root: str) -> dict[str, Any] | None:
    """Helper to retrieve registered foundation event for a date string (YYYY-MM-DD)."""
    try:
        from datetime import datetime
        dt = datetime.strptime(date_str, "%Y-%m-%d").date()
        _, ev_dict, _ = resolve_event_and_theme_for_date(dt, project_root)
        return ev_dict
    except Exception:
        return None
