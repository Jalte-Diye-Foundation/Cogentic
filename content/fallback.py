"""CSV fallback content and duplicate quote tracking."""

from __future__ import annotations

import csv
import logging
import os
from typing import Any

from content.generator import (
    build_social_caption,
    build_structured_long_explanation,
    sanitize_text,
)
from content.validator import THEME_EXPECTED_DOMAINS, detect_domain_scores

logger = logging.getLogger(__name__)

# Topic-specific synthesis templates for fallback scenarios to ensure semantic consistency and variation
TOPIC_FALLBACK_TEMPLATES: dict[str, list[dict[str, Any]]] = {
    "Foundation Events": [
        {
            "context": "Observing International Day of Older Persons reminds us to honor the wisdom, resilience, and lifelong contributions of older persons in our communities.",
            "foundation_connection": "At Jalte Diye Foundation, our social education values intergenerational respect and learning from the life experiences of our elders.",
            "cta": "Spend time today having a conversation with an older person and listen to their life story.",
            "hashtags": ["#InternationalDayofOlderPersons", "#IntergenerationalWisdom", "#RespectElders", "#CommunityCare"],
        },
        {
            "context": "Special calendar observances bring communities together to pause, reflect, and celebrate values that enrich our collective humanity.",
            "foundation_connection": "Jalte Diye Foundation observes these occasions to foster community connection, empathy, and shared learning across all generations.",
            "cta": "Take a moment today to learn about today's observance and share an inspiring takeaway with a friend.",
            "hashtags": ["#FoundationEvents", "#CommunityObservance", "#SharedValues", "#SocialEducation"],
        },
    ],
    "refugees_migration": [
        {
            "context": "When families are forced to leave home, remembering our common humanity bridges the divide between strangers and neighbors.",
            "foundation_connection": "For Jalte Diye Foundation, social education begins with recognizing equal human dignity in every person regardless of borders or displacement.",
            "cta": "Reach out with simple kindness or welcome someone new in your neighborhood today.",
            "hashtags": ["#HumanDignity", "#SharedHumanity", "#EmpathyInAction", "#PeaceAndJustice"],
        },
        {
            "context": "Displacement uproots lives, but it never diminishes the inherent worth and potential every human being brings with them.",
            "foundation_connection": "At Jalte Diye Foundation, our community initiatives focus on fostering welcoming spaces where every person feels seen, respected, and supported.",
            "cta": "Share a warm greeting or offer practical support to an immigrant or refugee family living nearby.",
            "hashtags": ["#RefugeeDignity", "#InclusiveCommunities", "#SharedBelonging", "#SocialEducation"],
        },
    ],
    "women_gender_empowerment": [
        {
            "context": "Every family and community thrives when women have the space to speak, make decisions, and lead without fear or artificial barriers.",
            "foundation_connection": "Promoting gender equity and mutual respect is a vital part of Jalte Diye Foundation's social education efforts. Real progress happens when women's ideas and voices are genuinely heard and supported.",
            "cta": "Make space today to support and encourage a woman's voice or idea in your workplace or family circle.",
            "hashtags": ["#WomenEmpowerment", "#EqualVoices", "#CommunityRespect", "#SocialEducation"],
        },
        {
            "context": "When girls and women access quality education and equal economic opportunities, the benefits ripple across entire generations.",
            "foundation_connection": "At Jalte Diye Foundation, our social initiatives break down barriers to learning, ensuring every girl and woman has the tools to achieve self-reliance.",
            "cta": "Mentor, recommend, or share an educational opportunity with a young woman in your community today.",
            "hashtags": ["#EqualOpportunities", "#GirlsEducation", "#EmpowerWomen", "#SocialEducation"],
        },
        {
            "context": "True dignity begins with dismantling outdated stereotypes and respecting the individual choices, agency, and aspirations of every woman.",
            "foundation_connection": "Social education at Jalte Diye Foundation centers on cultivating a culture of equal partnership and mutual dignity across all spheres of life.",
            "cta": "Speak up against a casual gender stereotype when you hear one in conversation today.",
            "hashtags": ["#GenderEquality", "#BreakTheBias", "#MutualRespect", "#SocialEducation"],
        },
    ],
    "climate_environment_nature": [
        {
            "context": "The choices we make in our daily routines—what we consume, what we throw away, and what we care for—shape the neighborhood our kids will grow up in.",
            "foundation_connection": "At Jalte Diye Foundation, our environmental focus is about practical everyday responsibility. Caring for the planet isn't an abstract theory; it's a series of small, thoughtful habits we practice together.",
            "cta": "Pick one small habit today to reduce waste—like carrying a reusable water bottle or cloth bag.",
            "hashtags": ["#ClimateCare", "#DailyHabits", "#EcoAwareness", "#JalteDiyeFoundation"],
        },
        {
            "context": "Nature operates in delicate balance, and preserving clean air, fertile soil, and thriving green spaces requires conscious stewardship from all of us.",
            "foundation_connection": "Our community work emphasizes environmental awareness through neighborhood tree planting, cleanups, and educating young minds about local ecology.",
            "cta": "Spend 15 minutes outdoors today and water a neighborhood plant or pick up litter in your local park.",
            "hashtags": ["#ProtectNature", "#GreenLiving", "#LocalEcology", "#CommunityAction"],
        },
        {
            "context": "Protecting our shared natural resources is not an optional task; it is the essential groundwork for healthy, sustainable communities.",
            "foundation_connection": "Jalte Diye Foundation promotes ecological literacy, helping citizens understand that preserving nature directly protects public health and well-being.",
            "cta": "Turn off unnecessary lights and appliances when leaving a room to conserve energy today.",
            "hashtags": ["#Sustainability", "#EcoLiteracy", "#ConserveEnergy", "#EarthStewardship"],
        },
    ],
    "quality_education_literacy": [
        {
            "context": "Education is the quiet spark that helps a child understand their worth, question the world, and build a meaningful future.",
            "foundation_connection": "At Jalte Diye Foundation, we believe learning should reach every doorstep. Our grassroots education programs work to ensure no child is left behind due to circumstance.",
            "cta": "Gift a book to a child or spend 20 minutes reading with someone in your family today.",
            "hashtags": ["#QualityEducation", "#EveryChildLearns", "#LiteracyForAll", "#GrassrootsEducation"],
        },
        {
            "context": "True learning extends far beyond textbooks; it nurtures curiosity, critical reasoning, and the courage to think independently.",
            "foundation_connection": "Our education initiatives encourage participatory learning and creative problem-solving so young learners become thoughtful, active citizens.",
            "cta": "Share an interesting educational article, documentary, or podcast with a friend or colleague today.",
            "hashtags": ["#LifelongLearning", "#Curiosity", "#ActiveCitizenship", "#SocialEducation"],
        },
        {
            "context": "Literacy is the foundational key that unlocks economic independence, personal agency, and informed civic participation.",
            "foundation_connection": "Jalte Diye Foundation supports community libraries and after-school support sessions to cultivate a deep love for reading among first-generation learners.",
            "cta": "Donate a gently used book to a local library, community center, or neighborhood school today.",
            "hashtags": ["#ReadToLead", "#CommunityLibrary", "#EmpowerThroughBooks", "#JalteDiyeFoundation"],
        },
    ],
    "peace_justice_humanity": [
        {
            "context": "Peace is not just the absence of conflict; it is the presence of fairness, mutual respect, and equal opportunities for everyone.",
            "foundation_connection": "At Jalte Diye Foundation, our peacebuilding efforts focus on constructive dialogue and bringing diverse community members together to solve shared problems.",
            "cta": "Practice patience in a difficult conversation today by actively listening before responding.",
            "hashtags": ["#PeaceAndJustice", "#MutualRespect", "#CommunityDialogue", "#SocialHarmony"],
        },
        {
            "context": "A just society is built when ordinary citizens choose empathy and stand up for fairness in their daily circles of influence.",
            "foundation_connection": "Our social education programs equip communities with tools for conflict resolution, mutual understanding, and civic responsibility.",
            "cta": "Reach out to resolve a minor misunderstanding with someone you know with kindness and honesty.",
            "hashtags": ["#EmpathyFirst", "#JusticeInAction", "#CivicResponsibility", "#SharedDignity"],
        },
        {
            "context": "Human dignity is universal; treating every individual with respect creates the bedrock of safe and flourishing neighborhoods.",
            "foundation_connection": "Jalte Diye Foundation fosters inclusive community platforms that celebrate diverse backgrounds and protect the fundamental dignity of all.",
            "cta": "Perform one deliberate act of kindness for a neighbor or service worker in your locality today.",
            "hashtags": ["#HumanDignity", "#KindnessMatters", "#InclusiveSociety", "#JalteDiyeFoundation"],
        },
    ],
    "mental_health_mindfulness": [
        {
            "context": "Taking care of our mental and emotional health is just as vital as physical well-being. Slowing down helps us stay grounded.",
            "foundation_connection": "At Jalte Diye Foundation, our wellness workshops encourage open conversations about mental health, stress management, and mindful living.",
            "cta": "Take 5 minutes away from your screen today to practice deep breathing or a quiet walk.",
            "hashtags": ["#MentalHealthMatters", "#MindfulLiving", "#SelfCare", "#EmotionalWellness"],
        },
        {
            "context": "In a fast-paced world, pausing to check in on our thoughts and feelings builds inner resilience and compassion for others.",
            "foundation_connection": "We integrate mindfulness and peer-support activities into our community centers to nurture emotionally safe and supportive environments.",
            "cta": "Ask a friend or family member how they are genuinely doing today and listen without offering quick advice.",
            "hashtags": ["#EmotionalSupport", "#ListenWithCare", "#Mindfulness", "#CommunityWellbeing"],
        },
    ],
    "cardiovascular_heart_health": [
        {
            "context": "Heart health is built through simple, consistent daily choices—eating nourishing foods, moving regularly, and managing stress.",
            "foundation_connection": "At Jalte Diye Foundation, our community health sessions promote preventive cardiovascular care and accessible wellness routines for all families.",
            "cta": "Take a brisk 20-minute walk or choose a fresh, heart-healthy snack instead of processed food today.",
            "hashtags": ["#WorldHeartDay", "#HeartHealth", "#PreventiveCare", "#HealthyLiving"],
        },
        {
            "context": "Caring for your heart protects your energy, longevity, and ability to be there for the people and causes you love.",
            "foundation_connection": "Our health education initiatives raise awareness about blood pressure monitoring, active living, and daily habits that sustain vitality.",
            "cta": "Encourage a loved one to join you for an evening walk or schedule a routine health checkup.",
            "hashtags": ["#HealthyHabits", "#CardiovascularWellness", "#MoveDaily", "#JalteDiyeFoundation"],
        },
    ],
    "health_wellness_nutrition": [
        {
            "context": "True community resilience starts with good health, balanced nutrition, and clean surroundings that allow families to thrive.",
            "foundation_connection": "At Jalte Diye Foundation, our healthcare initiatives focus on preventive health awareness, clean drinking water, and balanced community nutrition.",
            "cta": "Drink an extra glass of water and add a serving of fresh fruits or vegetables to your meals today.",
            "hashtags": ["#CommunityHealth", "#NutritionMatters", "#PreventiveHealth", "#WellnessForAll"],
        },
        {
            "context": "Healthy daily habits build strong immune systems and provide the stamina needed for learning, working, and caring for others.",
            "foundation_connection": "We partner with local healthcare volunteers to provide accessible wellness guidance and nutritional education in underserved neighborhoods.",
            "cta": "Replace one sugary drink with fresh water or herbal tea today to support your body's wellness.",
            "hashtags": ["#DailyWellness", "#HealthyChoices", "#StayHydrated", "#SocialEducation"],
        },
    ],
    "democracy_civic_rights": [
        {
            "context": "An active democracy relies on informed, engaged citizens who care about their community and participate in civic life.",
            "foundation_connection": "At Jalte Diye Foundation, our civic literacy programs empower community members with knowledge about their rights, duties, and local governance.",
            "cta": "Read up on a local community issue or attend a neighborhood meeting to stay informed.",
            "hashtags": ["#CivicEngagement", "#InformedCitizens", "#DemocracyInAction", "#SocialEducation"],
        },
        {
            "context": "Democracy is strengthened when every voice has an opportunity to contribute to positive community decisions.",
            "foundation_connection": "We facilitate inclusive community town halls and youth forums to encourage constructive civic participation and responsible leadership.",
            "cta": "Have a constructive conversation with a neighbor about how to improve your local community.",
            "hashtags": ["#ActiveCitizenship", "#CommunityVoices", "#CivicDuty", "#JalteDiyeFoundation"],
        },
    ],
    "civic_rights_transparency_information": [
        {
            "context": "Access to accurate information and transparency in public systems empower citizens to make sound decisions and hold institutions accountable.",
            "foundation_connection": "Jalte Diye Foundation advocates for information access and media literacy so people can navigate public resources with confidence.",
            "cta": "Verify the source of a news item before sharing it on social media or in messaging groups today.",
            "hashtags": ["#RightToInformation", "#Transparency", "#MediaLiteracy", "#EmpoweredCitizens"],
        },
    ],
}


def get_topic_fallback_template(domain: str, quote: str, event_name: str = "") -> dict[str, Any]:
    """Retrieve a varied topic-specific fallback template for the given domain."""
    # Check if event_name has an exact event match in Foundation Events
    if event_name and ("older person" in event_name.lower() or "elder" in event_name.lower()):
        return TOPIC_FALLBACK_TEMPLATES["Foundation Events"][0]

    templates = TOPIC_FALLBACK_TEMPLATES.get(domain)
    if not templates:
        templates = TOPIC_FALLBACK_TEMPLATES.get("peace_justice_humanity", [
            {
                "context": "Every small step we take today shapes the world we live in tomorrow.",
                "foundation_connection": "At Jalte Diye Foundation, our work is centered on bringing people together to solve everyday challenges through social education.",
                "cta": "Take one positive step in your community today, whether it's learning something new or helping a neighbor.",
                "hashtags": ["#SocialEducation", "#CommunityFirst", "#JalteDiyeFoundation"],
            }
        ])

    idx = sum(ord(c) for c in quote) % len(templates)
    return templates[idx]


THEME_TO_DOMAIN_MAP = {
    "Quality Education": "quality_education_literacy",
    "Climate & Environment": "climate_environment_nature",
    "Peace & Justice": "peace_justice_humanity",
    "Women Empowerment": "women_gender_empowerment",
    "Health & Mindfulness": "health_wellness_nutrition",
    "Foundation Events": "Foundation Events",
}

EMERGENCY_DOMAIN_QUOTES = {
    "Foundation Events": [
        {
            "quote": "To honor our elders is to honor the roots that give our entire community shade and stability.",
            "explanation": "Elders carry irreplaceable lived wisdom and stories that guide and strengthen future generations.",
        },
        {
            "quote": "Wisdom is not found in search engines alone; it lives in the lived experiences and stories of our elders.",
            "explanation": "Observing International Day of Older Persons reminds us to honor the lifelong contributions and dignity of older persons.",
        },
        {
            "quote": "Every elder is a living archive of community memory, resilience, and quiet guidance.",
            "explanation": "At Jalte Diye Foundation, our social education values intergenerational respect and learning from the life experiences of our elders.",
        },
        {
            "quote": "Special calendar observances unite us in remembering our shared values, history, and common humanity.",
            "explanation": "Observing foundation events encourages reflection, community conversations, and mutual respect across generations.",
        },
    ],
    "peace_justice_humanity": [
        {
            "quote": "Peace is not the absence of conflict, but the presence of creative alternatives for responding to conflict.",
            "explanation": "True peace comes from actively listening and finding constructive solutions together.",
        },
        {
            "quote": "Justice will not be served until those who are unaffected are as outraged as those who are.",
            "explanation": "Standing up for others is the cornerstone of a fair and compassionate society.",
        },
    ],
    "quality_education_literacy": [
        {
            "quote": "Education is the most powerful weapon which you can use to change the world.",
            "explanation": "Learning gives people the agency to shape their own lives and uplift their neighborhoods.",
        },
        {
            "quote": "The roots of education are bitter, but the fruit is sweet.",
            "explanation": "Dedication to learning requires patience, but the long-term rewards transform entire generations.",
        },
    ],
    "climate_environment_nature": [
        {
            "quote": "The earth does not belong to us: we belong to the earth.",
            "explanation": "Living responsibly means respecting natural resources and protecting the ecosystems around us.",
        },
        {
            "quote": "What we are doing to the forests of the world is but a mirror reflection of what we are doing to ourselves and one another.",
            "explanation": "Environmental health is inextricably linked to our own well-being and future security.",
        },
    ],
    "women_gender_empowerment": [
        {
            "quote": "There is no limit to what we, as women, can accomplish.",
            "explanation": "When women have equal opportunities, entire societies become more innovative and resilient.",
        },
        {
            "quote": "I raise up my voice—not so that I can shout, but so that those without a voice can be heard.",
            "explanation": "Empowering women means creating platforms where everyone's perspective is heard and respected.",
        },
    ],
    "health_wellness_nutrition": [
        {
            "quote": "It is health that is real wealth and not pieces of gold and silver.",
            "explanation": "Daily well-being and preventive care are the true foundations of a flourishing life.",
        },
        {
            "quote": "Take care of your body. It is the only place you have to live.",
            "explanation": "Nourishing habits and balanced routines sustain our energy and resilience over time.",
        },
    ],
    "mental_health_mindfulness": [
        {
            "quote": "Quiet the mind, and the soul will speak.",
            "explanation": "Mindful pauses during the day restore mental clarity and inner balance.",
        },
    ],
    "cardiovascular_heart_health": [
        {
            "quote": "A healthy heart is the rhythm of a vibrant and purposeful life.",
            "explanation": "Daily physical activity and nutritious choices protect cardiovascular wellness and longevity.",
        },
    ],
    "democracy_civic_rights": [
        {
            "quote": "An informed citizen is a free citizen. Transparency is the air a democracy breathes.",
            "explanation": "Active civic participation and access to reliable information keep our public institutions accountable.",
        },
    ],
    "civic_rights_transparency_information": [
        {
            "quote": "Access to accurate information is the foundation of an empowered community.",
            "explanation": "Transparency ensures citizens can make well-informed decisions for their families and neighborhoods.",
        },
    ],
}

EMERGENCY_FALLBACK_QUOTES = EMERGENCY_DOMAIN_QUOTES


def derive_fallback_event_name(
    theme: str,
    quote: str,
    context: str,
    event: dict | None = None,
) -> str:
    """Determine the content-relevant event name for fallback metadata."""
    if event and event.get("event"):
        return event["event"]

    clean_quote = (quote or "").lower()
    clean_ctx = (context or "").lower()

    if "elder" in clean_quote or "elder" in clean_ctx or "older person" in clean_ctx:
        return "International Day of Older Persons"
    if "heart" in clean_quote or "cardiovascular" in clean_ctx or "heart" in clean_ctx:
        return "World Heart Day"
    if "teacher" in clean_quote or "teacher" in clean_ctx or "teaching" in clean_ctx:
        return "World Teachers' Day"
    if "non-violence" in clean_quote or "gandhi" in clean_ctx or "non-violence" in clean_ctx:
        return "Gandhi Jayanti / International Day of Non-Violence"
    if "mental health" in clean_quote or "mental health" in clean_ctx:
        return "World Mental Health Day"
    if "girl child" in clean_quote or "girl child" in clean_ctx:
        return "International Day of the Girl Child"

    return "General Awareness"


def load_used_quotes(log_path: str) -> set[str]:
    """Load previously used quotes from the log file to prevent duplicate selections."""
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


def synthesize_fresh_fallback_candidate(
    domain: str,
    theme: str = "",
    event_name: str = "",
    used_quotes: set[str] | None = None,
) -> dict[str, str]:
    """Synthesize a fresh, semantically valid fallback candidate when emergency pools are exhausted."""
    used_quotes = used_quotes or set()
    from content.validator import normalize_text

    used_norms = {normalize_text(q) for q in used_quotes if q}

    def _is_unused(q: str) -> bool:
        return bool(q and q.strip() not in used_quotes and normalize_text(q) not in used_norms)

    # 1. If event_name is specified, try event-focused variations
    if event_name:
        clean_ev = event_name.strip()
        ev_variations = []
        if "elder" in clean_ev.lower() or "older person" in clean_ev.lower():
            ev_variations.extend([
                (
                    "To honor our elders is to preserve the living history and wisdom that guide our community forward.",
                    "Elders carry irreplaceable lived wisdom and stories that guide and strengthen future generations.",
                ),
                (
                    "Observing International Day of Older Persons reminds us to honor the wisdom and lifelong learning of our elders.",
                    "At Jalte Diye Foundation, our social education values intergenerational respect and learning from the life experiences of our elders.",
                ),
                (
                    "A community that listens to its elders builds a future anchored in compassion and shared values.",
                    "Connecting with older persons enriches our perspective and deepens mutual respect across generations.",
                ),
            ])
        elif "heart" in clean_ev.lower():
            ev_variations.extend([
                (
                    "Every beat matters. Guard your heart with daily movement and mindful living.",
                    "Caring for cardiovascular health protects your vitality and strengthens your everyday well-being.",
                ),
                (
                    "A healthy heart powers every ambition and sustains every community connection.",
                    "Preventive heart habits practiced daily ensure long-term energy, resilience, and community strength.",
                ),
            ])
        for q_cand, exp_cand in ev_variations:
            if _is_unused(q_cand):
                return {"quote": q_cand, "explanation": exp_cand}

    # 2. Domain-focused synthesis pools
    fresh_domain_pools = {
        "Foundation Events": [
            (
                "Special calendar observances unite us in remembering our shared values, history, and common humanity.",
                "Marking community occasions helps us reflect on empathy, lifelong learning, and social progress.",
            ),
            (
                "When we come together to observe important days, we renew our commitment to community well-being.",
                "Community observances provide meaningful opportunities to connect, learn, and act with shared purpose.",
            ),
        ],
        "peace_justice_humanity": [
            (
                "True peace begins when every person is recognized with equal dignity and given fair respect.",
                "Fostering justice and human dignity creates a strong foundation where all people can thrive together.",
            ),
            (
                "Justice is the quiet commitment to stand for fairness and mutual respect in every neighborhood.",
                "Promoting human dignity and equality builds lasting trust and harmony across our community.",
            ),
        ],
        "climate_environment_nature": [
            (
                "Small daily actions to protect nature preserve the clean air and green spaces we all depend on.",
                "Caring for the environment is an ongoing responsibility that safeguards the planet for future generations.",
            ),
            (
                "Every conscious choice to reduce waste and conserve water strengthens our shared environment.",
                "Sustainable daily habits protect local ecosystems and build a healthier, greener tomorrow.",
            ),
        ],
        "quality_education_literacy": [
            (
                "Education opens doors to curiosity, critical thinking, and lifelong opportunities for every learner.",
                "Accessible learning and literacy empower individuals to build meaningful lives and uplift their community.",
            ),
            (
                "When knowledge is shared freely and openly, entire communities gain the tools to solve complex problems.",
                "Investing in quality learning experiences nurtures thoughtful minds and drives collective progress.",
            ),
        ],
        "women_gender_empowerment": [
            (
                "When women and girls are supported to lead with confidence, entire communities grow stronger and more just.",
                "Empowering women through equal opportunity and mutual respect unlocks potential across all fields of life.",
            ),
            (
                "Real equality means creating spaces where women's voices and ideas are valued and celebrated.",
                "Championing gender equality transforms families and builds more resilient, fair, and prosperous societies.",
            ),
        ],
        "mental_health_mindfulness": [
            (
                "Mindful awareness in our daily routines helps us navigate stress and cultivate deeper presence with loved ones.",
                "Caring for emotional well-being is an essential daily practice that nurtures peace within and around us.",
            ),
        ],
        "cardiovascular_heart_health": [
            (
                "Prioritizing cardiovascular health through daily movement and mindful choices protects your energy and vitality.",
                "Small, nourishing habits practiced every day keep our hearts resilient and our bodies energized.",
            ),
        ],
        "health_wellness_nutrition": [
            (
                "Good health and compassionate community support are the essential foundations of human well-being.",
                "Promoting preventive wellness and healthy daily choices enables entire neighborhoods to thrive.",
            ),
        ],
    }

    candidates = fresh_domain_pools.get(domain) or fresh_domain_pools.get("Foundation Events") or fresh_domain_pools["peace_justice_humanity"]
    for q_cand, exp_cand in candidates:
        if _is_unused(q_cand):
            return {"quote": q_cand, "explanation": exp_cand}

    # 3. Procedural generator for infinite unique candidates guaranteed never to duplicate
    prefix_map = {
        "Foundation Events": "Community observance and shared heritage",
        "peace_justice_humanity": "True peace, justice, and human dignity",
        "climate_environment_nature": "Care for the earth and sustainable living",
        "quality_education_literacy": "Lifelong learning and open knowledge",
        "women_gender_empowerment": "Equal empowerment and mutual dignity for women",
        "mental_health_mindfulness": "Inner mindfulness, patience, and emotional calm",
        "cardiovascular_heart_health": "Daily heart care and cardiovascular wellness",
        "health_wellness_nutrition": "Community wellness and preventive health care",
        "democracy_civic_rights": "Active citizenship and civic awareness",
        "civic_rights_transparency_information": "Public transparency and honest information",
    }
    subj = prefix_map.get(domain, "Shared empathy and mutual respect")
    counter = 1
    while True:
        procedural_q = f"{subj} inspire meaningful progress across our community (Ref #{counter})."
        procedural_exp = f"Emphasizing {domain.replace('_', ' ')} fosters understanding, empathy, and collective community growth."
        if _is_unused(procedural_q):
            return {"quote": procedural_q, "explanation": procedural_exp}
        counter += 1


class FallbackProvider:
    """Provides unused quotes from theme-specific CSV files with structured fallback descriptions."""

    def __init__(self, config: dict[str, Any], project_root: str) -> None:
        self._config = config
        self._project_root = project_root
        self._used_quotes_log = self._resolve_path(config["paths"]["used_quotes_log"])
        self._emergency = config.get("emergency_failsafe", {})

    def _resolve_path(self, relative_path: str) -> str:
        return os.path.join(self._project_root, relative_path)

    def get_fallback_quote(self, theme: str, event: dict | None = None) -> dict[str, Any]:
        """Pull an unused quote from the CSV mapped to the given theme or event."""
        logger.warning("Triggering CSV fallback for theme: %s (event: %s)", theme, event.get("event") if event else None)
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
        fallback_content = self._read_unused_csv_quote(csv_file, used_quotes, event_name, theme)
        if fallback_content:
            mark_quote_used(fallback_content["quote"], self._used_quotes_log)

            # Determine best template based on quote domain to guarantee topic consistency
            quote_scores = detect_domain_scores(f"{fallback_content['quote']} {fallback_content.get('explanation', '')}")
            if not event_name and theme and theme in THEME_EXPECTED_DOMAINS:
                valid_domains = [d for d in quote_scores if d in THEME_EXPECTED_DOMAINS[theme]]
                if valid_domains:
                    top_domain = max(valid_domains, key=lambda d: quote_scores[d])
                else:
                    top_domain = THEME_TO_DOMAIN_MAP.get(theme, "peace_justice_humanity")
            elif event_name and "heart" in event_name.lower():
                top_domain = "cardiovascular_heart_health"
            elif event_name and ("elder" in event_name.lower() or "older person" in event_name.lower()):
                top_domain = "Foundation Events"
            elif quote_scores:
                top_domain = max(quote_scores.items(), key=lambda x: x[1])[0]
            elif event_name:
                top_domain = "Foundation Events"
            else:
                top_domain = THEME_TO_DOMAIN_MAP.get(theme, "peace_justice_humanity")

            tpl = get_topic_fallback_template(top_domain, fallback_content["quote"], event_name=event_name or "")

            context = sanitize_text(tpl["context"])
            foundation_conn = sanitize_text(tpl["foundation_connection"])
            cta = sanitize_text(tpl["cta"])
            hashtags = list(tpl["hashtags"])
            if event_name:
                event_tag = f"#{event_name.replace(' ', '').replace('&', 'And').replace('-', '')}"
                if event_tag not in hashtags:
                    hashtags.insert(0, event_tag)

            fallback_content["topic"] = top_domain.replace("_", " ").title()
            fallback_content["event_name"] = derive_fallback_event_name(theme, fallback_content["quote"], context, event)
            fallback_content["quote"] = sanitize_text(fallback_content["quote"])
            fallback_content["explanation"] = sanitize_text(fallback_content.get("explanation", ""))
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

        logger.warning("No unused or theme-aligned quotes remain in CSV: %s; using domain emergency failsafe.", csv_file)
        return self._emergency_failsafe(theme, event)

    def _read_unused_csv_quote(
        self,
        csv_file: str,
        used_quotes: set[str],
        event_name: str | None = None,
        theme: str | None = None,
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
                quote_idx = 0
                caption_idx = 1 if len(raw_rows[0]) > 1 else -1
                occasion_idx = -1
                data_rows = raw_rows

        if event_name and occasion_idx != -1:
            norm_ev = event_name.lower().replace("'", "").replace("’", "").strip()
            candidate_rows = [
                r for r in data_rows
                if len(r) > occasion_idx and r[occasion_idx].strip().lower().replace("'", "").replace("’", "") == norm_ev
            ]
            if not candidate_rows:
                candidate_rows = [
                    r for r in data_rows
                    if len(r) > occasion_idx and (
                        norm_ev in r[occasion_idx].strip().lower().replace("'", "").replace("’", "")
                        or r[occasion_idx].strip().lower().replace("'", "").replace("’", "") in norm_ev
                    )
                ]
            if not candidate_rows:
                logger.warning("No CSV rows matching event '%s'", event_name)
                return None
        else:
            candidate_rows = data_rows

        def validate_explanation_quality(explanation: str, quote_text: str) -> bool:
            if not explanation:
                return True
            words = explanation.split()
            if len(words) < 3:
                return False
            return True

        expected_doms = None
        if event_name and "heart" in event_name.lower():
            expected_doms = {"cardiovascular_heart_health", "health_wellness_nutrition"}
        elif theme and theme in THEME_EXPECTED_DOMAINS:
            expected_doms = THEME_EXPECTED_DOMAINS[theme]

        from content.validator import normalize_text
        used_norms = {normalize_text(q) for q in used_quotes if q}

        for row in candidate_rows:
            if not row or len(row) <= quote_idx:
                continue
            row_quote = sanitize_text(row[quote_idx].strip())
            row_explanation = ""
            if caption_idx != -1 and len(row) > caption_idx:
                row_explanation = sanitize_text(row[caption_idx].strip())
            elif occasion_idx != -1 and len(row) > occasion_idx:
                occasion_val = sanitize_text(row[occasion_idx].strip())
                if event_name and norm_ev in occasion_val.lower().replace("'", "").replace("’", ""):
                    row_explanation = f"Observing {occasion_val}."

            if not row_quote or row_quote in used_quotes or normalize_text(row_quote) in used_norms:
                continue

            # Verify that quote strictly matches the expected domain
            if expected_doms:
                q_scores = detect_domain_scores(row_quote)
                if q_scores:
                    matched_expected = [d for d in q_scores if d in expected_doms]
                    if not matched_expected:
                        continue

            if not row_explanation:
                row_explanation = "Every small step we take today shapes the world we live in tomorrow."

            if validate_explanation_quality(row_explanation, row_quote):
                q_scores = detect_domain_scores(row_quote)
                top_dom = max(q_scores.items(), key=lambda x: x[1])[0] if q_scores else "peace_justice_humanity"
                if "elder" in row_quote.lower() or "older person" in (event_name or "").lower():
                    row_explanation = "Elders carry irreplaceable lived wisdom and stories that guide and strengthen future generations."
                elif "heart" in row_quote.lower() or "cardiovascular" in row_quote.lower():
                    row_explanation = "Daily cardiovascular care and healthy habits protect your heart and strengthen your future."
                elif "math" in row_quote.lower() or "chalk" in row_quote.lower():
                    row_explanation = "The quote emphasizes measurable urgency and acting before emissions become harder to change."
                elif "peace" in row_quote.lower() or "violence" in row_quote.lower():
                    row_explanation = "Non-violence is an active choice to build understanding and resolve conflict with empathy."
                return {
                    "quote": row_quote,
                    "explanation": row_explanation,
                }

            fallback_explanation = "Every small step we take today shapes the world we live in tomorrow."
            if validate_explanation_quality(fallback_explanation, row_quote):
                return {
                    "quote": row_quote,
                    "explanation": fallback_explanation,
                }

        return None

    def _emergency_failsafe(self, theme: str = "", event: dict | None = None) -> dict[str, Any]:
        """Generate a semantically aligned emergency failsafe quote for the given theme or event, strictly respecting duplicate prevention and domain compatibility."""
        logger.warning("Using emergency domain-aligned failsafe quote.")
        top_domain = "peace_justice_humanity"
        ev_name = ""

        if event and event.get("event"):
            ev_name = event["event"]
            if "heart" in ev_name.lower():
                top_domain = "cardiovascular_heart_health"
            elif "elder" in ev_name.lower() or "older person" in ev_name.lower() or event.get("is_foundation_event") or theme == "Foundation Events":
                top_domain = "Foundation Events"
            else:
                ev_scores = detect_domain_scores(ev_name)
                if ev_scores:
                    top_domain = max(ev_scores.items(), key=lambda x: x[1])[0]
                else:
                    top_domain = THEME_TO_DOMAIN_MAP.get(theme, "Foundation Events")
        elif theme:
            top_domain = THEME_TO_DOMAIN_MAP.get(theme, "peace_justice_humanity")

        used_quotes = load_used_quotes(self._used_quotes_log)
        from content.validator import normalize_text
        used_norms = {normalize_text(q) for q in used_quotes if q}

        def _is_unused(q: str) -> bool:
            return bool(q and q.strip() not in used_quotes and normalize_text(q) not in used_norms)

        # 1. First search in target domain emergency pool for an unused candidate
        chosen = None
        if top_domain in EMERGENCY_DOMAIN_QUOTES:
            for candidate in EMERGENCY_DOMAIN_QUOTES[top_domain]:
                cand_quote = sanitize_text(candidate["quote"])
                if _is_unused(cand_quote):
                    chosen = candidate
                    break

        # 2. If no unused quote in target domain, search ONLY in semantically compatible domains
        if not chosen:
            compatible_domains = []
            if theme == "Foundation Events" or top_domain == "Foundation Events":
                compatible_domains = ["Foundation Events", "peace_justice_humanity", "democracy_civic_rights", "civic_rights_transparency_information"]
            elif theme and theme in THEME_EXPECTED_DOMAINS:
                compatible_domains = [top_domain] + [d for d in THEME_EXPECTED_DOMAINS[theme] if d != top_domain]
            elif top_domain in EMERGENCY_DOMAIN_QUOTES:
                compatible_domains = [top_domain]

            for domain_key in compatible_domains:
                if domain_key == top_domain:
                    continue
                domain_candidates = EMERGENCY_DOMAIN_QUOTES.get(domain_key, [])
                for candidate in domain_candidates:
                    cand_quote = sanitize_text(candidate["quote"])
                    if _is_unused(cand_quote):
                        chosen = candidate
                        top_domain = domain_key
                        break
                if chosen:
                    break

        # 3. If all compatible candidates are exhausted, synthesize a fresh, unused candidate
        if not chosen:
            chosen = synthesize_fresh_fallback_candidate(top_domain, theme=theme, event_name=ev_name, used_quotes=used_quotes)
            logger.info("Synthesized fresh emergency fallback for domain '%s', theme '%s'", top_domain, theme)

        quote = sanitize_text(chosen["quote"])
        explanation = sanitize_text(chosen["explanation"])

        mark_quote_used(quote, self._used_quotes_log)

        tpl = get_topic_fallback_template(top_domain, quote, event_name=ev_name)

        context = sanitize_text(tpl["context"])
        foundation_conn = sanitize_text(tpl["foundation_connection"])
        cta = sanitize_text(tpl["cta"])
        hashtags = list(tpl["hashtags"])
        if ev_name:
            event_tag = f"#{ev_name.replace(' ', '').replace('&', 'And').replace('-', '')}"
            if event_tag not in hashtags:
                hashtags.insert(0, event_tag)

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
            "topic": top_domain.replace("_", " ").title(),
            "event_name": derive_fallback_event_name(theme, quote, context, event),
            "context": context,
            "foundation_connection": foundation_conn,
            "cta": cta,
            "hashtags": hashtags,
            "long_explanation": long_explanation,
            "caption": caption,
            "description": build_structured_long_explanation(
                context=context,
                foundation_connection=foundation_conn,
                cta=cta,
                hashtags=hashtags,
            ),
        }
