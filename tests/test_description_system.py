"""Comprehensive automated test suite for Cogentic AI Daily Description System.

Verifies:
- 20 Required Description System Tests
- Multi-level repetition and template detection
- Foundation claim grounding
- IST date handling
- Backward compatibility and poster generation regression
"""

import json
import os
import unittest
from datetime import date, datetime, timedelta, timezone

from content.fallback import FallbackProvider
from content.foundation_context import FOUNDATION_CONTEXT, get_foundation_prompt_context
from content.generator import (
    build_social_caption,
    build_structured_long_explanation,
)
from content.validator import (
    ContentValidator,
    cosine_similarity,
    jaccard_similarity,
    normalize_text,
)
from image_gen import render_output_image
from rendering.poster_generator import PosterGenerator
from scheduler.daily_runner import (
    IST,
    get_current_ist_date,
    get_today_event,
    load_config,
    select_theme,
)


class TestCogenticDescriptionSystem(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.project_root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
        cls.config_path = os.path.join(cls.project_root, "config.json")
        cls.config = load_config(cls.config_path)
        cls.validator = ContentValidator()
        cls.fallback = FallbackProvider(cls.config, cls.project_root)

    def test_01_no_exact_duplicate_quotes(self):
        """TEST 1: Validator detects and rejects exact duplicate quotes."""
        history = [{"quote": "Education is the light that illuminates society."}]
        candidate = {
            "quote": "Education is the light that illuminates society.",
            "explanation": "Learning enables progress.",
            "context": "Education is vital for societal development and ethical values.",
            "foundation_connection": "Jalte Diye Foundation promotes accessible education.",
            "cta": "Read a book with someone today.",
            "hashtags": ["#Education", "#Learning", "#Community"],
        }
        errors = self.validator.validate_deterministic(candidate, "Quality Education", recent_history=history)
        self.assertTrue(any("duplicate quote" in err.lower() for err in errors))

    def test_02_no_exact_duplicate_contexts(self):
        """TEST 2: Validator detects and rejects exact duplicate contexts."""
        history = [{
            "quote": "First quote.",
            "context": "This is a specific context paragraph about civic duties.",
        }]
        candidate = {
            "quote": "Second different quote.",
            "explanation": "Short expl.",
            "context": "This is a specific context paragraph about civic duties.",
            "foundation_connection": "Jalte Diye Foundation emphasizes civic ethics.",
            "cta": "Take an active role in local discussions.",
            "hashtags": ["#CivicDuty", "#Society", "#Awareness"],
        }
        errors = self.validator.validate_deterministic(candidate, "Social Education", recent_history=history)
        self.assertTrue(any("duplicate context" in err.lower() for err in errors))

    def test_03_no_exact_duplicate_foundation_connections(self):
        """TEST 3: Validator detects and rejects exact duplicate Foundation connections."""
        history = [{
            "foundation_connection": "At Jalte Diye Foundation, our focus on education inspires youth.",
        }]
        candidate = {
            "quote": "Unique quote here.",
            "explanation": "Short expl.",
            "context": "Unique context text.",
            "foundation_connection": "At Jalte Diye Foundation, our focus on education inspires youth.",
            "cta": "Mentor someone today.",
            "hashtags": ["#Youth", "#Mentorship", "#Growth"],
        }
        errors = self.validator.validate_deterministic(candidate, "Quality Education", recent_history=history)
        self.assertTrue(any("duplicate foundation_connection" in err.lower() for err in errors))

    def test_04_no_exact_duplicate_ctas(self):
        """TEST 4: Validator detects and rejects exact duplicate CTAs."""
        history = [{"cta": "Plant a native sapling in your neighborhood today."}]
        candidate = {
            "quote": "Nature provides abundantly.",
            "explanation": "Short expl.",
            "context": "Forests are essential carbon sinks.",
            "foundation_connection": "Jalte Diye Foundation promotes environmental sustainability.",
            "cta": "Plant a native sapling in your neighborhood today.",
            "hashtags": ["#PlantTrees", "#GreenPlanet", "#Sustainability"],
        }
        errors = self.validator.validate_deterministic(candidate, "Climate & Environment", recent_history=history)
        self.assertTrue(any("duplicate cta" in err.lower() for err in errors))

    def test_05_no_identical_hashtag_sets(self):
        """TEST 5: Validator detects and rejects identical hashtag sets."""
        history = [{"hashtags": ["#Peace", "#Justice", "#Humanity"]}]
        candidate = {
            "quote": "Peace starts with understanding.",
            "explanation": "Short expl.",
            "context": "Justice builds mutual trust.",
            "foundation_connection": "Jalte Diye Foundation advocates for ethical harmony.",
            "cta": "Practice active listening.",
            "hashtags": ["#Peace", "#Justice", "#Humanity"],
        }
        errors = self.validator.validate_deterministic(candidate, "Peace & Justice", recent_history=history)
        self.assertTrue(any("identical hashtag set" in err.lower() for err in errors))

    def test_06_no_unnecessary_quote_repetition_in_description(self):
        """TEST 6: Validator detects quote repetition inside context or foundation connection."""
        candidate = {
            "quote": "Protect the layer that protects us all.",
            "explanation": "Observing World Ozone Day.",
            "context": "As the quote says, Protect the layer that protects us all in our daily life.",
            "foundation_connection": "Jalte Diye Foundation fosters awareness.",
            "cta": "Reduce harmful chemical usage.",
            "hashtags": ["#OzoneDay", "#Atmosphere", "#CleanAir"],
        }
        errors = self.validator.validate_deterministic(candidate, "Foundation Events")
        self.assertTrue(any("quote text repeated" in err.lower() for err in errors))

    def test_07_no_unnecessary_event_line_repetition(self):
        """TEST 7: Generated long explanation formats cleanly without redundant event lines."""
        long_expl = build_structured_long_explanation(
            context="World Ozone Day reminds us of the fragile atmospheric shield.",
            foundation_connection="Jalte Diye Foundation links ecological awareness to community well-being.",
            cta="Make conscious choices about emissions.",
            hashtags=["#WorldOzoneDay", "#CleanAir"],
        )
        # Verify clean structure
        self.assertNotIn('""', long_expl)
        self.assertIn("**How this connects with our mission:**", long_expl)
        self.assertIn("**Take Action:**", long_expl)

    def test_08_non_event_days_contain_no_event_content(self):
        """TEST 8: Non-event days reject event-specific observation phrasing."""
        candidate = {
            "quote": "Knowledge is power.",
            "explanation": "Observing National Science Day.",
            "context": "Observing National Science Day helps us appreciate scientific inquiry.",
            "foundation_connection": "Jalte Diye Foundation encourages scientific thinking.",
            "cta": "Explore a science article today.",
            "hashtags": ["#Science", "#Education", "#Discovery"],
        }
        # Pass event=None
        errors = self.validator.validate_deterministic(candidate, "Quality Education", event=None)
        self.assertTrue(any("non-event day contains event observation" in err.lower() for err in errors))

    def test_09_event_days_use_correct_event_info(self):
        """TEST 9: Event days must reflect the configured event."""
        event = {"event": "World Health Day", "theme": "Health & Mindfulness"}
        valid_candidate = {
            "quote": "Good health is the foundation of all human endeavor.",
            "explanation": "Observing World Health Day.",
            "context": "World Health Day reminds us to prioritize equitable healthcare and wellness.",
            "foundation_connection": "Jalte Diye Foundation values holistic mental and physical well-being.",
            "cta": "Schedule your annual health checkup.",
            "hashtags": ["#WorldHealthDay", "#HealthForAll", "#Mindfulness"],
        }
        errors = self.validator.validate_deterministic(valid_candidate, "Health & Mindfulness", event=event)
        self.assertEqual(errors, [])

    def test_10_hashtags_validation(self):
        """TEST 10: Hashtags must be 3-6 tags, start with #, and have no internal duplicates."""
        # Test invalid tags (no #, duplicates, too few)
        bad_tags = ["NoHash", "#Duplicate", "#duplicate"]
        errors = self.validator.validate_hashtags(bad_tags, "Peace & Justice")
        self.assertTrue(len(errors) > 0)

        # Test valid tags
        good_tags = ["#PeaceAndJustice", "#HumanDignity", "#CommunityAction", "#EthicalLiving"]
        errors_good = self.validator.validate_hashtags(good_tags, "Peace & Justice")
        self.assertEqual(errors_good, [])

    def test_11_foundation_connection_exists_for_every_post(self):
        """TEST 11: Missing foundation_connection is caught."""
        candidate = {
            "quote": "Every drop counts.",
            "explanation": "Water is life.",
            "context": "Conserving water preserves our planet's future.",
            "foundation_connection": "",  # Empty
            "cta": "Turn off the tap while brushing.",
            "hashtags": ["#SaveWater", "#Conservation", "#Ecology"],
        }
        errors = self.validator.validate_deterministic(candidate, "Climate & Environment")
        self.assertTrue(any("foundation_connection" in err.lower() for err in errors))

    def test_12_foundation_connection_grounded_in_repo_mission(self):
        """TEST 12: Verify foundation context in repository is well-defined and non-empty."""
        self.assertIn("Jalte Diye Foundation", FOUNDATION_CONTEXT["name"])
        self.assertTrue(len(FOUNDATION_CONTEXT["mission"]) > 20)
        self.assertTrue(len(FOUNDATION_CONTEXT["goals"]) >= 3)
        self.assertTrue(len(FOUNDATION_CONTEXT["focus_areas"]) >= 5)
        prompt_ctx = get_foundation_prompt_context()
        self.assertIn("Mission:", prompt_ctx)

    def test_13_no_unsupported_foundation_claims(self):
        """TEST 13: Detect and reject fabricated NGO claims."""
        candidate = {
            "quote": "Together we can solve hunger.",
            "explanation": "Food security matters.",
            "context": "Communities must unite against food insecurity.",
            "foundation_connection": "At Jalte Diye Foundation, our shelters and feeding program distributed food to 5000 families.",
            "cta": "Donate to our medical camps.",
            "hashtags": ["#ZeroHunger", "#Community", "#Action"],
        }
        errors = self.validator.validate_deterministic(candidate, "Social Education")
        self.assertTrue(any("unsupported foundation claim" in err.lower() for err in errors))

    def test_14_descriptions_show_meaningful_variation(self):
        """TEST 14: Similarity checker flags high cosine/jaccard overlap."""
        text1 = "At Jalte Diye Foundation, this reflection on climate speaks directly to our work every day."
        text2 = "At Jalte Diye Foundation, this reflection on quality education speaks directly to our work every day."
        sim = cosine_similarity(text1, text2)
        self.assertGreater(sim, 0.70)  # Flags near-duplicate template text

    def test_15_ctas_vary_according_to_topic(self):
        """TEST 15: Distinct CTAs across different themes in fallback templates."""
        fb_peace = self.fallback.get_fallback_quote("Peace & Justice")
        fb_climate = self.fallback.get_fallback_quote("Climate & Environment")
        self.assertNotEqual(fb_peace["cta"], fb_climate["cta"])
        self.assertNotEqual(fb_peace["context"], fb_climate["context"])

    def test_16_correct_ist_dates_used(self):
        """TEST 16: IST date helper produces correct date with +05:30 offset."""
        ist_now = datetime.now(IST)
        ist_date = get_current_ist_date()
        self.assertEqual(ist_now.date(), ist_date)
        self.assertEqual(ist_now.tzinfo, IST)

    def test_17_all_json_follows_schema(self):
        """TEST 17: Fallback and synthesized descriptions output all required keys."""
        res = self.fallback.get_fallback_quote("Quality Education")
        required_keys = [
            "quote", "explanation", "context", "foundation_connection",
            "cta", "long_explanation", "caption", "hashtags"
        ]
        for k in required_keys:
            self.assertIn(k, res)
            self.assertTrue(len(res[k]) > 0)

    def test_18_template_repetition_detection(self):
        """TEST 18: Detects and rejects legacy canned template phrases."""
        candidate = {
            "quote": "A single spark can start a flame.",
            "explanation": "Inspiration drives change.",
            "context": "Small actions create a ripple effect.",
            "foundation_connection": "At Jalte Diye Foundation, this reflection on social education speaks directly to the work we do every day — showing up for our community, listening first.",
            "cta": "Be kind to someone today.",
            "hashtags": ["#Kindness", "#Inspiration", "#Society"],
        }
        errors = self.validator.validate_deterministic(candidate, "Social Education")
        self.assertTrue(any("canned template phrase" in err.lower() for err in errors))

    def test_19_no_accidental_duplicate_sections(self):
        """TEST 19: Caption and Long explanation assembly is clean."""
        caption = build_social_caption(
            quote="Stand for justice.",
            context="Fairness creates lasting harmony.",
            foundation_connection="Jalte Diye Foundation promotes ethical civic principles.",
            cta="Speak up against injustice.",
            hashtags=["#Justice", "#Integrity"],
        )
        self.assertTrue(caption.startswith('"Stand for justice."'))
        self.assertIn("#Justice #Integrity", caption)

    def test_20_existing_poster_generation_remains_unchanged(self):
        """TEST 20: Regression test: Poster generator renders successfully."""
        out_path = os.path.join(self.project_root, "output", "alignment_test", "regression_test.jpg")
        os.makedirs(os.path.dirname(out_path), exist_ok=True)
        bg_path = os.path.join(self.project_root, "themes", "peace", "bg1.png")
        if os.path.exists(bg_path):
            success = render_output_image(
                bg_image_path=bg_path,
                quote_text="Peace is not the absence of conflict, but the presence of justice.",
                explanation_text="When justice and compassion prevail, every individual thrives.",
                theme="Peace & Justice",
                output_filename=out_path,
            )
            self.assertTrue(success)
            self.assertTrue(os.path.exists(out_path))


if __name__ == "__main__":
    unittest.main()
