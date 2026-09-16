"""Authoritative, repository-grounded Jalte Diye Foundation context.

This module provides verified mission, goals, and focus areas extracted
strictly from project documentation (README.md, SRS.md, ARCHITECTURE.md).
It includes strict guardrails against fabricating unsupported NGO claims.
"""

from __future__ import annotations

FOUNDATION_CONTEXT = {
    "name": "Jalte Diye Foundation",
    "tagline": "Cognitive Agentic AI & Social Education for Social Good",
    "mission": (
        "Promote social awareness, ethical development, community engagement, "
        "human values, and holistic social education through accessible, "
        "thought-provoking daily reflections and learning."
    ),
    "core_vision": (
        "Explore how ethical, human-centered AI can create and deliver content "
        "that supports learning, empathy, responsible citizenship, and positive "
        "social impact."
    ),
    "goals": [
        "Inspire responsible citizenship, empathy, and constructive social awareness.",
        "Foster community dialogue around sustainability, quality education, equality, peace, justice, and mindfulness.",
        "Maintain human-centered values, transparency, and responsible AI practices in education.",
        "Deliver daily educational reflections that bridge awareness and daily personal action.",
    ],
    "focus_areas": [
        "Social Education & Ethical Living",
        "Quality Education & Lifelong Learning",
        "Peace, Justice & Human Dignity",
        "Climate Action, Environmental Stewardship & Sustainability",
        "Health, Mental Well-being & Mindfulness",
        "Equality, Inclusion & Women Empowerment",
        "Cultural Heritage, National Observances & Community Celebrations",
    ],
    "verified_work": [
        "Daily automated social education and awareness publishing via Cogentic AI.",
        "Digital content delivery for the Jalte Diye Foundation educational initiatives.",
        "Curated daily thought leadership on ethics, empathy, and social responsibility.",
    ],
    "unsupported_claim_prohibitions": [
        "Do not claim specific physical donation amounts or financial statistics.",
        "Do not invent physical charity branches, shelters, schools, or clinics.",
        "Do not invent unverified beneficiary counts (e.g., 'we fed 10,000 children').",
        "Do not invent unverified partnerships with specific corporations or government bodies.",
        "Keep the focus on social education, awareness, empathy, values, community reflection, and individual responsibility.",
    ],
}


def get_foundation_prompt_context() -> str:
    """Format the foundation context for injection into Gemini prompts."""
    goals_bulleted = "\n".join(f"- {g}" for g in FOUNDATION_CONTEXT["goals"])
    focus_bulleted = "\n".join(f"- {f}" for f in FOUNDATION_CONTEXT["focus_areas"])
    verified_bulleted = "\n".join(f"- {w}" for w in FOUNDATION_CONTEXT["verified_work"])
    prohibitions_bulleted = "\n".join(f"- {p}" for p in FOUNDATION_CONTEXT["unsupported_claim_prohibitions"])

    return f"""
Jalte Diye Foundation Authoritative Context:
Name: {FOUNDATION_CONTEXT["name"]}
Mission: {FOUNDATION_CONTEXT["mission"]}
Core Vision: {FOUNDATION_CONTEXT["core_vision"]}

Core Goals:
{goals_bulleted}

Focus Areas:
{focus_bulleted}

Verified Work:
{verified_bulleted}

STRICT Content Guardrails (DO NOT VIOLATE):
{prohibitions_bulleted}
"""
