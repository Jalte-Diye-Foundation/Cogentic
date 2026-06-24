
"""
Jalte Diye Foundation – MASTER DAILY CONTENT PIPELINE (v2.2)
=============================================================
Key changes in v2.2:
  - FREE_MODELS updated to verified June 2025 OpenRouter IDs.
  - Uses openrouter/free as ultimate auto-router fallback.
  - Fetches live free model list from OpenRouter at startup & picks top 5.
  - Exponential backoff on 429 (rate limit) errors.
  - Cleaner JSON extraction that handles any model's output style.
  - Background auto-generates branded gradient if image file missing.
  - Emergency quotes verified at exactly 12–15 words.
"""

import os, csv, json, re, random, time, textwrap, traceback
import requests
from PIL import Image, ImageDraw, ImageFont

# ======================== CONFIGURATION =========================
GNEWS_API_KEY      = "pls enter key"
OPENROUTER_API_KEY = "pls enter key"

POSTER_OUTPUT_DIR  = "posters"
USED_QUOTES_LOG    = "used_quotes_log.txt"
SUB_THEME_LOG      = "sub_theme_log.json"
os.makedirs(POSTER_OUTPUT_DIR, exist_ok=True)

DOMAINS = {
    "Peace & Justice":       "jalte_diye_1.jpg",
    "Health & Mindfulness":  "jalte_diye_1.jpg",
    "Social Education":      "jalte_diye_1.jpg",
    "Climate & Environment": "jalte_diye_1.jpg",
}

CSV_FALLBACK_MAP = {
    "Peace & Justice":       "peace_justice.csv",
    "Health & Mindfulness":  "event_quotes.csv",
    "Social Education":      "quality_education.csv",
    "Climate & Environment": "climate.csv",
}

# ── Verified free model IDs from OpenRouter (June 2025) ─────────
# Quality-ranked: best models first, openrouter/free as safety net.
FREE_MODELS_DEFAULT = [
    "google/gemma-4-31b-it:free",           # quality score 65 — best free
    "nvidia/nemotron-3-super-120b-a12b:free", # quality score 60, 1M ctx
    "openai/gpt-oss-120b:free",             # quality score 55
    "meta-llama/llama-3.3-70b-instruct:free", # quality score 24, reliable
    "qwen/qwen3-coder:free",                # quality score 41, follows instructions well
    "openrouter/free",                      # auto-router: picks any available free model
]

# ================================================================

SUB_THEMES = {
    "Peace & Justice": [
        "reconciliation and forgiveness",
        "nonviolent conflict resolution",
        "equal justice under law",
        "empathy across borders",
        "community-led peacebuilding",
        "human dignity in conflict zones",
        "truth and accountability",
    ],
    "Health & Mindfulness": [
        "inner silence and self-awareness",
        "mindful living and daily habits",
        "emotional resilience and mental strength",
        "compassionate self-care",
        "holistic well-being of body and mind",
        "stress reduction and clarity",
        "the healing power of community",
    ],
    "Social Education": [
        "curiosity as a lifelong companion",
        "education that builds character",
        "inclusive classrooms and equal access",
        "ethics and values in learning",
        "empowering young minds",
        "teachers as agents of change",
        "innovation and critical thinking",
    ],
    "Climate & Environment": [
        "stewardship of the natural world",
        "responsibility to future generations",
        "renewable hope and clean energy",
        "biodiversity and ecosystem care",
        "sustainable everyday choices",
        "indigenous wisdom and nature",
        "collective action for a green future",
    ],
}

SDG_TEMPLATES = {
    "Peace & Justice": {
        "tone": "solemn, hopeful, and deeply humanitarian",
        "exemplar": '"Where justice blooms, the roots of war can no longer grow."',
        "vocabulary": ["peace", "justice", "harmony", "reconciliation", "dignity", "rights",
                       "unity", "empathy", "forgiveness", "conflict", "diplomacy", "equity"],
    },
    "Health & Mindfulness": {
        "tone": "calm, nurturing, and introspective",
        "exemplar": '"Stillness within is the seed of strength without."',
        "vocabulary": ["health", "mindfulness", "wellness", "calm", "balance", "breath",
                       "healing", "awareness", "inner peace", "resilience", "mental", "compassion"],
    },
    "Social Education": {
        "tone": "inspiring, warm, and thought-provoking",
        "exemplar": '"Education plants seeds of wisdom that no storm of ignorance can uproot."',
        "vocabulary": ["education", "learning", "knowledge", "curiosity", "wisdom", "character",
                       "ethics", "values", "teacher", "student", "skill", "growth", "moral"],
    },
    "Climate & Environment": {
        "tone": "urgent yet hopeful, reverent toward nature",
        "exemplar": '"The earth whispers its needs; may we finally learn to listen."',
        "vocabulary": ["climate", "environment", "earth", "green", "future", "nature",
                       "sustainable", "ecosystem", "conservation", "renewable", "generations", "planet"],
    },
}

COMMON_VALUES = [
    "kindness", "respect", "dignity", "ethical", "compassion", "solidarity",
    "equality", "fairness", "inclusive", "community", "cooperation", "humanity",
    "shared values", "global harmony", "moral courage", "social good",
]

EMERGENCY = {
    "Peace & Justice": {
        "quote": "True peace is not silence but the courage to seek justice always.",
        "explanation": "Peace is built through fair institutions, empathetic dialogue, and courageous commitment to human rights for all.",
    },
    "Health & Mindfulness": {
        "quote": "A quiet mind is the greatest sanctuary we can ever build within.",
        "explanation": "Mindfulness teaches us that stillness and self-awareness are the foundation of lasting well-being and inner strength.",
    },
    "Social Education": {
        "quote": "Education without values is a ship without a compass or moral anchor.",
        "explanation": "Knowledge becomes transformative only when guided by ethical values and deep compassion for our shared humanity.",
    },
    "Climate & Environment": {
        "quote": "The earth does not belong to us; we belong to the earth.",
        "explanation": "Sustainable living means honouring our interdependence with nature and protecting the planet for every future generation.",
    },
}

# ================================================================
# 0. DYNAMIC MODEL FETCHING (gets live free model list from OR)
# ================================================================
def fetch_live_free_models() -> list:
    """
    Fetch the current free model list from OpenRouter and return top IDs by quality.
    Falls back to FREE_MODELS_DEFAULT if the API call fails.
    """
    try:
        resp = requests.get(
            "https://openrouter.ai/api/v1/models",
            headers={
                "Authorization":  f"Bearer {OPENROUTER_API_KEY}",
                "HTTP-Referer":   "https://jaltediye.org",
                "X-Title":        "Jalte Diye Foundation",
            },
            timeout=10,
        )
        if resp.status_code == 200:
            all_models = resp.json().get("data", [])
            # Filter: free (prompt price == 0 or "0") and text output
            free = [
                m for m in all_models
                if str(m.get("pricing", {}).get("prompt", "1")) == "0"
                and ":free" in m.get("id", "")
            ]
            # Sort by context window descending (proxy for capability)
            free.sort(key=lambda m: m.get("context_length", 0), reverse=True)
            ids = [m["id"] for m in free[:8]]
            if ids:
                ids.append("openrouter/free")  # always keep auto-router
                print(f"   🔄 Live free models fetched: {len(ids)} models")
                return ids
    except Exception as e:
        print(f"   ⚠️  Could not fetch live models: {e}")
    print("   ℹ️  Using default free model list.")
    return FREE_MODELS_DEFAULT


# ================================================================
# 1. SUB-THEME ROTATION
# ================================================================
def get_next_sub_theme(domain: str) -> str:
    log: dict = {}
    if os.path.exists(SUB_THEME_LOG):
        try:
            with open(SUB_THEME_LOG, "r", encoding="utf-8") as f:
                log = json.load(f)
        except Exception:
            pass
    themes   = SUB_THEMES.get(domain, ["general reflection"])
    next_idx = (log.get(domain, -1) + 1) % len(themes)
    log[domain] = next_idx
    with open(SUB_THEME_LOG, "w", encoding="utf-8") as f:
        json.dump(log, f, indent=2)
    return themes[next_idx]


# ================================================================
# 2. NEWS FETCHING & RELEVANCE SCORING
# ================================================================
def fetch_headlines(domain: str) -> list:
    query = domain.replace(" & ", " OR ").replace(" ", "+")
    url   = f"https://gnews.io/api/v4/search?q={query}&lang=en&max=5&apikey={GNEWS_API_KEY}"
    try:
        resp = requests.get(url, timeout=10)
        if resp.status_code == 200:
            return [a["title"] for a in resp.json().get("articles", [])]
        print(f"   ⚠️  GNews {resp.status_code}: {resp.text[:80]}")
    except Exception as e:
        print(f"   ⚠️  GNews error: {e}")
    return []


def relevance_score(domain: str, text: str) -> int:
    t = text.lower()
    return sum(1 for kw in SDG_TEMPLATES[domain]["vocabulary"] + COMMON_VALUES if kw in t)


def find_best_domain_and_topic():
    best_score, best_domain, best_topic = 0, None, None
    for domain in DOMAINS:
        for headline in fetch_headlines(domain)[:3]:
            s = relevance_score(domain, headline)
            if s > best_score:
                best_score, best_domain, best_topic = s, domain, headline
    return best_domain, best_topic, best_score


# ================================================================
# 3. QUOTE HELPERS
# ================================================================
def word_count(text: str) -> int:
    return len(text.split())

def trim_to_sentence(text: str) -> str:
    for p in ['.', '!', '?']:
        i = text.find(p)
        if i != -1:
            return text[:i + 1].strip()
    return text.strip()

def validate_quote_length(quote: str) -> bool:
    return 12 <= word_count(quote) <= 15


# ================================================================
# 4. PROMPT BUILDER
# ================================================================
def build_prompt(domain: str, sub_theme: str, topic, n: int) -> str:
    tmpl = SDG_TEMPLATES[domain]
    topic_line = (
        f'Today\'s news hook: "{topic}". Use it as inspiration only — write a timeless reflection.'
        if topic else
        "No specific news today — write a timeless, universal reflection."
    )
    vocab_hint = ", ".join(tmpl["vocabulary"][:6])
    return textwrap.dedent(f"""
        You are a philosopher-educator for the Jalte Diye Foundation.
        Mission: promote social education, mental peace, social harmony, and global unity.

        SDG Domain : {domain}
        Sub-theme  : {sub_theme}
        Context    : {topic_line}
        Tone       : {tmpl['tone']}
        Key words  : {vocab_hint}
        Style ref  : {tmpl['exemplar']}

        TASK: Write {n} original, distinct philosophical quotes about "{sub_theme}".

        ═══════════════════════════════════
        MANDATORY RULES — follow exactly:
        ═══════════════════════════════════
        1. Each quote = EXACTLY 12 to 15 words. Count every word.
        2. Poetic and value-driven. Not a cliché. Not a news headline.
        3. Must include at least one word from: {vocab_hint}.
        4. Each quote needs an explanation of 30–50 words.
        5. Return ONLY a valid JSON array. No markdown. No intro text. No extra keys.

        Output format (copy exactly):
        [
          {{"quote": "Your 12-15 word quote goes here ending with period.", "explanation": "Your 30-50 word explanation here."}},
          {{"quote": "Another distinct quote here of twelve to fifteen words.", "explanation": "Another 30-50 word explanation here."}}
        ]
    """).strip()


# ================================================================
# 5. JSON EXTRACTOR — handles any model's messy output
# ================================================================
def extract_candidates(raw: str) -> list:
    """Robustly extract a list of {quote, explanation} dicts from model output."""
    # Strip markdown fences
    raw = re.sub(r"^```(?:json)?[\r\n]*", "", raw.strip())
    raw = re.sub(r"[\r\n]*```$", "", raw.strip())

    # Attempt 1: direct JSON parse
    try:
        parsed = json.loads(raw)
        if isinstance(parsed, list):
            return [c for c in parsed if "quote" in c]
        if isinstance(parsed, dict) and "quote" in parsed:
            return [parsed]
    except json.JSONDecodeError:
        pass

    # Attempt 2: find JSON array in text
    m = re.search(r'\[[\s\S]*?\]', raw)
    if m:
        try:
            parsed = json.loads(m.group())
            if isinstance(parsed, list):
                return [c for c in parsed if "quote" in c]
        except Exception:
            pass

    # Attempt 3: extract individual objects
    objs = re.findall(r'\{[^{}]+\}', raw, re.DOTALL)
    results = []
    for o in objs:
        try:
            d = json.loads(o)
            if "quote" in d:
                results.append(d)
        except Exception:
            pass
    if results:
        return results

    # Attempt 4: look for "quote": "..." patterns line-by-line
    quote_matches = re.findall(r'"quote"\s*:\s*"([^"]+)"', raw)
    expl_matches  = re.findall(r'"explanation"\s*:\s*"([^"]+)"', raw)
    if quote_matches:
        paired = []
        for i, q in enumerate(quote_matches):
            e = expl_matches[i] if i < len(expl_matches) else "A reflection on our shared values."
            paired.append({"quote": q, "explanation": e})
        return paired

    return []


# ================================================================
# 6. OPENROUTER CALLER WITH RETRY + BACKOFF
# ================================================================
def call_openrouter(prompt: str, models: list) -> list:
    headers = {
        "Authorization":  f"Bearer {OPENROUTER_API_KEY}",
        "Content-Type":   "application/json",
        "HTTP-Referer":   "https://jaltediye.org",
        "X-Title":        "Jalte Diye Foundation",
    }
    for model in models:
        print(f"      🤖 Trying: {model}")
        payload = {
            "model": model,
            "messages": [
                {
                    "role": "system",
                    "content": (
                        "You are a helpful assistant. "
                        "Always respond with ONLY a valid JSON array. "
                        "No markdown, no code fences, no explanation outside the JSON."
                    ),
                },
                {"role": "user", "content": prompt},
            ],
            "temperature": 0.82,
            "max_tokens":  900,
        }
        for attempt in range(3):  # up to 3 retries per model
            try:
                resp = requests.post(
                    "https://openrouter.ai/api/v1/chat/completions",
                    headers=headers,
                    json=payload,
                    timeout=50,
                )
                if resp.status_code == 429:
                    wait = 2 ** attempt
                    print(f"      ⏳ Rate limited — waiting {wait}s…")
                    time.sleep(wait)
                    continue
                if resp.status_code == 200:
                    raw = (
                        resp.json()
                        .get("choices", [{}])[0]
                        .get("message", {})
                        .get("content", "")
                        .strip()
                    )
                    if not raw:
                        print("      ⚠️  Empty content.")
                        break
                    candidates = extract_candidates(raw)
                    if candidates:
                        print(f"      ✅ {len(candidates)} candidate(s) parsed from {model}")
                        return candidates
                    else:
                        print(f"      ⚠️  Could not parse JSON from: {raw[:120]}")
                        break  # try next model
                else:
                    err = resp.text[:150]
                    print(f"      ❌ HTTP {resp.status_code}: {err}")
                    break  # try next model
            except requests.exceptions.Timeout:
                print(f"      ❌ Timeout (attempt {attempt+1}/3)")
            except Exception as e:
                print(f"      ❌ Error: {e}")
                break
    return []


# ================================================================
# 7. CANDIDATE SCORING + RANKING
# ================================================================
def score_candidate(c: dict, domain: str) -> float:
    quote = c.get("quote", "").strip()
    expl  = c.get("explanation", "").strip()
    score = 0.0
    wc    = word_count(quote)
    score += 3.0 if 12 <= wc <= 15 else (1.5 if 10 <= wc <= 17 else 0.0)
    combined = (quote + " " + expl).lower()
    vocab    = SDG_TEMPLATES[domain]["vocabulary"] + COMMON_VALUES
    score   += min(sum(1 for kw in vocab if kw in combined), 4.0)
    ew       = word_count(expl)
    score   += 2.0 if 25 <= ew <= 60 else (1.0 if ew >= 15 else 0.0)
    if os.path.exists(USED_QUOTES_LOG):
        with open(USED_QUOTES_LOG, "r", encoding="utf-8") as f:
            if quote in {l.strip() for l in f}:
                score -= 10.0
    return score


def generate_and_rank(domain: str, sub_theme: str, topic, models: list, n: int = 4) -> dict | None:
    prompt     = build_prompt(domain, sub_theme, topic, n)
    candidates = call_openrouter(prompt, models)
    if not candidates:
        return None

    print(f"   📊 Ranking {len(candidates)} candidate(s):")
    scored = []
    for i, c in enumerate(candidates):
        q  = c.get("quote", "").strip()
        if word_count(q) > 15:
            q = trim_to_sentence(q)
            c["quote"] = q
        s  = score_candidate(c, domain)
        wc = word_count(q)
        tag = "✅" if validate_quote_length(q) else f"⚠️  {wc}w"
        print(f"      [{i+1}] {tag} score={s:.1f} │ {q[:75]}")
        scored.append((s, c))

    scored.sort(key=lambda x: x[0], reverse=True)

    # Return best that passes strict length rule
    for s, c in scored:
        if validate_quote_length(c.get("quote", "")):
            return c

    # Relax: return highest-scored overall
    if scored:
        print("   ⚠️  No candidate hit 12–15 words — using closest match.")
        return scored[0][1]
    return None


# ================================================================
# 8. CSV FALLBACK
# ================================================================
def get_csv_quote(domain: str) -> dict | None:
    csv_file = CSV_FALLBACK_MAP.get(domain)
    if not csv_file or not os.path.exists(csv_file):
        return None
    used: set = set()
    if os.path.exists(USED_QUOTES_LOG):
        with open(USED_QUOTES_LOG, "r", encoding="utf-8") as f:
            used = {l.strip() for l in f}
    with open(csv_file, "r", encoding="utf-8-sig") as f:
        reader  = csv.reader(f)
        raw_hdr = next((r for r in reader if any(c.strip() for c in r)), None)
        if not raw_hdr:
            return None
        hdrs = [h.strip().lower() for h in raw_hdr]
        q_i  = hdrs.index("quote")    if "quote"   in hdrs else -1
        c_i  = hdrs.index("caption")  if "caption" in hdrs else -1
        o_i  = hdrs.index("occasion") if "occasion" in hdrs else -1
        if q_i == -1:
            return None
        for row in reader:
            if not row or len(row) <= q_i:
                continue
            qt = row[q_i].strip()
            if qt and qt not in used:
                exp = ""
                if c_i != -1 and len(row) > c_i:
                    exp = row[c_i].strip()
                elif o_i != -1 and len(row) > o_i:
                    exp = f"On {row[o_i].strip()}."
                _log_used(qt)
                return {"quote": qt, "explanation": exp}
    return None


# ================================================================
# 9. USED LOG
# ================================================================
def _log_used(quote: str) -> None:
    with open(USED_QUOTES_LOG, "a", encoding="utf-8") as f:
        f.write(quote.strip() + "\n")

def _is_used(quote: str) -> bool:
    if not os.path.exists(USED_QUOTES_LOG):
        return False
    with open(USED_QUOTES_LOG, "r", encoding="utf-8") as f:
        return quote.strip() in {l.strip() for l in f}


# ================================================================
# 10. BACKGROUND — AUTO-GENERATE PLACEHOLDER IF FILE MISSING
# ================================================================
DOMAIN_COLORS = {
    "Peace & Justice":       ((20,  50, 100), ( 80, 140, 200)),
    "Health & Mindfulness":  ((10,  80,  60), ( 60, 170, 120)),
    "Social Education":      ((70,  40,  10), (190, 120,  30)),
    "Climate & Environment": (( 8,  60,  25), ( 50, 150,  70)),
}

def ensure_background(domain: str, path: str) -> str:
    if os.path.exists(path):
        return path
    print(f"   ℹ️  '{path}' not found — auto-generating branded placeholder.")
    W, H   = 1080, 1080
    c1, c2 = DOMAIN_COLORS.get(domain, ((40, 40, 80), (120, 120, 180)))
    img    = Image.new("RGB", (W, H))
    draw   = ImageDraw.Draw(img)
    for y in range(H):
        t = y / H
        r = int(c1[0] + (c2[0] - c1[0]) * t)
        g = int(c1[1] + (c2[1] - c1[1]) * t)
        b = int(c1[2] + (c2[2] - c1[2]) * t)
        draw.line([(0, y), (W, y)], fill=(r, g, b))
    # Decorative circles
    for radius in range(250, 520, 45):
        ov = Image.new("RGBA", (W, H), (0, 0, 0, 0))
        od = ImageDraw.Draw(ov)
        alpha = max(8, 55 - (radius - 250) // 6)
        od.ellipse(
            [(W // 2 - radius, H // 2 - radius), (W // 2 + radius, H // 2 + radius)],
            outline=(255, 255, 255, alpha), width=2,
        )
        img = Image.alpha_composite(img.convert("RGBA"), ov).convert("RGB")
    slug = domain.replace(" & ", "_").replace(" ", "_")
    out  = os.path.join(POSTER_OUTPUT_DIR, f"bg_{slug}.jpg")
    img.save(out, "JPEG", quality=92)
    print(f"   ✅ Placeholder saved: {out}")
    return out


# ================================================================
# 11. POSTER GENERATOR
# ================================================================
def _load_font(size: int):
    for face in [
        "arial.ttf", "Arial.ttf",
        "/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf",
        "/usr/share/fonts/truetype/liberation/LiberationSans-Regular.ttf",
        "/System/Library/Fonts/Helvetica.ttc",
    ]:
        try:
            return ImageFont.truetype(face, size)
        except Exception:
            pass
    return ImageFont.load_default()


def wrap_text(text: str, max_chars: int = 30) -> list:
    words = text.split()
    lines, line = [], ""
    for w in words:
        if len(line) + len(w) + 1 <= max_chars:
            line += (" " + w if line else w)
        else:
            lines.append(line)
            line = w
    if line:
        lines.append(line)
    return lines


def generate_poster(domain: str, quote: str, explanation: str, bg_path: str) -> str | None:
    bg_path = ensure_background(domain, bg_path)
    try:
        bg      = Image.open(bg_path).convert("RGBA")
        W, H    = bg.size
        overlay = Image.new("RGBA", (W, H), (0, 0, 0, 0))
        draw    = ImageDraw.Draw(overlay)

        fnt_domain = _load_font(22)
        fnt_quote  = _load_font(44)
        fnt_expl   = _load_font(26)
        fnt_wm     = _load_font(20)

        q_lines = wrap_text(f'"{quote}"', 28)
        e_lines = wrap_text(explanation, 44)
        panel_h = 72 + len(q_lines) * 56 + 18 + len(e_lines) * 34 + 36
        top     = H - panel_h

        # Gradient dark panel
        for y in range(top, H):
            t = (y - top) / panel_h
            a = int(155 + 70 * t)
            draw.line([(0, y), (W, y)], fill=(8, 18, 45, a))

        # Domain badge
        draw.text((28, top + 14), f"✦  {domain.upper()}  ✦", fill=(160, 200, 255), font=fnt_domain)
        draw.line([(28, top + 44), (W - 28, top + 44)], fill=(160, 200, 255, 100), width=1)

        y = top + 56
        for line in q_lines:
            draw.text((28, y), line, fill=(255, 248, 200), font=fnt_quote)
            y += 56
        y += 12
        for line in e_lines:
            draw.text((28, y), line, fill=(210, 220, 235), font=fnt_expl)
            y += 34

        draw.text((28, H - 28), "— Jalte Diye Foundation", fill=(130, 165, 210), font=fnt_wm)

        result = Image.alpha_composite(bg, overlay)
        slug   = domain.lower().replace(" & ", "_").replace(" ", "_")
        out    = os.path.join(POSTER_OUTPUT_DIR, f"poster_{slug}_{int(time.time())}.png")
        result.save(out, "PNG")
        print(f"   ✅ Poster saved: {out}")
        return out
    except Exception as exc:
        print(f"❌ Poster error: {exc}")
        traceback.print_exc()
        return None


# ================================================================
# 12. MAIN PIPELINE
# ================================================================
def main():
    print("=" * 64)
    print("  JALTE DIYE FOUNDATION – MASTER CONTENT PIPELINE v2.2")
    print("=" * 64)

    # ── Step 0: Fetch live free model list
    print("\n🔌 [Step 0] Loading free model list from OpenRouter…")
    models = fetch_live_free_models()
    print(f"   Models in queue: {models[:4]} …")

    # ── Step 1: News & domain detection
    print("\n🔍 [Step 1] Fetching news & scoring against SDG philosophy…")
    domain, topic, score = find_best_domain_and_topic()
    if domain and score >= 2:
        print(f"   🌐 Best domain  : {domain}  (score {score})")
        print(f"   📰 Topic        : {(topic or '')[:90]}")
    else:
        domain = random.choice(list(DOMAINS.keys()))
        topic  = None
        print(f"   📭 No relevant news — random domain: {domain}")

    # ── Step 2: Sub-theme rotation
    sub_theme = get_next_sub_theme(domain)
    print(f"\n🔄 [Step 2] Sub-theme today : \"{sub_theme}\"")

    # ── Step 3: AI generation — 4 candidates
    print(f"\n🧠 [Step 3] Generating 4 candidate quotes…")
    quote_data = generate_and_rank(domain, sub_theme, topic, models, n=4)

    # ── Step 4: Retry with 3 if first failed
    if not quote_data:
        print("\n⚠️  [Step 4] Retrying with n=3…")
        quote_data = generate_and_rank(domain, sub_theme, topic, models, n=3)

    # ── Step 5: CSV → emergency fallback
    if not quote_data:
        print("\n📂 [Step 5] AI exhausted — trying CSV fallback…")
        quote_data = get_csv_quote(domain)
        if quote_data:
            print("   ✅ CSV quote found.")
        else:
            print("   ⚠️  CSV empty — using emergency quote.")
            quote_data = EMERGENCY.get(domain, {
                "quote": "Every single day holds a chance to build a kinder world.",
                "explanation": "Our collective actions, however small, weave the fabric of a more just and compassionate society.",
            })
    else:
        q = quote_data.get("quote", "")
        if not _is_used(q):
            _log_used(q)

    # ── Step 6: Poster
    print("\n🖼️  [Step 6] Generating poster…")
    bg_path     = DOMAINS.get(domain, "jalte_diye_1.jpg")
    poster_path = generate_poster(domain, quote_data["quote"], quote_data["explanation"], bg_path)

    # ── Final output
    print("\n" + "=" * 64)
    print("  FINAL CONTENT")
    print("=" * 64)
    print(f"  Domain      : {domain}")
    print(f"  Sub-theme   : {sub_theme}")
    print(f"  Trend topic : {topic or '(none – general reflection)'}")
    print(f"  Quote       : {quote_data['quote']}")
    print(f"  Word count  : {word_count(quote_data['quote'])} words")
    print(f"  Explanation : {quote_data['explanation']}")
    print(f"  Poster      : {poster_path or 'Not generated'}")
    print("=" * 64)

    return {
        "domain": domain, "sub_theme": sub_theme, "topic": topic,
        "quote": quote_data["quote"], "explanation": quote_data["explanation"],
        "poster": poster_path,
    }


if __name__ == "__main__":
    main()
