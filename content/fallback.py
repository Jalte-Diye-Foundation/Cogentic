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
from content.validator import detect_domain_scores

logger = logging.getLogger(__name__)

# Topic-specific synthesis templates for fallback scenarios to ensure semantic consistency and variation
TOPIC_FALLBACK_TEMPLATES: dict[str, list[dict[str, Any]]] = {
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
            "context": "Our relationship with nature shows up in the food we eat, the soil we preserve, and the biodiversity we protect around our homes.",
            "foundation_connection": "Jalte Diye Foundation connects environmental awareness directly with community well-being, encouraging sustainable living that respects local ecosystems.",
            "cta": "Choose locally grown produce or plant a native flower pot on your balcony today.",
            "hashtags": ["#EcoFriendlyLiving", "#ProtectNature", "#SustainableChoices", "#ClimateAction"],
        },
        {
            "context": "Every river, tree, and open green space is borrowed from future generations, demanding our active care and mindful stewardship.",
            "foundation_connection": "Social education at Jalte Diye Foundation includes nurturing environmental consciousness so young people grow up valuing clean air, clean water, and green surroundings.",
            "cta": "Spend ten minutes today picking up litter in a neighborhood park or conserving water at home.",
            "hashtags": ["#EarthCare", "#CleanPlanet", "#GreenFuture", "#SocialEducation"],
        },
    ],
    "quality_education_literacy": [
        {
            "context": "Real learning happens far beyond school walls. It happens whenever someone asks a good question, learns from a mistake, or shares a skill with a friend.",
            "foundation_connection": "Education is at the very core of Jalte Diye Foundation. When knowledge is shared freely and kindly, it gives people the confidence to shape their own lives.",
            "cta": "Share one interesting thing you learned recently with someone who might enjoy hearing it.",
            "hashtags": ["#QualityEducation", "#LifelongLearning", "#ShareKnowledge", "#SocialEducation"],
        },
        {
            "context": "Curiosity is the spark of wisdom; asking why and questioning assumptions allows a society to grow wiser and more compassionate.",
            "foundation_connection": "Jalte Diye Foundation fosters critical thinking and lifelong curiosity through accessible social learning for learners of all ages.",
            "cta": "Read an article on a new topic or ask a thoughtful question about something you do not understand today.",
            "hashtags": ["#CuriosityAndLearning", "#EducationForAll", "#ReadToGrow", "#SocialEducation"],
        },
        {
            "context": "Books and open discussions open windows into experiences we have never lived, expanding our empathy and perspective.",
            "foundation_connection": "Promoting reading and open dialogue is essential to Jalte Diye Foundation's goal of building compassionate, well-informed communities.",
            "cta": "Gift or lend a favorite book to a neighbor, child, or colleague today.",
            "hashtags": ["#LoveOfReading", "#OpenMinds", "#LifelongLiteracy", "#SocialEducation"],
        },
    ],
    "mental_health_mindfulness": [
        {
            "context": "Taking care of your mental peace is not selfish—it is what gives you the patience and empathy to show up well for the people who rely on you.",
            "foundation_connection": "Emotional well-being and mindfulness are central to Jalte Diye Foundation's holistic view of social education. Calm, grounded individuals build more caring communities.",
            "cta": "Take a quiet five-minute pause today to breathe deeply and check in on how you are feeling.",
            "hashtags": ["#HealthAndMindfulness", "#MentalPeace", "#SelfCare", "#DailyCalm"],
        },
        {
            "context": "Being fully present for another person in distress, listening without rushing to fix everything, has profound healing power.",
            "foundation_connection": "Jalte Diye Foundation nurtures compassionate listening as an essential life skill that strengthens relationships and reduces emotional isolation.",
            "cta": "Check in on a friend or family member today and listen without interrupting or giving unsolicited advice.",
            "hashtags": ["#EmotionalWellbeing", "#MindfulLiving", "#EmpatheticListening", "#SocialEducation"],
        },
        {
            "context": "Slow, mindful breathing during stressful moments helps reset our focus and allows reason rather than reaction to guide our words.",
            "foundation_connection": "At Jalte Diye Foundation, mindfulness is taught as a daily tool for peaceful communication and self-regulation in community life.",
            "cta": "Step away from your screen for five minutes and take ten conscious, calming breaths.",
            "hashtags": ["#MindfulMoments", "#InnerCalm", "#StressRelief", "#MentalWellbeing"],
        },
    ],
    "peace_justice_humanity": [
        {
            "context": "Meaningful peace rarely begins with treaties in distant capitals; it starts in quiet moments when we choose to listen rather than argue.",
            "foundation_connection": "Fairness and empathy form the bedrock of social education at Jalte Diye Foundation. Choosing understanding over swift judgment makes every neighborhood safer.",
            "cta": "Pause and listen completely during one conversation today before thinking about your reply.",
            "hashtags": ["#PeaceAndJustice", "#DailyKindness", "#CommunityDialogue", "#SocialEducation"],
        },
        {
            "context": "Building harmony is not an abstract theory, but a daily practice of patience, mutual respect, and quiet courage.",
            "foundation_connection": "At Jalte Diye Foundation, our social education work emphasizes practical coexistence. Treating every neighbor with equal dignity turns goodwill into real community strength.",
            "cta": "Offer a sincere word of appreciation to someone whose daily work makes your life easier.",
            "hashtags": ["#DailyKindness", "#PeaceInAction", "#SharedDignity", "#SocialEducation"],
        },
        {
            "context": "Disagreements are natural in any community, but how we respond to them determines whether we grow apart or grow closer.",
            "foundation_connection": "Jalte Diye Foundation focuses on community dialogue because lasting solutions come when people sit face-to-face and find common ground.",
            "cta": "Reach out to mend a small misunderstanding with a friend, coworker, or neighbor today.",
            "hashtags": ["#CommunityHarmony", "#EmpathyFirst", "#PeacefulCoexistence", "#SocialEducation"],
        },
    ],
    "democracy_civic_rights": [
        {
            "context": "A strong community depends on active, thoughtful citizens who participate and stand up for the collective good.",
            "foundation_connection": "Jalte Diye Foundation fosters civic responsibility and ethical awareness as cornerstones of constructive community life.",
            "cta": "Engage in an open, respectful discussion on an issue that affects your neighborhood today.",
            "hashtags": ["#CivicAwareness", "#ActiveCitizenship", "#CommunityAction", "#SocialEducation"],
        },
    ],
    "civic_rights_transparency_information": [
        {
            "context": "A healthy society relies on informed citizens who have access to truthful information and open, honest dialogue.",
            "foundation_connection": "At Jalte Diye Foundation, we believe transparency and awareness are essential pillars of constructive social education.",
            "cta": "Take a moment today to verify a piece of information before sharing it with others.",
            "hashtags": ["#RightToKnow", "#InformedCitizens", "#TransparencyInAction", "#SocialEducation"],
        },
    ],
    "health_wellness_nutrition": [
        {
            "context": "Good physical and community health allows every person to learn, work, and contribute meaningfully to those around them.",
            "foundation_connection": "Promoting health awareness and preventive well-being is an essential aspect of Jalte Diye Foundation's holistic community support.",
            "cta": "Encourage a healthy habit or share a nutritious meal with someone today.",
            "hashtags": ["#HealthAndWellness", "#CommunityCare", "#HealthyHabits", "#SocialEducation"],
        },
        {
            "context": "Health is a fundamental human right; when quality healthcare and clean environments reach everyone, entire communities flourish.",
            "foundation_connection": "At Jalte Diye Foundation, our social education highlights the importance of public health, sanitation, and equal access to essential care.",
            "cta": "Support a local sanitation effort or drink plenty of water and encourage a coworker to take a brisk walk today.",
            "hashtags": ["#HealthEquity", "#PublicHealth", "#WellbeingForAll", "#SocialEducation"],
        },
    ],
    "rural_development_opportunity": [
        {
            "context": "Every community, whether in a bustling city or a quiet village, thrives when people have fair access to opportunities and resources.",
            "foundation_connection": "Jalte Diye Foundation values inclusive social education that reaches every neighborhood and community with equal dedication.",
            "cta": "Learn about and support an initiative that empowers rural or local artisan communities today.",
            "hashtags": ["#EqualOpportunity", "#CommunityDevelopment", "#RuralEmpowerment", "#SocialEducation"],
        },
    ],
    "Foundation Events": [
        {
            "context": "Special calendar days give us a welcome reason to pause our busy routines and remember the values that bring our communities together.",
            "foundation_connection": "Jalte Diye Foundation observes these occasions to encourage reflection, community conversations, and shared appreciation for our common humanity.",
            "cta": "Take two minutes today to learn about today's observance and share one thoughtful takeaway with a friend.",
            "hashtags": ["#CommunityObservance", "#CivicAwareness", "#SharedValues", "#JalteDiyeFoundation"],
        },
    ],
}


def get_topic_fallback_template(domain: str, quote_text: str = "") -> dict[str, Any]:
    """Retrieve a topic-specific fallback template, selecting dynamically when multiple exist."""
    norm_q = quote_text.lower()
    if "math" in norm_q or "chalk" in norm_q or "calculation" in norm_q:
        return {
            "context": "Addressing climate change requires measurable urgency and decisive action before emissions rise beyond our capacity to adapt.",
            "foundation_connection": "At Jalte Diye Foundation, our environmental focus emphasizes taking measurable, timely steps to care for our shared planet.",
            "cta": "Identify one practical daily action today to measure and reduce your personal carbon and waste footprint.",
            "hashtags": ["#ClimateUrgency", "#ClimateAction", "#MeasurableChoices", "#ClimateCare"],
        }
    if "renewable" in norm_q or "clean energy" in norm_q:
        return {
            "context": "Transitioning to clean, renewable energy powers our communities while reducing emissions and safeguarding the air we breathe.",
            "foundation_connection": "Jalte Diye Foundation promotes sustainable energy awareness as a vital pillar of long-term community health.",
            "cta": "Turn off unused appliances and learn about clean energy options available in your local area today.",
            "hashtags": ["#RenewableEnergy", "#CleanPower", "#EnergyTransition", "#ClimateCare"],
        }
    if ("activism" in norm_q or "advocacy" in norm_q) and ("selfcare" in norm_q or "self-care" in norm_q or "burnout" in norm_q or "tension" in norm_q):
        return {
            "context": "Social change work demands sustained energy and emotional commitment; prioritizing self-care enables advocates to stay engaged without burning out.",
            "foundation_connection": "Emotional resilience is central to Jalte Diye Foundation's view of social education, supporting dedicated changemakers in staying healthy and effective.",
            "cta": "Set aside time today to recharge your energy so you can continue supporting your community sustainably.",
            "hashtags": ["#SustainableActivism", "#SelfCare", "#CommunityWellbeing", "#MentalPeace"],
        }
    if "hope" in norm_q and ("anchor" in norm_q or "drift" in norm_q or "peace" in norm_q):
        return {
            "context": "When conflict and uncertainty create instability, a shared sense of hope and mutual trust keeps communities grounded and resilient.",
            "foundation_connection": "At Jalte Diye Foundation, our educational efforts foster hope and constructive dialogue as essential anchors of enduring peace.",
            "cta": "Share a message of hope and encouragement with a neighbor or colleague today.",
            "hashtags": ["#HopeAndPeace", "#CommunityResilience", "#PeaceAndJustice", "#SocialEducation"],
        }

    templates = TOPIC_FALLBACK_TEMPLATES.get(domain)
    if not templates:
        templates = TOPIC_FALLBACK_TEMPLATES.get("peace_justice_humanity", [])
    if isinstance(templates, dict):
        return templates
    if not templates:
        return {
            "context": "Reflecting on shared values and community responsibility helps us build a kinder, more empathetic society.",
            "foundation_connection": "At Jalte Diye Foundation, social education centers on practical empathy and mutual respect.",
            "cta": "Share one thoughtful takeaway with someone in your community today.",
            "hashtags": ["#SocialEducation", "#CommunityCare", "#JalteDiyeFoundation"],
        }

    if domain == "peace_justice_humanity" and len(templates) >= 3:
        if any(w in norm_q for w in ["action", "actions", "song", "deed", "deeds", "acts"]):
            return templates[1]
        if any(w in norm_q for w in ["conflict", "justice", "treaty", "treaties", "listen"]):
            return templates[0]
        if any(w in norm_q for w in ["disagree", "disagreement", "disagreements", "grow closer"]):
            return templates[2]

    if domain == "quality_education_literacy" and len(templates) >= 3:
        if any(w in norm_q for w in ["book", "books", "reading", "read", "library", "borrow"]):
            return templates[2]
        if any(w in norm_q for w in ["curiosity", "curious", "fire", "spark", "question", "questions"]):
            return templates[1]
        return templates[0]

    if domain == "climate_environment_nature" and len(templates) >= 3:
        if any(w in norm_q for w in ["river", "tree", "trees", "forest", "litter", "air"]):
            return templates[2]
        if any(w in norm_q for w in ["soil", "food", "biodiversity", "produce"]):
            return templates[1]
        return templates[0]

    if domain == "women_gender_empowerment" and len(templates) >= 3:
        if any(w in norm_q for w in ["daughter", "daughters", "girl", "girls", "barrier"]):
            return templates[1]
        if any(w in norm_q for w in ["stereotype", "bias", "dignity", "choice"]):
            return templates[2]
        return templates[0]

    if domain == "mental_health_mindfulness" and len(templates) >= 3:
        if any(w in norm_q for w in ["breathe", "breath", "breathing", "pause", "screen"]):
            return templates[2]
        if any(w in norm_q for w in ["listen", "distress", "story", "stories", "witness"]):
            return templates[1]
        return templates[0]

    if quote_text:
        selected_idx = sum(ord(c) * (i + 1) for i, c in enumerate(quote_text.strip().lower())) % len(templates)
    else:
        selected_idx = 0
    return templates[selected_idx]





THEME_TO_DOMAIN_MAP = {
    "Peace & Justice": "peace_justice_humanity",
    "Climate & Environment": "climate_environment_nature",
    "Quality Education": "quality_education_literacy",
    "Women Empowerment": "women_gender_empowerment",
    "Health & Mindfulness": "mental_health_mindfulness",
    "Foundation Events": "Foundation Events",
}

EMERGENCY_DOMAIN_QUOTES: dict[str, list[dict[str, str]]] = {
    "peace_justice_humanity": [
        {
            "quote": "Peace is not the absence of conflict; it is the presence of justice, understanding, and shared dignity.",
            "explanation": "True harmony begins when we choose dialogue, fairness, and mutual respect over division.",
        },
        {
            "quote": "The song of peace has no words, only actions.",
            "explanation": "Quiet acts of understanding build deeper trust than the grandest speeches.",
        },
        {
            "quote": "Where understanding grows, war finds no soil.",
            "explanation": "Listening with patience turns strangers into neighbors and dissolves conflict before it begins.",
        },
    ],
    "civic_rights_transparency_information": [
        {
            "quote": "An informed citizen is a free citizen. Transparency is the air a democracy breathes.",
            "explanation": "Access to truth and open information strengthens democratic accountability and public trust.",
        },
    ],
    "democracy_civic_rights": [
        {
            "quote": "An informed citizen is a free citizen. Transparency is the air a democracy breathes.",
            "explanation": "Active civic participation and transparency are the foundations of freedom.",
        },
    ],
    "climate_environment_nature": [
        {
            "quote": "The best time to plant a tree was twenty years ago. The second best time is now.",
            "explanation": "Every small step we take today shapes the world we live in tomorrow.",
        },
        {
            "quote": "We do not inherit the earth from our ancestors; we borrow it from our children.",
            "explanation": "Mindful daily choices protect our shared environment for future generations.",
        },
        {
            "quote": "Bread made from local grain is a loaf of climate justice.",
            "explanation": "Supporting local, sustainable choices strengthens community resilience and cares for the land.",
        },
    ],
    "quality_education_literacy": [
        {
            "quote": "Education is not filling a bucket, but lighting a fire that illuminates minds and communities.",
            "explanation": "Sharing knowledge freely and kindly empowers people to shape their own futures.",
        },
        {
            "quote": "To open a book is to borrow someone else's life for a while, return it richer.",
            "explanation": "Reading and curiosity expand our world and deepen our empathy for others.",
        },
        {
            "quote": "Knowledge hoarded is knowledge lost; knowledge shared is knowledge multiplied.",
            "explanation": "When we share what we learn, we help our entire community grow stronger.",
        },
    ],
    "women_gender_empowerment": [
        {
            "quote": "When women are given the space, freedom, and support to lead, entire communities rise.",
            "explanation": "Equal opportunities and mutual respect are essential for true community progress.",
        },
        {
            "quote": "A society that educates and empowers its daughters builds an unbreakable foundation for tomorrow.",
            "explanation": "Investing in girls' education and leadership creates lasting change for everyone.",
        },
        {
            "quote": "Equality is not a privilege to be granted; it is a fundamental human right to be honored.",
            "explanation": "True progress begins when every woman has the agency and freedom to shape her own path.",
        },
    ],
    "mental_health_mindfulness": [
        {
            "quote": "Inner stillness is the first seed of outer peace. Caring for your mental calm restores your strength.",
            "explanation": "Taking time to pause and reflect builds emotional resilience and compassion for others.",
        },
        {
            "quote": "Stories of suffering, heard with full attention, have healing power.",
            "explanation": "Being witnessed with genuine attention and care is one of the most powerful healing experiences.",
        },
        {
            "quote": "Breathing with awareness is the first and simplest act of peace.",
            "explanation": "A quiet moment of reflection calms the mind and helps us respond with clarity.",
        },
    ],
    "health_wellness_nutrition": [
        {
            "quote": "Good health and community care are the foundations upon which all human potential is built.",
            "explanation": "Prioritizing physical and mental well-being enables everyone to participate fully in life.",
        },
        {
            "quote": "Health equity is not a gift; it is an obligation that a caring society owes to all.",
            "explanation": "Ensuring fair access to healthcare creates stronger, more resilient neighborhoods.",
        },
    ],
    "refugees_migration": [
        {
            "quote": "Refugees carry their humanity across every border. Their worth is not defined by papers.",
            "explanation": "Recognizing equal human dignity bridges the divide between strangers and neighbors.",
        },
    ],
}


def derive_fallback_event_name(theme: str, quote: str, context: str = "", event: dict | None = None) -> str:
    """Derive an authoritative or content-relevant recognized event name for fallback content."""
    if event and event.get("event"):
        return sanitize_text(str(event["event"]).strip())

    text = f"{quote} {context}".lower()

    # 1. Topic/Quote specific recognized awareness days
    if any(w in text for w in ["girl", "daughter", "female child"]):
        return "International Day of the Girl Child"
    if any(w in text for w in ["women", "woman", "female leader", "equal partnership"]):
        return "International Women's Day"
    if any(w in text for w in ["forest", "trees", "woodland", "planting a tree", "plant a tree"]):
        return "International Day of Forests"
    if any(w in text for w in ["water", "river", "rivers", "wetland"]):
        return "World Water Day"
    if any(w in text for w in ["ocean", "marine", "sea", "coral"]):
        return "World Oceans Day"
    if any(w in text for w in ["earth", "soil", "climate", "renewable", "clean energy", "carbon", "nature", "litter", "plastic"]):
        return "World Environment Day"
    if any(w in text for w in ["book", "reading", "read a book", "library"]):
        return "World Book Day"
    if any(w in text for w in ["literacy", "illiteracy", "learn to read"]):
        return "International Literacy Day"
    if any(w in text for w in ["teacher", "classroom", "teach"]):
        return "World Teachers' Day"
    if any(w in text for w in ["mental health", "emotional", "stress", "calm", "inner stillness", "pause", "suffering"]):
        return "World Mental Health Day"
    if any(w in text for w in ["health", "nutrition", "wellness", "vitality", "doctor"]):
        return "World Health Day"
    if any(w in text for w in ["refugee", "migration", "border", "displaced"]):
        return "World Refugee Day"
    if any(w in text for w in ["transparency", "information", "right to know", "civic"]):
        return "Right to Know Day"
    if any(w in text for w in ["democracy", "vote", "voter", "voting"]):
        return "International Day of Democracy"
    if any(w in text for w in ["non-violence", "nonviolence", "ahimsa"]):
        return "International Day of Non-Violence"
    if any(w in text for w in ["human rights", "rights", "dignity"]):
        return "Human Rights Day"
    if any(w in text for w in ["peace", "justice", "conflict", "harmony", "dialogue"]):
        return "International Day of Peace"
    if any(w in text for w in ["education", "curiosity", "school", "learning"]):
        return "International Day of Education"

    # 2. Theme-level mapping
    if theme == "Women Empowerment":
        return "International Women's Day"
    elif theme == "Climate & Environment":
        return "World Environment Day"
    elif theme == "Quality Education":
        return "International Day of Education"
    elif theme == "Health & Mindfulness":
        return "World Mental Health Day"
    elif theme == "Peace & Justice":
        return "International Day of Peace"

    return "General Awareness"


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
            from content.validator import THEME_EXPECTED_DOMAINS
            quote_scores = detect_domain_scores(f"{fallback_content['quote']} {fallback_content.get('explanation', '')}")
            if not event_name and theme and theme in THEME_EXPECTED_DOMAINS:
                valid_domains = [d for d in quote_scores if d in THEME_EXPECTED_DOMAINS[theme]]
                if valid_domains:
                    top_domain = max(valid_domains, key=lambda d: quote_scores[d])
                else:
                    top_domain = THEME_TO_DOMAIN_MAP.get(theme, "peace_justice_humanity")
            elif quote_scores:
                top_domain = max(quote_scores.items(), key=lambda x: x[1])[0]
            elif event_name:
                top_domain = "Foundation Events"
            else:
                top_domain = THEME_TO_DOMAIN_MAP.get(theme, "peace_justice_humanity")

            tpl = get_topic_fallback_template(top_domain, fallback_content["quote"])

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
            candidate_rows = [
                r for r in data_rows
                if len(r) > occasion_idx and r[occasion_idx].strip().lower() == event_name.lower()
            ]
            if not candidate_rows:
                logger.warning("No CSV rows matching event '%s'", event_name)
                return None
        else:
            candidate_rows = data_rows

        from content.validator import THEME_EXPECTED_DOMAINS

        for row in candidate_rows:
            if not row or len(row) <= quote_idx:
                continue

            row_quote = sanitize_text(row[quote_idx].strip())
            row_explanation = ""
            if caption_idx != -1 and len(row) > caption_idx:
                row_explanation = sanitize_text(row[caption_idx].strip())
            elif occasion_idx != -1 and len(row) > occasion_idx:
                occasion_val = sanitize_text(row[occasion_idx].strip())
                if event_name and occasion_val.lower() == event_name.lower():
                    row_explanation = f"Observing {occasion_val}."

            if not row_quote or row_quote in used_quotes:
                continue

            # If evergreen theme, verify that quote strictly matches the expected theme domain
            if not event_name and theme and theme in THEME_EXPECTED_DOMAINS:
                q_scores = detect_domain_scores(row_quote)
                if not q_scores:
                    continue
                top_domain = max(q_scores.items(), key=lambda x: x[1])[0]
                expected_doms = THEME_EXPECTED_DOMAINS[theme]
                if top_domain not in expected_doms:
                    continue

            # Ensure explanation meets explanation quality standards
            from content.validator import validate_explanation_quality
            if validate_explanation_quality(row_explanation, row_quote):
                q_scores = detect_domain_scores(row_quote)
                top_dom = max(q_scores.items(), key=lambda x: x[1])[0] if q_scores else "peace_justice_humanity"
                if "math" in row_quote.lower() or "chalk" in row_quote.lower():
                    row_explanation = "The quote emphasizes measurable urgency and acting before emissions become harder to change."
                elif "renewable" in row_quote.lower() or "energy" in row_quote.lower():
                    row_explanation = "Clean energy powers communities sustainably without demanding ecological forgiveness."
                elif "hope" in row_quote.lower() and "peace" in row_quote.lower():
                    row_explanation = "Hope and mutual trust provide the stability communities need to sustain lasting peace."
                elif "activism" in row_quote.lower() or "self-care" in row_quote.lower():
                    row_explanation = "Sustaining long-term community action requires balancing dedicated advocacy with personal well-being."
                elif top_dom == "women_gender_empowerment":
                    row_explanation = "Investing in girls' education and women's leadership creates lasting progress for entire communities."
                elif top_dom == "climate_environment_nature":
                    row_explanation = "Mindful daily actions and sustainable choices protect our shared environment for future generations."
                elif top_dom == "quality_education_literacy":
                    row_explanation = "Sharing knowledge freely and fostering curiosity empowers people to shape their own futures."
                elif top_dom == "mental_health_mindfulness":
                    row_explanation = "Taking time to pause and care for your mental calm restores emotional resilience and empathy."
                else:
                    row_explanation = "True harmony begins when communities choose dialogue, fairness, and mutual respect over division."

            return {
                "quote": row_quote,
                "explanation": row_explanation,
            }
        return None

    def _emergency_failsafe(self, theme: str = "", event: dict | None = None) -> dict[str, Any]:
        """Generate a semantically aligned emergency failsafe quote for the given theme or event."""
        logger.warning("Using emergency domain-aligned failsafe quote.")
        top_domain = "peace_justice_humanity"

        if event and event.get("event"):
            ev_name = event["event"]
            ev_scores = detect_domain_scores(ev_name)
            if ev_scores:
                top_domain = max(ev_scores.items(), key=lambda x: x[1])[0]
            else:
                top_domain = "peace_justice_humanity"
        elif theme:
            top_domain = THEME_TO_DOMAIN_MAP.get(theme, "peace_justice_humanity")

        used_quotes = load_used_quotes(self._used_quotes_log)
        quote = ""
        explanation = ""

        if top_domain in EMERGENCY_DOMAIN_QUOTES:
            quotes_list = EMERGENCY_DOMAIN_QUOTES[top_domain]
            # Try to pick an unused emergency quote from the list
            chosen = None
            for candidate in quotes_list:
                cand_quote = sanitize_text(candidate["quote"])
                if cand_quote not in used_quotes:
                    chosen = candidate
                    break
            if not chosen:
                chosen_idx = len(used_quotes) % len(quotes_list)
                chosen = quotes_list[chosen_idx]
            quote = sanitize_text(chosen["quote"])
            explanation = sanitize_text(chosen["explanation"])

        else:
            quote = sanitize_text(self._emergency["quote"])
            explanation = sanitize_text(self._emergency["explanation"])

        mark_quote_used(quote, self._used_quotes_log)

        tpl = get_topic_fallback_template(top_domain, quote)

        context = sanitize_text(tpl["context"])
        foundation_conn = sanitize_text(tpl["foundation_connection"])
        cta = sanitize_text(tpl["cta"])
        hashtags = list(tpl["hashtags"])
        if event and event.get("event"):
            event_name = event["event"]
            event_tag = f"#{event_name.replace(' ', '').replace('&', 'And').replace('-', '')}"
            if event_tag not in hashtags:
                hashtags.insert(0, event_tag)

        return {
            "topic": top_domain.replace("_", " ").title(),
            "event_name": derive_fallback_event_name(theme, quote, context, event),
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
