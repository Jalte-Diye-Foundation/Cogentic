"""Gemini-powered quote, explanation, and dynamic description generation."""

from __future__ import annotations

import glob
import json
import logging
import os
from typing import Any

from google import genai
from google.genai import types

from content.foundation_context import get_foundation_prompt_context

logger = logging.getLogger(__name__)


import re


def strip_markdown(text: str) -> str:
    """Remove markdown bold/italic formatting markers (** or * or __) while preserving text."""
    if not text:
        return ""
    text = re.sub(r"\*\*([^*]+)\*\*", r"\1", text)
    text = re.sub(r"\*([^*]+)\*", r"\1", text)
    text = re.sub(r"__([^_]+)__", r"\1", text)
    text = re.sub(r"_([^_]+)_", r"\1", text)
    return text.strip()


def sanitize_text(text: str) -> str:
    """Clean punctuation artifacts, double spaces, and formatting issues.

    - Normalizes curly quotes/apostrophes and dashes without destroying structure.
    - Converts em-dashes / double spaces between clauses into clean punctuation (comma or period).
    - Removes spaces before punctuation marks.
    - Removes duplicate punctuation marks (e.g., '..', ',,').
    - Ensures proper single spacing between words.
    - Strips markdown formatting markers (**bold**, *italic*, etc.).
    """
    if not text:
        return ""

    # 1. Strip markdown bold/italics/headings
    text = strip_markdown(text)

    # 2. Normalize curly quotes and apostrophes
    text = text.replace("’", "'").replace("‘", "'").replace("“", '"').replace("”", '"')

    # 3. Normalize em-dashes, en-dashes, and double hyphens into natural punctuation
    text = re.sub(r"\s*[—–―]\s*", ", ", text)
    text = re.sub(r"\s*--\s*", ", ", text)

    # 4. Fix double-space clause boundaries where dashes were stripped
    # e.g., "word  it is" -> "word, it is" or "word  It is" -> "word. It is"
    text = re.sub(r"(\b\w+)\s{2,}([a-z])", r"\1, \2", text)
    text = re.sub(r"(\b\w+)\s{2,}([A-Z])", r"\1. \2", text)

    # 5. Handle specific common idiom missing commas
    text = re.sub(r"\bno words only actions\b", "no words, only actions", text, flags=re.IGNORECASE)

    # 6. Fix spaces before punctuation
    text = re.sub(r"\s+([,.:;?!])", r"\1", text)

    # 7. Fix duplicate punctuation marks
    text = re.sub(r",+", ",", text)
    text = re.sub(r"\.{2,}", ".", text)
    text = re.sub(r";+", ";", text)
    text = re.sub(r":+", ":", text)
    text = re.sub(r"!+", "!", text)
    text = re.sub(r"\?+", "?", text)
    text = re.sub(r"([!?:;])\.", r"\1", text)
    text = re.sub(r"\.([!?:;])", r"\1", text)
    text = re.sub(r"[,;]\.", ".", text)
    text = re.sub(r"\.,", ".", text)


    # 8. Ensure space after punctuation when followed by a letter
    text = re.sub(r"([,.:;?!])([A-Za-z])", r"\1 \2", text)

    # 9. Collapse multiple whitespace into single space
    text = re.sub(r"[ \t]+", " ", text).strip()

    return text


def build_structured_long_explanation(
    context: str,
    foundation_connection: str,
    cta: str,
    hashtags: list[str] | None = None,
    hook: str = "",
) -> str:
    """Assemble the web-facing long explanation from structured components.

    - Does NOT repeat the quote or event sentence.
    - Does NOT contain markdown asterisks (**).
    - Does NOT append hashtags (hashtags are rendered separately downstream via metadata.json).
    """
    clean_hook = sanitize_text(hook)
    clean_context = sanitize_text(context)
    clean_foundation = sanitize_text(foundation_connection)
    clean_cta = sanitize_text(cta)

    sections = [
        clean_hook,
        clean_context,
        clean_foundation,
        clean_cta,
    ]
    return "\n\n".join(s for s in sections if s)


def build_social_caption(
    quote: str,
    context: str,
    foundation_connection: str,
    cta: str,
    hashtags: list[str] | None = None,
    hook: str = "",
) -> str:
    """Assemble a human-first social caption for social channels."""
    clean_hook = sanitize_text(hook)
    clean_context = sanitize_text(context)
    clean_foundation = sanitize_text(foundation_connection)
    clean_cta = sanitize_text(cta)

    sections = [
        clean_hook,
        clean_context,
        clean_foundation,
        clean_cta,
    ]
    if hashtags:
        sections.append(" ".join(hashtags))
    return "\n\n".join(s for s in sections if s)


def default_social_hook(theme: str) -> str:
    """Provide a human-led fallback opening when AI generation is unavailable."""
    hooks = {
    "Peace & Justice": "Peace is tested in the small moments, not the speeches.",
    "Climate & Environment": "The environment pays attention to our everyday habits.",
    "Quality Education": "Real education changes how we treat people.",
    "Women Empowerment": "Equality cannot wait for permission.",
    "Health & Mindfulness": "Caring for ourselves changes how we show up for others.",
    "Foundation Events": "A day of observance should lead to an honest conversation.",
    }
    return hooks.get(theme, "The way we treat people is part of what we teach.")


class ContentGenerator:
    """Generates theme-specific quote and structured description content using Gemini."""

    def __init__(self, config: dict[str, Any], project_root: str) -> None:
        self._config = config
        self._project_root = project_root
        gemini_config = config["gemini"]
        api_key_env = gemini_config.get("api_key_env", "GEMINI_API_KEY")
        api_key = os.environ.get(api_key_env)
        if not api_key:
            logger.warning("Gemini API key not found (%s). AI generation will fall back to CSV/emergency.", api_key_env)
            self._client = None
        else:
            try:
                self._client = genai.Client(api_key=api_key)
            except Exception as exc:
                logger.warning("Failed to initialize Gemini client: %s. Will fall back to CSV/emergency.", exc)
                self._client = None
        self._model = gemini_config["model"]

    @property
    def client(self) -> genai.Client:
        return self._client

    def get_recent_history(self, limit: int = 15) -> list[dict[str, Any]]:
        """Load recent posts from website_assets/archive to avoid repetition."""
        archive_dir = os.path.join(self._project_root, "website_assets", "archive")
        history: list[dict[str, Any]] = []

        if os.path.exists(archive_dir):
            files = sorted(glob.glob(os.path.join(archive_dir, "*", "metadata.json")))
            for file in files[-limit:]:
                try:
                    with open(file, "r", encoding="utf-8") as f:
                        data = json.load(f)
                        history.append(data)
                except Exception:
                    logger.warning("Failed to read history from %s", file)
        return history

    def get_recent_quotes(self) -> list[str]:
        """Load recently generated quotes to avoid repetition."""
        history = self.get_recent_history(limit=15)
        return [h.get("quote", "").strip() for h in history if h.get("quote")]

    def generate(self, theme: str, event: dict | None = None) -> dict[str, Any]:
        """Generate a complete daily content package for the given theme/event."""
        if self._client is None:
            logger.warning("Gemini client is unavailable; triggering fallback.")
            raise RuntimeError("Gemini API client not initialized (missing API key or init error).")

        recent_history = self.get_recent_history(limit=10)
        recent_quotes = [h.get("quote", "").strip() for h in recent_history if h.get("quote")]
        recent_ctas = [h.get("cta", "").strip() for h in recent_history if h.get("cta")]
        recent_hashtags = [" ".join(h.get("hashtags", [])) for h in recent_history if h.get("hashtags")]

        recent_quotes_text = "\n".join(f"- {q}" for q in recent_quotes) if recent_quotes else "None recorded."
        recent_ctas_text = "\n".join(f"- {c}" for c in recent_ctas) if recent_ctas else "None recorded."
        recent_hashtags_text = "\n".join(f"- {t}" for t in recent_hashtags) if recent_hashtags else "None recorded."

        foundation_context = get_foundation_prompt_context()

        # Determine target date string and pre-determine event_name
        if isinstance(event, dict) and event.get("target_date"):
            target_date_str = str(event["target_date"])
        else:
            target_date_str = get_current_ist_date().strftime("%d %B %Y")

        if event and event.get("event"):
            event_name = sanitize_text(str(event["event"]).strip())
            is_awareness = event.get("is_awareness_day", False)
            if is_awareness:
                event_instruction = f"""
Today's Date: {target_date_str}
Recognized Awareness Day: {event_name}
Configured Theme: {theme}

HARD CONSTRAINT (AWARENESS EVENT SPECIFICITY):
- Today is '{event_name}'.
- The quote, explanation, context, foundation connection, CTA, and hashtags MUST be specifically focused on the topic represented by '{event_name}' (e.g. for 'World Heart Day' -> heart health, cardiovascular wellness, daily heart care, healthy habits).
- Do NOT generate a generic or disconnected reflection.
- Event Name must be exact: '{event_name}'.
"""
            else:
                event_instruction = f"""
Today's Date: {target_date_str}
Today's Special Calendar Event:
Event Name: {event_name}
Theme: {theme}

HARD CONSTRAINT (EVENT > THEME):
- The active calendar event is '{event_name}'.
- The quote MUST directly represent and celebrate '{event_name}'.
- Do NOT generate content about an unrelated topic (e.g. do not generate tree-planting or climate quotes for Peace Day or Right to Know Day).
- The quote, explanation, context, foundation connection, CTA, and hashtags must all celebrate '{event_name}'.
- Event Name must be exact: '{event_name}'.
"""
        else:
            event_name = "General Awareness"
            event_instruction = f"""
Today's Date: {target_date_str}
This is an evergreen theme day (NO special event).
Theme: {theme}
Event Name: General Awareness

HARD CONSTRAINT (THEME AS CLASSIFICATION CONSTRAINT):
- The quote MUST be semantically compatible with '{theme}'.
- Do NOT introduce an unrelated topic (e.g. if Theme is 'Women Empowerment', do NOT generate quotes about rural development or car-free streets; if Theme is 'Climate & Environment', do NOT generate quotes about peace or schooling).
- Do NOT invent or attach any calendar holiday or special event day. Set event_name to 'General Awareness'.
"""

        prompt = f"""
You are a thoughtful human social-media writer and educational storyteller for Jalte Diye Foundation.
Your goal is to write a warm, conversational, reflective, and relatable daily reflection for everyday people.

{foundation_context}

Configured Theme: {theme}
Determined Event Name: {event_name}
{event_instruction}

Previous Recent Quotes (DO NOT REPEAT):
{recent_quotes_text}

Previous Recent CTAs (DO NOT REPEAT):
{recent_ctas_text}

Previous Recent Hashtag Sets (DO NOT REPEAT):
{recent_hashtags_text}

REQUIRED GENERATION SEQUENCE (FOLLOW EXACTLY IN ORDER):
STEP 1: Identify the exact topic and subject of the quote (aligned with Event '{event_name}' if active, or Theme '{theme}' if General Awareness).
STEP 2: Identify the specific entity, challenge, or human experience represented by the quote.
STEP 3: Use the pre-determined event name: '{event_name}'.
STEP 4: Generate a concise poster explanation (under 35 words) around that exact subject.
STEP 5: Generate context (40 to 70 words) explaining why this exact subject matters to everyday people.
STEP 6: Generate foundation connection (40 to 80 words) linking this exact subject to Jalte Diye Foundation's social education mission.
STEP 7: Generate a concrete daily CTA (20 to 40 words) for this exact subject.
STEP 8: Generate 3 to 6 hashtags specifically representing that subject.
STEP 9: Check whether the entire package matches the configured Theme and Event Name.

CRITICAL SEMANTIC CONSISTENCY RULES:
1. PRIMARY ANCHOR: The Quote + Explanation is the primary semantic anchor of the entire post.
2. SECONDARY CONTENT: Context, Foundation Connection, CTA, and Hashtags MUST be semantically derived from the Quote + Explanation.
3. EVENT NAME RULE: Use the exact pre-determined event name '{event_name}'.
4. EXTERNAL CONSTRAINT: Theme is a classification constraint, NOT permission to introduce an unrelated topic.
5. EVENT CONSTRAINT: If an Event is present, Event is a hard semantic constraint (EVENT > THEME).
6. NO ARBITRARY TOPIC INJECTION: Do NOT introduce women empowerment, climate, education, mental health, refugees, etc. unless the quote itself directly establishes that subject.
7. NO VAGUE/GENERIC BRIDGING: Do NOT accept generic concepts like "community", "equality", "respect", "humanity", "education", or "awareness" as sufficient evidence of topic alignment when the underlying subjects differ.
8. THEME & EVENT FIDELITY: Theme/Event must NEVER force you to rewrite or diverge from the quote's subject.

Required Output Schema:
Return ONLY valid JSON matching this exact structure:
{{
    "topic": "Specific 2 to 6 word topic label (e.g. 'Cardiovascular Wellness & Daily Heart Care')",
    "topic_keywords": ["keyword1", "keyword2", "keyword3"],
    "topic_domains": ["domain_label"],
    "event_name": "{event_name}",
    "hook": "A strong, human first line of 14 words or fewer. Start with a relatable question, clear opinion, or counter-intuitive observation. Never start with a greeting, a holiday name, or a quote.",
    "quote": "10 to 20 word memorable, inspiring quote (for poster)",
    "explanation": "Short 2-sentence explanation for the poster (maximum 35 words)",
    "context": "Why this specific quote topic matters to everyday people (2 to 3 sentences, 40 to 70 words). Must address the quote's topic directly. Do NOT repeat the quote text. Do NOT write like an academic textbook or NGO report.",
    "foundation_connection": "Explain why THIS specific topic matters to Jalte Diye Foundation's mission of social education, empathy, and community awareness (2 to 4 sentences, 40 to 80 words). Be dynamic and topic-specific. Vary sentence openings naturally—DO NOT start with 'At Jalte Diye Foundation, we believe...'. DO NOT invent fake programs, numbers, or facilities.",
    "cta": "One concrete, simple, and realistic action step the reader can do today related to THIS specific topic (1 to 2 sentences, 20 to 40 words). Avoid generic slogans like 'be the change' or 'spread awareness'.",
    "hashtags": ["#TopicTag1", "#TopicTag2", "#TopicTag3", "#TopicTag4"]
}}

Key Style & Human-Writing Rules:
1. LinkedIn Caption Structure: The hook is the first line of the LinkedIn caption. Follow it with the context, foundation connection, CTA, and hashtags as separate paragraphs. Do not include the poster quote in the caption; the graphic already carries it.
2. White Space: Every caption section must be one or two short sentences. Use bullet points only when presenting a genuine framework, never a generic list.
3. Voice: Write in first-person plural when referring to the Foundation: "We at Jalte Diye Foundation..." or "Our team...". Write as an empathetic, professional founder who opposes discrimination and believes real education changes how people treat one another.
4. Tone: Warm, human, thoughtful, conversational, and grounded. Sound like a real person writing a meaningful post, not a corporate press release or robotic AI generator.
5. Quote-Specific Depth: The long explanation must directly unpack the exact meaning and imagery of the quote. Answer naturally: What does this specific quote mean? What real-world behavior or challenge does it point toward? Why does it matter to ordinary people? What can someone realistically do today?
6. Strict Cliché & Robotic Phrase Ban: You must NOT use repetitive AI templates and formulaic phrases, including:
   - "is at the heart of..."
   - "isn't just..." / "is not just..."
   - "for us at Jalte Diye Foundation..."
   - "this reminds us that..."
   - "it is a powerful reminder..."
   - "in today's world..."
   - "by coming together..."
   - "together, we can..."
   - "let us all..."
   - "this quote..."
   - "essential foundations" / "collective responsibility" / "fostering" / "cultivating" / "holistic development"
   Also never use: "In today's fast-paced world", "It is important to remember", "A testament to", "Delve deep into", "Fostering a sense of", "Look no further", "Furthermore", "Moreover", "In conclusion", "Revolutionize", "Tap into", "Synergy", "Beacon", "Pivotal", "Unlocking", "Catalyst", "Transformative", "Harnessing", "Let's explore", "Here's how", or "Let's unpack this".
7. Sentence Style: Use short and medium sentences, active voice, and varied openings. Avoid formulaic openings.
8. Grounded Foundation Connection: Answer 'Why does THIS specific topic matter to Jalte Diye Foundation?' specifically, grounded in verified social education and empathy values. Vary openings naturally.
9. Actionable CTA: Give the reader something concrete and realistic they can do in their day-to-day routine for this specific topic.
10. Distinctiveness: Every section must be unique. Never repeat the quote inside context, foundation connection, or CTA.
11. Hashtags: Provide 3 to 6 valid hashtags starting with '#' matching the quote's actual topic. At least 2 must be strongly topic/event-specific.
12. Punctuation & Formatting: Use proper standard punctuation (commas, periods, colons). Never use double spaces or leave sentences unpunctuated. Output plain text values. Do NOT include markdown formatting (such as **bold**, *italic*, or markdown headings) in any JSON values.
"""

        try:
            response = self._client.models.generate_content(
                model=self._model,
                contents=prompt,
                config=types.GenerateContentConfig(
                    response_mime_type="application/json",
                ),
            )

            parsed = json.loads(response.text)

            topic = sanitize_text(str(parsed.get("topic", "")).strip())
            # Enforce pre-determined authoritative event_name
            final_event_name = event_name

            hook = sanitize_text(str(parsed.get("hook", "")).strip())
            quote = sanitize_text(str(parsed.get("quote", "")).strip())
            explanation = sanitize_text(str(parsed.get("explanation", "")).strip())
            context = sanitize_text(str(parsed.get("context", "")).strip())
            foundation_conn = sanitize_text(str(parsed.get("foundation_connection", "")).strip())
            cta = sanitize_text(str(parsed.get("cta", "")).strip())
            raw_hashtags = parsed.get("hashtags", [])

            # Format and sanitize hashtags
            if isinstance(raw_hashtags, str):
                raw_hashtags = raw_hashtags.split()
            hashtags = []
            for tag in raw_hashtags:
                tag_str = str(tag).strip()
                if tag_str:
                    tag_str = re.sub(r"[^A-Za-z0-9_#]", "", tag_str)
                    if not tag_str.startswith("#"):
                        tag_str = f"#{tag_str}"
                    if len(tag_str) > 1 and tag_str not in hashtags:
                        hashtags.append(tag_str)

            # Safety word-count trims if model generated slightly over length
            quote_words = quote.split()
            if len(quote_words) > 20:
                quote = " ".join(quote_words[:20])
                if not quote.endswith((".", "!", "?", '"', "'")):
                    quote = quote + "."

            explanation_words = explanation.split()
            if len(explanation_words) > 35:
                explanation = " ".join(explanation_words[:35])
                if not explanation.endswith((".", "!", "?", '"', "'")):
                    explanation = explanation + "."

            if not hook or not quote or not explanation or not context or not foundation_conn or not cta:
                raise ValueError("Gemini response missing one or more required fields.")

            long_explanation = build_structured_long_explanation(
                context=context,
                foundation_connection=foundation_conn,
                cta=cta,
                hashtags=hashtags,
                hook=hook,
            )

            caption = build_social_caption(
                quote=quote,
                context=context,
                foundation_connection=foundation_conn,
                cta=cta,
                hashtags=hashtags,
                hook=hook,
            )

            return {
                "topic": topic,
                "event_name": final_event_name,
                "hook": hook,
                "quote": quote,
                "explanation": explanation,
                "context": context,
                "foundation_connection": foundation_conn,
                "cta": cta,
                "long_explanation": long_explanation,
                "caption": caption,
                "hashtags": hashtags,
            }

        except json.JSONDecodeError as exc:
            logger.exception("Failed to parse Gemini generation response as JSON.")
            raise ValueError("Invalid JSON returned by Gemini generation.") from exc

        except Exception:
            logger.exception("Gemini content generation failed for theme: %s", theme)
            raise
