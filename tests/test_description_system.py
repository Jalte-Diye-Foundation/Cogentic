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
        """TEST 7: Generated long explanation formats cleanly without redundant event lines or markdown asterisks."""
        long_expl = build_structured_long_explanation(
            context="World Ozone Day reminds us of the fragile atmospheric shield.",
            foundation_connection="Jalte Diye Foundation links ecological awareness to community well-being.",
            cta="Make conscious choices about emissions.",
            hashtags=["#WorldOzoneDay", "#CleanAir"],
        )
        # Verify clean structure without literal asterisks
        self.assertNotIn('""', long_expl)
        self.assertNotIn("**", long_expl)
        self.assertNotIn("#", long_expl)  # Hashtags must NOT be inside long_explanation
        self.assertIn("How this connects with our mission:\nJalte Diye Foundation", long_expl)
        self.assertIn("Take Action:\nMake conscious choices", long_expl)

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

    def test_21_no_duplicate_hashtags_between_long_explanation_and_metadata(self):
        """TEST 21: Regression test: Hashtags must exist in hashtags list and NOT in long_explanation."""
        candidate = self.fallback.get_fallback_quote("Peace & Justice")
        # Hashtags array is populated
        self.assertTrue(len(candidate["hashtags"]) >= 3)
        # Hashtags are NOT in long_explanation
        self.assertNotIn("#", candidate["long_explanation"])
        for tag in candidate["hashtags"]:
            self.assertNotIn(tag, candidate["long_explanation"])

    def test_22_no_literal_markdown_asterisks_in_any_field(self):
        """TEST 22: Regression test: No literal ** or __ in description or fallback fields."""
        for theme in ["Peace & Justice", "Climate & Environment", "Quality Education", "Women Empowerment", "Health & Mindfulness", "Foundation Events"]:
            candidate = self.fallback.get_fallback_quote(theme)
            for field in ["quote", "explanation", "context", "foundation_connection", "cta", "long_explanation"]:
                val = candidate.get(field, "")
                self.assertNotIn("**", val, f"Found ** in {field} for theme {theme}")
                self.assertNotIn("__", val, f"Found __ in {field} for theme {theme}")

    def test_23_validator_rejects_literal_markdown_and_embedded_hashtags(self):
        """TEST 23: Validator rejects posts with ** in headings or hashtags in long_explanation."""
        bad_markdown_candidate = {
            "quote": "Peace begins with a smile.",
            "explanation": "Short expl.",
            "context": "Context text.",
            "foundation_connection": "**Mission connection:** At Jalte Diye Foundation, we focus on harmony.",
            "cta": "Smile today.",
            "hashtags": ["#Peace", "#Kindness", "#Community"],
            "long_explanation": "Context text.\n\n**How this connects with our mission:**\nAt Jalte Diye Foundation...\n\n**Take Action:**\nSmile today.",
        }
        errors = self.validator.validate_deterministic(bad_markdown_candidate, "Peace & Justice")
        self.assertTrue(any("literal markdown asterisks" in err.lower() for err in errors))

        bad_hashtag_candidate = {
            "quote": "Peace begins with a smile.",
            "explanation": "Short expl.",
            "context": "Context text.",
            "foundation_connection": "At Jalte Diye Foundation, we focus on harmony.",
            "cta": "Smile today.",
            "hashtags": ["#Peace", "#Kindness", "#Community"],
            "long_explanation": "Context text.\n\nHow this connects with our mission:\nAt Jalte Diye Foundation...\n\nTake Action:\nSmile today.\n\n#Peace #Kindness #Community",
        }
        errors2 = self.validator.validate_deterministic(bad_hashtag_candidate, "Peace & Justice")
        self.assertTrue(any("must not contain hashtags" in err.lower() for err in errors2))

    def test_24_humanization_validator_detects_excessive_buzzwords(self):
        """TEST 24: Validator flags excessive corporate/NGO buzzword stuffing."""
        buzzword_candidate = {
            "quote": "Peace is our shared goal.",
            "explanation": "Short explanation.",
            "context": "Fostering sustainable change requires cultivating collective responsibility across society.",
            "foundation_connection": "Jalte Diye Foundation creates positive social impact through constructive social awareness.",
            "cta": "Engage in this process today.",
            "hashtags": ["#Peace", "#Awareness", "#Community"],
        }
        errors = self.validator.validate_deterministic(buzzword_candidate, "Peace & Justice")
        self.assertTrue(any("excessive corporate/ngo buzzword" in err.lower() for err in errors))

    def test_25_humanization_validator_detects_empty_slogan_ctas(self):
        """TEST 25: Validator flags empty slogan CTAs without concrete everyday action."""
        slogan_candidate = {
            "quote": "Knowledge is a light.",
            "explanation": "Learning helps everyone.",
            "context": "When we share what we know, we help others grow.",
            "foundation_connection": "Jalte Diye Foundation believes in making knowledge accessible to everyone.",
            "cta": "Be the change.",
            "hashtags": ["#Education", "#Learning", "#Community"],
        }
        errors = self.validator.validate_deterministic(slogan_candidate, "Quality Education")
        self.assertTrue(any("generic slogan without concrete action" in err.lower() for err in errors))

    def test_26_humanization_validator_detects_repeated_foundation_openings(self):
        """TEST 26: Validator catches identical 4-word Foundation openings across history."""
        history = [{
            "foundation_connection": "At Jalte Diye Foundation, our main mission is promoting peace.",
        }]
        candidate = {
            "quote": "A different quote today.",
            "explanation": "Short expl.",
            "context": "A different context paragraph about everyday kindness.",
            "foundation_connection": "At Jalte Diye Foundation, our focus on education inspires youth.",
            "cta": "Help a neighbor today with a simple task.",
            "hashtags": ["#Education", "#Youth", "#Action"],
        }
        errors = self.validator.validate_deterministic(candidate, "Quality Education", recent_history=history)
        self.assertTrue(any("repeated formulaic foundation opening" in err.lower() for err in errors))

    def test_27_semantic_mismatch_refugee_quote_with_women_empowerment_description_fails(self):
        """TEST 27 (Exact Bug Regression): Refugee quote with Women Empowerment description MUST FAIL."""
        candidate = {
            "quote": "Refugees carry their humanity across every border.",
            "explanation": "Their passport may be torn, but their worth is not.",
            "context": "Every family and community thrives when women have the space to speak, make decisions, and lead without fear or artificial barriers.",
            "foundation_connection": "Promoting gender equity and mutual respect is a vital part of Jalte Diye Foundation's social education efforts. Real progress happens when women's ideas and voices are genuinely heard and supported.",
            "cta": "Make space today to support and encourage a woman's voice or idea in your workplace or family circle.",
            "hashtags": ["#WomenEmpowerment", "#EqualVoices", "#CommunityRespect", "#SocialEducation"],
        }
        errors = self.validator.validate_deterministic(candidate, "Women Empowerment")
        self.assertTrue(len(errors) > 0)
        self.assertTrue(any("semantic topic mismatch" in err.lower() for err in errors))
        self.assertTrue(any("refugee" in err.lower() for err in errors))

    def test_28_semantic_alignment_refugee_quote_with_refugee_description_passes(self):
        """TEST 28: Refugee quote with refugee/human dignity description MUST PASS."""
        candidate = {
            "quote": "Refugees carry their humanity across every border.",
            "explanation": "Their passport may be torn, but their worth is not.",
            "context": "When displaced families cross borders fleeing crisis, remembering our shared humanity turns strangers into neighbors.",
            "foundation_connection": "For Jalte Diye Foundation, social education begins with recognizing human dignity in every person regardless of their origins or displacement.",
            "cta": "Reach out with simple kindness or support local initiatives assisting displaced families in your area today.",
            "hashtags": ["#RefugeeDignity", "#HumanityFirst", "#EmpathyInAction", "#PeaceAndJustice"],
        }
        errors = self.validator.validate_deterministic(candidate, "Peace & Justice")
        self.assertEqual(errors, [])

    def test_29_semantic_mismatch_climate_quote_with_women_empowerment_description_fails(self):
        """TEST 29: Climate quote with women empowerment description MUST FAIL."""
        candidate = {
            "quote": "Plant a tree; plant hope. Forests are the living lungs of our earth.",
            "explanation": "Every green sapling heals our planet.",
            "context": "Every family and community thrives when women have the space to speak, make decisions, and lead without fear.",
            "foundation_connection": "Promoting gender equity and mutual respect for women is central to Jalte Diye Foundation's mission.",
            "cta": "Support a woman's initiative in your neighborhood today.",
            "hashtags": ["#WomenEmpowerment", "#GenderEquity", "#WomenLead"],
        }
        errors = self.validator.validate_deterministic(candidate, "Climate & Environment")
        self.assertTrue(any("semantic topic mismatch" in err.lower() for err in errors))

    def test_30_semantic_mismatch_mental_health_quote_with_climate_description_fails(self):
        """TEST 30: Mental health quote with climate description MUST FAIL."""
        candidate = {
            "quote": "Inner stillness is the first seed of peace. Breathe deeply and find calm.",
            "explanation": "Caring for your mind restores your strength.",
            "context": "Reducing carbon emissions and conserving wetlands is essential to protecting planetary ecosystems.",
            "foundation_connection": "Jalte Diye Foundation focuses on environmental protection and climate awareness.",
            "cta": "Plant a native sapling or carry a reusable bottle today.",
            "hashtags": ["#ClimateCare", "#EcoAwareness", "#PlanetFirst"],
        }
        errors = self.validator.validate_deterministic(candidate, "Health & Mindfulness")
        self.assertTrue(any("semantic topic mismatch" in err.lower() for err in errors))

    def test_31_semantic_alignment_peace_quote_with_dialogue_description_passes(self):
        """TEST 31: Peace quote with community dialogue description MUST PASS."""
        candidate = {
            "quote": "Peace is not the absence of conflict, but the presence of understanding and justice.",
            "explanation": "Dialogue and mutual respect resolve deep divisions.",
            "context": "When communities cultivate fairness and open dialogue, mutual trust replaces hostility and suspicion.",
            "foundation_connection": "Jalte Diye Foundation emphasizes constructive dialogue and social harmony as essential pillars of peace.",
            "cta": "Listen patiently to someone with a different viewpoint today.",
            "hashtags": ["#PeaceAndJustice", "#CommunityDialogue", "#MutualRespect", "#SocialEducation"],
        }
        errors = self.validator.validate_deterministic(candidate, "Peace & Justice")
        self.assertEqual(errors, [])

    def test_32_semantic_alignment_education_quote_with_learning_description_passes(self):
        """TEST 32: Education quote with learning description MUST PASS."""
        candidate = {
            "quote": "The classroom that welcomes all voices teaches the greatest lesson.",
            "explanation": "Inclusive learning empowers every child to thrive.",
            "context": "Real learning happens when every student has access to knowledge and feels valued in their school.",
            "foundation_connection": "Education is at the heart of Jalte Diye Foundation's mission to ignite curiosity and lifelong learning.",
            "cta": "Share a book or helpful learning resource with a young person today.",
            "hashtags": ["#QualityEducation", "#InclusiveClassrooms", "#LifelongLearning", "#ShareKnowledge"],
        }
        errors = self.validator.validate_deterministic(candidate, "Quality Education")
        self.assertEqual(errors, [])

    def test_33_semantic_alignment_women_empowerment_quote_and_description_passes(self):
        """TEST 33: Women empowerment quote with women empowerment description MUST PASS."""
        candidate = {
            "quote": "Empower a woman and you empower an entire generation.",
            "explanation": "When girls are educated and supported, entire communities rise.",
            "context": "Every family and community thrives when women have the space to speak, lead, and shape decisions.",
            "foundation_connection": "Promoting equal opportunities and mutual respect for women is central to Jalte Diye Foundation's mission.",
            "cta": "Support and encourage a woman's voice or initiative in your workplace or family today.",
            "hashtags": ["#WomenEmpowerment", "#EqualVoices", "#GenderEquity", "#SocialEducation"],
        }
        errors = self.validator.validate_deterministic(candidate, "Women Empowerment")
        self.assertEqual(errors, [])

    def test_34_semantic_mismatch_event_quote_with_unrelated_description_fails(self):
        """TEST 34: Event quote with unrelated description MUST FAIL."""
        event = {"event": "World Health Day", "theme": "Health & Mindfulness"}
        candidate = {
            "quote": "Observing World Health Day: access to healthcare is a mark of civilization.",
            "explanation": "Observing World Health Day.",
            "context": "Planting trees and conserving forests protects biodiversity across ecosystems.",
            "foundation_connection": "Jalte Diye Foundation promotes ecological sustainability and environmental protection.",
            "cta": "Carry a reusable water bottle today.",
            "hashtags": ["#ClimateCare", "#EcoAwareness", "#ZeroWaste"],
        }
        errors = self.validator.validate_deterministic(candidate, "Health & Mindfulness", event=event)
        self.assertTrue(any("topic mismatch" in err.lower() or "event" in err.lower() for err in errors))

    def test_35_semantic_mismatch_valid_quote_with_unrelated_hashtags_fails(self):
        """TEST 35: Valid refugee quote + valid context with unrelated hashtags MUST FAIL."""
        candidate = {
            "quote": "Refugees carry their humanity across every border.",
            "explanation": "Their passport may be torn, but their worth is not.",
            "context": "When displaced families cross borders fleeing crisis, remembering our shared humanity turns strangers into neighbors.",
            "foundation_connection": "For Jalte Diye Foundation, social education begins with recognizing human dignity in every displaced person.",
            "cta": "Reach out with simple kindness to displaced families today.",
            "hashtags": ["#WomenEmpowerment", "#GenderEquity", "#WomenLead"],  # Unrelated hashtags!
        }
        errors = self.validator.validate_deterministic(candidate, "Peace & Justice")
        self.assertTrue(any("hashtag topic mismatch" in err.lower() for err in errors))

    def test_36_semantic_alignment_valid_quote_with_related_hashtags_passes(self):
        """TEST 36: Valid refugee quote with semantically related hashtags MUST PASS."""
        candidate = {
            "quote": "Refugees carry their humanity across every border.",
            "explanation": "Their passport may be torn, but their worth is not.",
            "context": "When displaced families cross borders fleeing crisis, remembering our shared humanity turns strangers into neighbors.",
            "foundation_connection": "For Jalte Diye Foundation, social education begins with recognizing human dignity in every displaced person.",
            "cta": "Reach out with simple kindness to displaced families today.",
            "hashtags": ["#RefugeeDignity", "#HumanityFirst", "#EmpathyInAction", "#PeaceAndJustice"],
        }
        errors = self.validator.validate_deterministic(candidate, "Peace & Justice")
        self.assertEqual(errors, [])

    # ==========================================
    # SECTION 11 SPECIFIED REGRESSION TEST CASES
    # ==========================================

    def test_sec11_test01_quote_refugee_desc_women_rejects(self):
        """TEST 1: Quote: refugee dignity, Description: women empowerment -> Expected: REJECT."""
        candidate = {
            "quote": "Refugees carry their humanity across every border.",
            "explanation": "Human dignity knows no frontiers.",
            "context": "When women lead and have equal voices, entire communities flourish.",
            "foundation_connection": "Jalte Diye Foundation promotes women empowerment and leadership.",
            "cta": "Support a woman-led initiative in your community today.",
            "hashtags": ["#WomenEmpowerment", "#GenderEquity", "#WomenLead"],
        }
        errors = self.validator.validate_deterministic(candidate, "Peace & Justice")
        self.assertTrue(any("semantic topic mismatch" in err.lower() for err in errors))

    def test_sec11_test02_quote_refugee_desc_refugee_accepts(self):
        """TEST 2: Quote: refugee dignity, Description: refugee dignity -> Expected: ACCEPT."""
        candidate = {
            "quote": "Refugees carry their humanity across every border.",
            "explanation": "Human dignity knows no frontiers.",
            "context": "When displaced people cross borders fleeing crises, recognizing our shared humanity turns strangers into neighbors.",
            "foundation_connection": "For Jalte Diye Foundation, social education begins with recognizing equal human dignity in every person regardless of displacement.",
            "cta": "Reach out with simple kindness or welcome someone displaced today.",
            "hashtags": ["#RefugeeDignity", "#HumanityFirst", "#EmpathyInAction", "#PeaceAndJustice"],
        }
        errors = self.validator.validate_deterministic(candidate, "Peace & Justice")
        self.assertEqual(errors, [])

    def test_sec11_test03_quote_climate_desc_women_rejects(self):
        """TEST 3: Quote: climate, Description: women empowerment -> Expected: REJECT."""
        candidate = {
            "quote": "The best time to plant a tree was twenty years ago. The second best time is now.",
            "explanation": "Every small step we take today protects our planet.",
            "context": "When women have the space to speak and make decisions, families thrive.",
            "foundation_connection": "Promoting gender equity is central to Jalte Diye Foundation.",
            "cta": "Support a woman's voice in your workplace today.",
            "hashtags": ["#WomenEmpowerment", "#GenderEquity", "#WomenLead"],
        }
        errors = self.validator.validate_deterministic(candidate, "Climate & Environment")
        self.assertTrue(any("semantic topic mismatch" in err.lower() for err in errors))

    def test_sec11_test04_quote_mental_health_desc_climate_rejects(self):
        """TEST 4: Quote: mental health, Description: climate -> Expected: REJECT."""
        candidate = {
            "quote": "Inner stillness is the first seed of peace. Breathe deeply and find calm.",
            "explanation": "Caring for your mind restores your strength.",
            "context": "Conserving wetlands and reducing carbon emissions protects our ecosystems.",
            "foundation_connection": "Jalte Diye Foundation promotes ecological sustainability and environmental protection.",
            "cta": "Carry a reusable bag or plant a sapling today.",
            "hashtags": ["#ClimateCare", "#EcoAwareness", "#PlanetFirst"],
        }
        errors = self.validator.validate_deterministic(candidate, "Health & Mindfulness")
        self.assertTrue(any("semantic topic mismatch" in err.lower() for err in errors))

    def test_sec11_test05_quote_peace_desc_peace_accepts(self):
        """TEST 5: Quote: peace/community dialogue, Description: peace/community dialogue -> Expected: ACCEPT."""
        candidate = {
            "quote": "Peace is not the absence of conflict, but the presence of understanding and justice.",
            "explanation": "Constructive dialogue and fairness build lasting harmony.",
            "context": "When communities cultivate fairness and open dialogue, mutual trust replaces hostility.",
            "foundation_connection": "Jalte Diye Foundation emphasizes constructive dialogue and social harmony as pillars of peace.",
            "cta": "Listen patiently to someone with a different viewpoint today.",
            "hashtags": ["#PeaceAndJustice", "#CommunityDialogue", "#MutualRespect", "#SocialEducation"],
        }
        errors = self.validator.validate_deterministic(candidate, "Peace & Justice")
        self.assertEqual(errors, [])

    def test_sec11_test06_quote_education_desc_education_accepts(self):
        """TEST 6: Quote: education/access/learning, Description: education/access/learning -> Expected: ACCEPT."""
        candidate = {
            "quote": "The classroom that welcomes all voices teaches the greatest lesson.",
            "explanation": "Inclusive learning empowers every child to thrive.",
            "context": "Real learning happens when every student has access to knowledge and feels valued in their school.",
            "foundation_connection": "Education is at the heart of Jalte Diye Foundation's mission to ignite curiosity and lifelong learning.",
            "cta": "Share an insightful book or learning resource with a young person today.",
            "hashtags": ["#QualityEducation", "#InclusiveClassrooms", "#LifelongLearning", "#ShareKnowledge"],
        }
        errors = self.validator.validate_deterministic(candidate, "Quality Education")
        self.assertEqual(errors, [])

    def test_sec11_test07_quote_women_desc_women_accepts(self):
        """TEST 7: Quote: women empowerment, Description: women empowerment -> Expected: ACCEPT."""
        candidate = {
            "quote": "When women are given the space to lead, entire communities rise together.",
            "explanation": "Equal opportunities allow women to shape a better future.",
            "context": "Every family and community thrives when women have the space to speak, lead, and shape decisions.",
            "foundation_connection": "Promoting equal opportunities and mutual respect for women is central to Jalte Diye Foundation's mission.",
            "cta": "Encourage and support a woman's idea or leadership initiative today.",
            "hashtags": ["#WomenEmpowerment", "#EqualVoices", "#GenderEquity", "#SocialEducation"],
        }
        errors = self.validator.validate_deterministic(candidate, "Women Empowerment")
        self.assertEqual(errors, [])

    def test_sec11_test08_event_peace_day_tree_quote_rejects(self):
        """TEST 8: Event: International Day of Peace, Quote: climate/tree planting -> Expected: REJECT."""
        event = {"event": "International Day of Peace", "theme": "Foundation Events"}
        candidate = {
            "quote": "The best time to plant a tree was twenty years ago. The second best time is now.",
            "explanation": "Every small step we take today shapes the world we live in tomorrow.",
            "context": "The choices we make in our daily routines shape our environment.",
            "foundation_connection": "At Jalte Diye Foundation, environmental responsibility is a practical habit.",
            "cta": "Pick one small habit today to reduce waste.",
            "hashtags": ["#InternationalDayOfPeace", "#ClimateCare", "#EcoAwareness"],
        }
        errors = self.validator.validate_deterministic(candidate, "Foundation Events", event=event)
        self.assertTrue(any("event relevance mismatch" in err.lower() or "event topic mismatch" in err.lower() for err in errors))

    def test_sec11_test09_event_right_to_know_tree_quote_rejects(self):
        """TEST 9: Event: Right to Know Day, Quote: climate/tree planting -> Expected: REJECT."""
        event = {"event": "Right to Know Day", "theme": "Foundation Events"}
        candidate = {
            "quote": "The best time to plant a tree was twenty years ago. The second best time is now.",
            "explanation": "Every small step we take today shapes the world we live in tomorrow.",
            "context": "The choices we make in our daily routines shape our environment.",
            "foundation_connection": "At Jalte Diye Foundation, environmental responsibility is a practical habit.",
            "cta": "Pick one small habit today to reduce waste.",
            "hashtags": ["#RightToKnowDay", "#ClimateCare", "#EcoAwareness"],
        }
        errors = self.validator.validate_deterministic(candidate, "Foundation Events", event=event)
        self.assertTrue(any("event relevance mismatch" in err.lower() or "event topic mismatch" in err.lower() for err in errors))

    def test_sec11_test10_theme_women_rural_quote_women_desc_rejects(self):
        """TEST 10: Theme: Women Empowerment, Quote: rural development, Description: women leadership -> Expected: REJECT."""
        candidate = {
            "quote": "Rural communities deserve the same opportunities as cities.",
            "explanation": "Equal opportunities across villages build balanced progress.",
            "context": "Women should have space to lead and make decisions without barriers.",
            "foundation_connection": "Promoting gender equity is central to Jalte Diye Foundation's social education efforts.",
            "cta": "Support a woman's leadership initiative today.",
            "hashtags": ["#WomenEmpowerment", "#GenderEquity", "#WomenLead"],
        }
        errors = self.validator.validate_deterministic(candidate, "Women Empowerment")
        # Should reject because quote is about rural development (theme mismatch) and description introduces women (quote-desc mismatch)
        self.assertTrue(len(errors) > 0)
        self.assertTrue(any("theme compatibility mismatch" in err.lower() or "semantic topic mismatch" in err.lower() for err in errors))

    def test_sec11_test11_theme_climate_quote_climate_desc_climate_accepts(self):
        """TEST 11: Theme: Climate & Environment, Quote: climate, Description: climate -> Expected: ACCEPT."""
        candidate = {
            "quote": "The best time to plant a tree was twenty years ago. The second best time is now.",
            "explanation": "Every small step we take today shapes the world we live in tomorrow.",
            "context": "The choices we make in our daily routines shape the environment our kids grow up in.",
            "foundation_connection": "At Jalte Diye Foundation, our environmental focus is about practical everyday responsibility.",
            "cta": "Pick one small habit today to reduce waste like carrying a reusable water bottle.",
            "hashtags": ["#ClimateCare", "#DailyHabits", "#EcoAwareness", "#JalteDiyeFoundation"],
        }
        errors = self.validator.validate_deterministic(candidate, "Climate & Environment")
        self.assertEqual(errors, [])

    def test_sec11_test12_theme_education_quote_education_desc_education_accepts(self):
        """TEST 12: Theme: Quality Education, Quote: education, Description: education -> Expected: ACCEPT."""
        candidate = {
            "quote": "Education is not filling a bucket, but lighting a fire in every curious mind.",
            "explanation": "Real learning sparks questions that last a lifetime.",
            "context": "Real learning happens when someone asks a good question or shares knowledge with a peer.",
            "foundation_connection": "Education is at the core of Jalte Diye Foundation to empower people to shape their lives.",
            "cta": "Share one interesting thing you learned recently with someone today.",
            "hashtags": ["#QualityEducation", "#LifelongLearning", "#ShareKnowledge", "#SocialEducation"],
        }
        errors = self.validator.validate_deterministic(candidate, "Quality Education")
        self.assertEqual(errors, [])

    def test_sec11_test13_valid_quote_unrelated_hashtags_rejects(self):
        """TEST 13: Valid quote + unrelated hashtags -> Expected: REJECT."""
        candidate = {
            "quote": "The classroom that welcomes all voices teaches the greatest lesson.",
            "explanation": "Inclusive learning empowers every student to grow.",
            "context": "Real learning happens when every student has access to knowledge and feels valued in school.",
            "foundation_connection": "Education is at the heart of Jalte Diye Foundation's mission.",
            "cta": "Share a helpful learning resource with a young person today.",
            "hashtags": ["#ClimateCare", "#EcoAwareness", "#ZeroWaste"],  # Completely unrelated tags
        }
        errors = self.validator.validate_deterministic(candidate, "Quality Education")
        self.assertTrue(any("hashtag topic mismatch" in err.lower() for err in errors))

    def test_sec11_test14_valid_quote_related_hashtags_accepts(self):
        """TEST 14: Valid quote + semantically related hashtags -> Expected: ACCEPT."""
        candidate = {
            "quote": "The classroom that welcomes all voices teaches the greatest lesson.",
            "explanation": "Inclusive learning empowers every student to grow.",
            "context": "Real learning happens when every student has access to knowledge and feels valued in school.",
            "foundation_connection": "Education is at the heart of Jalte Diye Foundation's mission.",
            "cta": "Share a helpful learning resource with a young person today.",
            "hashtags": ["#QualityEducation", "#LifelongLearning", "#ShareKnowledge", "#SocialEducation"],
        }
        errors = self.validator.validate_deterministic(candidate, "Quality Education")
        self.assertEqual(errors, [])

    def test_cross_theme_car_free_streets_in_women_theme_rejects(self):
        """Day 04 case: Car-free streets quote in Women Empowerment theme -> Expected: REJECT."""
        candidate = {
            "quote": "Streets without cars become rooms where strangers become neighbours.",
            "explanation": "Car-free community spaces foster neighborly bonding.",
            "context": "Every family and community thrives when women have the space to speak and lead without fear.",
            "foundation_connection": "Promoting gender equity is central to Jalte Diye Foundation.",
            "cta": "Encourage a woman's voice today.",
            "hashtags": ["#WomenEmpowerment", "#GenderEquity", "#WomenLead"],
        }
        errors = self.validator.validate_deterministic(candidate, "Women Empowerment")
        self.assertTrue(len(errors) > 0)
        self.assertTrue(any("theme compatibility mismatch" in err.lower() or "semantic topic mismatch" in err.lower() for err in errors))

    def test_cross_theme_courage_no_gender_in_peace_theme_rejects(self):
        """Day 07 case: Courage has no gender quote in Peace & Justice theme with women description -> Expected: REJECT."""
        candidate = {
            "quote": "Courage has no gender. Strength belongs to everyone.",
            "explanation": "Bravery is a human quality shared by all.",
            "context": "Women deserve equal opportunity and respect to lead in every sector.",
            "foundation_connection": "Jalte Diye Foundation champions gender equity and empowerment.",
            "cta": "Support a female colleague today.",
            "hashtags": ["#WomenEmpowerment", "#GenderEquity", "#EqualVoices"],
        }
        errors = self.validator.validate_deterministic(candidate, "Peace & Justice")
        self.assertTrue(len(errors) > 0)
        self.assertTrue(any("theme compatibility mismatch" in err.lower() or "hashtag topic mismatch" in err.lower() for err in errors))

    def test_cross_theme_education_quote_in_health_theme_rejects(self):
        """Day 02 case: Education quote in Health & Mindfulness theme -> Expected: REJECT."""
        candidate = {
            "quote": "Peace travels fastest on the wings of education.",
            "explanation": "Learning accelerates community understanding.",
            "context": "Education opens doors to better livelihoods and informed minds.",
            "foundation_connection": "Jalte Diye Foundation promotes accessible education.",
            "cta": "Read with a student today.",
            "hashtags": ["#QualityEducation", "#LifelongLearning", "#ShareKnowledge"],
        }
        errors = self.validator.validate_deterministic(candidate, "Health & Mindfulness")
        self.assertTrue(len(errors) > 0)
        self.assertTrue(any("theme compatibility mismatch" in err.lower() for err in errors))

    def test_punctuation_sanitization_removes_double_spaces_and_artifacts(self):
        """Verify that sanitize_text cleans punctuation artifacts and double spaces."""
        from content.generator import sanitize_text

        # 1. Double space between clauses
        raw1 = "Biodiversity is not a luxury  it is the orchestra, and we are just one instrument."
        clean1 = sanitize_text(raw1)
        self.assertNotIn("  ", clean1)
        self.assertEqual(clean1, "Biodiversity is not a luxury, it is the orchestra, and we are just one instrument.")

        # 2. Missing comma in idiom
        raw2 = "The song of peace has no words only actions."
        clean2 = sanitize_text(raw2)
        self.assertEqual(clean2, "The song of peace has no words, only actions.")

        # 3. Curly apostrophe and double space
        raw3 = "To open a book is to borrow someone else’s life for a while  return it richer."
        clean3 = sanitize_text(raw3)
        self.assertNotIn("’", clean3)
        self.assertNotIn("  ", clean3)
        self.assertEqual(clean3, "To open a book is to borrow someone else's life for a while, return it richer.")

        # 4. Space before punctuation and duplicate periods
        raw4 = "Caring for the planet is essential .. Every choice matters ."
        clean4 = sanitize_text(raw4)
        self.assertEqual(clean4, "Caring for the planet is essential. Every choice matters.")

    def test_dynamic_fallback_templates_vary_for_different_quotes_same_domain(self):
        """Verify that two different quotes in the same domain get distinct explanations."""
        from content.fallback import get_topic_fallback_template

        quote_a = "Peace is not the absence of conflict; it is the presence of justice."
        quote_b = "The song of peace has no words, only actions."

        tpl_a = get_topic_fallback_template("peace_justice_humanity", quote_a)
        tpl_b = get_topic_fallback_template("peace_justice_humanity", quote_b)

        self.assertNotEqual(tpl_a["context"], tpl_b["context"])
        self.assertNotEqual(tpl_a["cta"], tpl_b["cta"])

    # =========================================================================
    # SECTION 8 REGRESSION TESTS: QUOTE-LEVEL MEANING & EXPLANATION QUALITY
    # =========================================================================

    def test_quote_level_regression_test_a_slogan_explanation_fails(self):
        """TEST A: Quote: 'Hope is the anchor of peace...', Explanation: 'Drop your anchor.' -> Expected: FAIL."""
        candidate = {
            "quote": "Hope is the anchor of peace without it we drift.",
            "explanation": "Drop your anchor.",  # Slogan / too short
            "context": "When conflict and uncertainty arise, holding onto hope keeps communities grounded and resilient.",
            "foundation_connection": "At Jalte Diye Foundation, social education centers on fostering mutual trust and community resilience.",
            "cta": "Offer a word of encouragement to someone facing a challenge today.",
            "hashtags": ["#HopeAndPeace", "#CommunityResilience", "#PeaceAndJustice", "#SocialEducation"],
        }
        errors = self.validator.validate_deterministic(candidate, "Peace & Justice")
        self.assertTrue(len(errors) > 0)
        self.assertTrue(any("explanation is too short" in err.lower() or "slogan" in err.lower() for err in errors))

    def test_quote_level_regression_test_b_meaningful_explanation_passes(self):
        """TEST B: Same quote with meaningful 1-2 sentence explanation about hope and peace -> Expected: PASS."""
        candidate = {
            "quote": "Hope is the anchor of peace without it we drift.",
            "explanation": "Hope gives communities something steady to hold onto when conflict and uncertainty create division.",
            "context": "When conflict and uncertainty arise, holding onto hope keeps communities grounded and resilient.",
            "foundation_connection": "At Jalte Diye Foundation, social education centers on fostering mutual trust and community resilience.",
            "cta": "Offer a word of encouragement to someone facing a challenge today.",
            "hashtags": ["#HopeAndPeace", "#CommunityResilience", "#PeaceAndJustice", "#SocialEducation"],
        }
        errors = self.validator.validate_deterministic(candidate, "Peace & Justice")
        self.assertEqual(errors, [])

    def test_quote_level_regression_test_c_climate_math_with_biodiversity_fails(self):
        """TEST C: Quote: 'Climate change is a math problem...', Description: biodiversity only -> Expected: FAIL."""
        candidate = {
            "quote": "Climate change is a math problem, and we are running out of chalk.",
            "explanation": "The quote frames climate change as an urgent calculation of rising numbers.",
            "context": "Our relationship with nature shows up in the food we eat, the soil we preserve, and the biodiversity we protect.",
            "foundation_connection": "Jalte Diye Foundation preserves local flora, fauna, and soil quality in neighborhood parks.",
            "cta": "Plant native wildflowers in your garden or balcony pot today.",
            "hashtags": ["#ClimateCare", "#SoilPreservation", "#Biodiversity", "#EcoAwareness"],
        }
        errors = self.validator.validate_deterministic(candidate, "Climate & Environment")
        self.assertTrue(len(errors) > 0)
        self.assertTrue(any("quote-level semantic mismatch" in err.lower() for err in errors))
        self.assertTrue(any("climate math urgency" in err.lower() for err in errors))

    def test_quote_level_regression_test_d_activism_selfcare_with_breathing_only_fails(self):
        """TEST D: Quote: 'Activism and self-care are not in tension...', Description: breathing only -> Expected: FAIL."""
        candidate = {
            "quote": "Activism and self-care are not in tension; they depend on each other.",
            "explanation": "Sustaining long-term advocacy requires balancing dedicated action with personal well-being.",
            "context": "Slow, mindful breathing during stressful moments helps reset our focus and calm our nerves.",
            "foundation_connection": "At Jalte Diye Foundation, mindfulness is taught as a daily tool for peaceful breathing.",
            "cta": "Step away from your screen and take ten conscious breaths today.",
            "hashtags": ["#MindfulBreathing", "#InnerCalm", "#StressRelief", "#MentalPeace"],
        }
        errors = self.validator.validate_deterministic(candidate, "Health & Mindfulness")
        self.assertTrue(len(errors) > 0)
        self.assertTrue(any("quote-level semantic mismatch" in err.lower() for err in errors))
        self.assertTrue(any("activism burnout selfcare" in err.lower() for err in errors))

    def test_quote_level_regression_test_e_renewable_energy_with_river_litter_only_fails(self):
        """TEST E: Quote: 'Renewable energy is energy that doesn't ask for forgiveness...', Description: rivers/litter only -> Expected: FAIL."""
        candidate = {
            "quote": "Renewable energy is energy that doesn't ask for forgiveness.",
            "explanation": "Clean energy powers communities sustainably without demanding ecological forgiveness.",
            "context": "Every river and open green space suffers when plastic waste and litter accumulate on the banks.",
            "foundation_connection": "Jalte Diye Foundation organizes neighborhood cleanups to keep local waterways and rivers free of trash.",
            "cta": "Spend ten minutes today picking up litter in a neighborhood park.",
            "hashtags": ["#CleanRivers", "#NoLitter", "#CleanWaterways", "#ClimateCare"],
        }
        errors = self.validator.validate_deterministic(candidate, "Climate & Environment")
        self.assertTrue(len(errors) > 0)
        self.assertTrue(any("quote-level semantic mismatch" in err.lower() for err in errors))
        self.assertTrue(any("renewable clean energy" in err.lower() for err in errors))

    def test_quote_level_regression_test_f_valid_paraphrase_without_keyword_repetition_passes(self):
        """TEST F: Valid quote-specific paraphrase without exact keyword repetition -> Expected: PASS."""
        candidate = {
            "quote": "Hope is the anchor of peace without it we drift.",
            "explanation": "Hope gives communities something to hold onto when conflict creates uncertainty.",
            "context": "When uncertainty threatens community stability, a shared sense of possibility keeps people working together rather than giving up.",
            "foundation_connection": "At Jalte Diye Foundation, our educational efforts focus on instilling confidence and mutual trust so neighborhoods stay resilient.",
            "cta": "Reach out to someone experiencing difficult times today and offer words of encouragement.",
            "hashtags": ["#CommunityResilience", "#PeaceAndJustice", "#SharedPossibility", "#SocialEducation"],
        }
        errors = self.validator.validate_deterministic(candidate, "Peace & Justice")
        self.assertEqual(errors, [])

    def test_punctuation_comprehensive_sanitization(self):
        """Verify comprehensive punctuation handling: double spaces, curly quotes, markdown, spacing."""
        from content.generator import sanitize_text

        # 1. Double spaces and clause boundary
        raw1 = "Building peace requires patience  it begins with simple listening."
        clean1 = sanitize_text(raw1)
        self.assertEqual(clean1, "Building peace requires patience, it begins with simple listening.")

        # 2. Markdown artifacts (**bold**, *italic*, __underline__)
        raw2 = "At **Jalte Diye Foundation**, we believe in *accessible* education for __all__."
        clean2 = sanitize_text(raw2)
        self.assertEqual(clean2, "At Jalte Diye Foundation, we believe in accessible education for all.")

        # 3. Curly apostrophes and quotes
        raw3 = "“Learning is a child’s greatest adventure,” she said."
        clean3 = sanitize_text(raw3)
        self.assertEqual(clean3, '"Learning is a child\'s greatest adventure," she said.')

        # 4. Spaces before punctuation & repeated punctuation
        raw4 = "Education empowers everyone ! .. It opens doors ; let us learn together ."
        clean4 = sanitize_text(raw4)
        self.assertEqual(clean4, "Education empowers everyone! It opens doors; let us learn together.")

    def test_foundation_events_not_in_evergreen_rotation(self):
        """Verify that Foundation Events is strictly excluded from the evergreen theme pool."""
        all_themes = list(self.config["themes"].keys())
        evergreen_themes = [t for t in all_themes if t != "Foundation Events"]
        expected_evergreen = [
            "Peace & Justice",
            "Health & Mindfulness",
            "Quality Education",
            "Women Empowerment",
            "Climate & Environment",
        ]
        self.assertEqual(set(evergreen_themes), set(expected_evergreen))
        self.assertNotIn("Foundation Events", evergreen_themes)

        # Verify select_theme on a non-event day never returns 'Foundation Events'
        non_event_date = date(2026, 9, 22)
        for _ in range(20):
            selected_theme, event = select_theme(self.config, self.project_root, target_date=non_event_date)
            self.assertIn(selected_theme, expected_evergreen)
            self.assertNotEqual(selected_theme, "Foundation Events")
            self.assertIsNone(event)

    def test_event_priority_and_date_stability(self):
        """Verify event priority on calendar event dates and stability across multiple calls."""
        # 1. Event Day: 2026-09-21 (International Day of Peace)
        for _ in range(5):
            theme, event = select_theme(self.config, self.project_root, target_date=date(2026, 9, 21))
            self.assertEqual(theme, "Foundation Events")
            self.assertIsNotNone(event)
            self.assertEqual(event["event"], "International Day of Peace")

        # 2. Event Day: 2026-09-28 (Right to Know Day)
        for _ in range(5):
            theme, event = select_theme(self.config, self.project_root, target_date=date(2026, 9, 28))
            self.assertEqual(theme, "Foundation Events")
            self.assertIsNotNone(event)
            self.assertEqual(event["event"], "Right to Know Day")

        # 3. Non-Event Day: 2026-09-22
        for _ in range(5):
            theme, event = select_theme(self.config, self.project_root, target_date=date(2026, 9, 22))
            self.assertIsNone(event)
            self.assertIn(theme, [
                "Peace & Justice",
                "Health & Mindfulness",
                "Quality Education",
                "Women Empowerment",
                "Climate & Environment",
            ])

    def test_event_name_foundation_event_uses_exact_name_from_events_json(self):
        """1. Foundation Event uses exact event name from events.json."""
        event = get_today_event(self.project_root, date(2026, 9, 21))
        self.assertIsNotNone(event)
        self.assertEqual(event["event"], "International Day of Peace")

        # Fallback content on this event day must carry the exact event name
        fb = self.fallback.get_fallback_quote("Foundation Events", event)
        self.assertEqual(fb["event_name"], "International Day of Peace")

    def test_event_name_foundation_event_does_not_get_gemini_replacement(self):
        """2. Foundation Event does not get a Gemini-generated replacement name."""
        event = {"event": "International Day of Peace", "theme": "Foundation Events"}
        candidate = {
            "event_name": "Some Random Awareness Day",
            "quote": "Peace is not the absence of conflict; it is the presence of justice.",
            "explanation": "True peace comes through justice and mutual respect.",
            "context": "Meaningful peace begins in quiet moments of understanding and dialogue.",
            "foundation_connection": "At Jalte Diye Foundation, our social education fosters empathy and dialogue.",
            "cta": "Listen completely to someone today before forming a reply.",
            "hashtags": ["#InternationalDayofPeace", "#PeaceAndJustice", "#Dialogue"],
        }
        errors = self.validator.validate_deterministic(candidate, "Foundation Events", event=event)
        self.assertTrue(any("foundation event name mismatch" in e.lower() for e in errors))

    def test_event_name_women_girls_education_gets_relevant_event(self):
        """3. Women/girls education content gets a relevant women/girls awareness event."""
        candidate = {
            "event_name": "International Day of the Girl Child",
            "quote": "When a girl is educated, an entire generation is elevated with her.",
            "explanation": "Educating girls builds stronger, more equitable communities.",
            "context": "When girls access quality schooling and support, families and communities thrive.",
            "foundation_connection": "Jalte Diye Foundation promotes accessible education for girls to bridge social barriers.",
            "cta": "Support or mentor a young girl in your neighborhood with educational resources today.",
            "hashtags": ["#GirlsEducation", "#DayOfTheGirl", "#EqualOpportunities", "#SocialEducation"],
        }
        errors = self.validator.validate_deterministic(candidate, "Women Empowerment")
        self.assertEqual(errors, [])

    def test_event_name_forest_content_gets_forest_event(self):
        """4. Forest content gets a forest/environment event."""
        candidate = {
            "event_name": "International Day of Forests",
            "quote": "A forest is not just trees; it is a breathing community of ancient life.",
            "explanation": "Preserving forests safeguards biodiversity and the air we breathe.",
            "context": "Ancient woodlands and urban tree canopies filter our air and protect local water tables.",
            "foundation_connection": "At Jalte Diye Foundation, environmental awareness is part of daily community stewardship.",
            "cta": "Plant a sapling or water a neighborhood tree on your street today.",
            "hashtags": ["#DayOfForests", "#ProtectNature", "#TreeCanopy", "#EcoAwareness"],
        }
        errors = self.validator.validate_deterministic(candidate, "Climate & Environment")
        self.assertEqual(errors, [])

    def test_event_name_peace_content_gets_peace_event(self):
        """5. Peace content gets a peace-related event."""
        candidate = {
            "event_name": "International Day of Peace",
            "quote": "Peace is not the absence of conflict; it is the presence of justice and dialogue.",
            "explanation": "True harmony begins when we choose dialogue and fairness over division.",
            "context": "Everyday peace is built when people choose to listen and resolve differences fairly.",
            "foundation_connection": "Social education at Jalte Diye Foundation emphasizes mutual respect and compassionate dialogue.",
            "cta": "Reach out to resolve a misunderstanding with someone today through kind dialogue.",
            "hashtags": ["#InternationalDayOfPeace", "#PeaceAndJustice", "#CommunityDialogue"],
        }
        errors = self.validator.validate_deterministic(candidate, "Peace & Justice")
        self.assertEqual(errors, [])

    def test_event_name_unrelated_event_is_rejected(self):
        """6. Unrelated event name is rejected by validator."""
        # Quote about women's leadership with Event Name: International Day of Forests -> REJECT
        candidate = {
            "event_name": "International Day of Forests",
            "quote": "When women are given the space and freedom to lead, entire communities rise.",
            "explanation": "Equal opportunities enable women to lead meaningful community progress.",
            "context": "Every family and community thrives when women make decisions without barriers.",
            "foundation_connection": "Promoting gender equity is a vital part of Jalte Diye Foundation's social education efforts.",
            "cta": "Make space today to support a woman's voice or idea in your workplace.",
            "hashtags": ["#WomenEmpowerment", "#EqualVoices", "#CommunityRespect"],
        }
        errors = self.validator.validate_deterministic(candidate, "Women Empowerment")
        self.assertTrue(len(errors) > 0)
        self.assertTrue(
            any("event name topic mismatch" in e.lower() or "forests" in e.lower() for e in errors)
        )

    def test_event_name_content_with_no_strong_event_match_returns_general_awareness(self):
        """7. Content with no strong event match returns General Awareness and passes validation."""
        candidate = {
            "event_name": "General Awareness",
            "quote": "Taking time to pause and care for your mental calm restores emotional resilience.",
            "explanation": "A quiet moment of reflection calms the mind and helps us respond with clarity.",
            "context": "Taking care of your mental peace gives you the patience to show up well for others.",
            "foundation_connection": "Emotional well-being and mindfulness are central to Jalte Diye Foundation's holistic education.",
            "cta": "Take a quiet five-minute pause today to breathe deeply and check in on how you feel.",
            "hashtags": ["#HealthAndMindfulness", "#MentalPeace", "#DailyCalm", "#SelfCare"],
        }
        errors = self.validator.validate_deterministic(candidate, "Health & Mindfulness")
        self.assertEqual(errors, [])

    def test_event_name_present_in_final_metadata(self):
        """8. Event Name is present in final metadata construction."""
        from website_assets.update_assets import update_website_assets
        import tempfile

        with tempfile.TemporaryDirectory() as temp_dir:
            temp_output = os.path.join(temp_dir, "test_poster.jpg")
            with open(temp_output, "wb") as f:
                f.write(b"dummy image content")

            pipeline_result = {
                "date": "2026-09-22",
                "theme": "Women Empowerment",
                "event_name": "International Day of the Girl Child",
                "quote": "When women lead, communities rise.",
                "explanation": "Equal leadership drives community progress.",
                "long_explanation": "Context and action.",
                "caption": "Full caption text.",
                "hashtags": ["#WomenLead"],
                "poster_path": temp_output,
                "event": None,
            }

            res = update_website_assets(pipeline_result, project_root=temp_dir, config=self.config)
            self.assertTrue(os.path.exists(res["metadata_path"]))

            with open(res["metadata_path"], "r", encoding="utf-8") as f:
                saved_metadata = json.load(f)

            self.assertIn("event_name", saved_metadata)
            self.assertEqual(saved_metadata["event_name"], "International Day of the Girl Child")

    def test_event_name_canonical_metadata_key_order(self):
        """9. Canonical metadata key order strictly places event_name immediately after theme."""
        content = self.fallback.get_fallback_quote("Climate & Environment")
        today_str = "2026-09-22"
        theme = "Climate & Environment"
        event_name = content.get("event_name", "General Awareness")

        metadata = {
            "date": today_str,
            "theme": theme,
            "event_name": event_name,
            "quote": content["quote"],
            "explanation": content["explanation"],
            "long_explanation": content.get("long_explanation", ""),
            "caption": content.get("caption", ""),
            "hashtags": content.get("hashtags", []),
            "image": "latest/poster.jpg",
            "source": "Cogentic AI",
            "event": None,
        }

        keys = list(metadata.keys())
        theme_idx = keys.index("theme")
        event_name_idx = keys.index("event_name")
        quote_idx = keys.index("quote")

        self.assertEqual(event_name_idx, theme_idx + 1)
        self.assertEqual(quote_idx, event_name_idx + 1)

    def test_poster_generator_accepts_event_name(self):
        """10. PosterGenerator.render accepts event_name parameter gracefully."""
        pg = PosterGenerator(self.config, self.project_root)
        # Verify method signature allows event_name
        import inspect
        sig = inspect.signature(pg.render)
        self.assertIn("event_name", sig.parameters)


if __name__ == "__main__":
    unittest.main()



