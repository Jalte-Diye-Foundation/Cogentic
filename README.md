# Cogentic AI

**Cognitive Agentic AI System for Social Education & Poster Automation**

Cogentic AI is an automated, AI-assisted content publishing and visual poster automation system developed for the [Jalte Diye Foundation](https://github.com/Jalte-Diye-Foundation). It generates educational and social-impact quotes daily, scores their quality using AI, renders responsive, dynamically-aligned typography composites onto theme backgrounds, archives assets for website delivery, and prepares automated publishing pipelines.

---

## 1. Current vs Future Capabilities

### Currently Implemented & Active
- **Gemini Content Generation:** Generates daily educational and theme-aligned content using the Google GenAI SDK.
- **AI Quality Evaluation:** Strict automated quality scoring with retry loop.
- **Date-Aware Event Engine:** Calendar-aware theme selection locked to Indian Standard Time (`Asia/Kolkata`).
- **Adaptive Poster Rendering:** Dynamic font scaling, line wrapping, and safe-zone bounding using Pillow (PIL) with guaranteed zero text overflow.
- **CSV Fallback System:** Curated theme and date-safe festival fallback datasets with duplicate prevention.
- **Website Asset Generation:** Automatic generation and archival of `poster.jpg` and `metadata.json` for frontend consumption.
- **GitHub Actions Automation:** Scheduled daily execution at 09:00 AM IST with artifact preservation.

### Future Integrations (Planned Roadmap)
- **Automatic Social Publishing:** Direct publishing dispatch to LinkedIn, Meta/Instagram, and WhatsApp Business channels upon credential configuration.
- **CMS API Integration:** Automated push of generated metadata and images to a headless CMS or cloud storage (S3/GCS/CDN).
- **Vector Memory & Semantic Deduplication:** Semantic quote history retrieval using vector embeddings.
- **Multilingual Support:** Multi-language poster generation (Hindi and regional languages).
- **Analytics Feedback Loop:** Ingesting website and social engagement metrics to refine thematic selection.

---

## 2. Architecture

```text
GitHub Actions Scheduler (09:00 AM IST) / Manual Run
                     ↓
        Cogentic Engine (main.py)
                     ↓
   Date-Aware Event & Theme Selection (Asia/Kolkata)
        ├─ Event Active (e.g. Lohri on Jan 13, Independence Day on Aug 15)
        └─ Non-Event Day → Evergreen Rotation (5 Core Themes)
                     ↓
        Gemini Content Generation
                     ↓
         AI Quality Evaluation (Score >= 7/10)
        ├─ Pass → Proceed
        └─ Fail/Duplicate → Retry (up to 3x) → Date-Aware CSV Fallback
                     ↓
   Poster Rendering Engine (Dynamic Fit-to-Bounds PIL)
                     ↓
         Output Generation (output/YYYY-MM-DD/)
                     ↓
       Website Asset Update & Archival (website_assets/)
                     ↓
      LinkedIn Publishing Dispatch (publishing/)
```

---

## 3. Daily Pipeline Workflow

| Stage | Module | Description |
|---|---|---|
| **1. Date Resolution** | `scheduler/daily_runner.py` | Resolves current timestamp in Indian Standard Time (`Asia/Kolkata`, UTC+5:30). |
| **2. Event / Theme Selection** | `scheduler/daily_runner.py` | Priority lookup in `events.json`. Non-event days rotate through evergreen themes only. |
| **3. Background Selection** | `scheduler/daily_runner.py` | Selects high-resolution background asset from corresponding `themes/<theme>/` directory. |
| **4. Content Generation** | `content/generator.py` | Gemini generates theme- or event-specific quote, 2-sentence explanation, and hashtags. |
| **5. AI Evaluation** | `content/evaluator.py` | Evaluator scores alignment, clarity, and impact (passing score: >= 7/10). |
| **6. Retry & Deduplication** | `scheduler/daily_runner.py` | Checks `used_quotes_log.txt` and retry counter (up to 3 attempts). |
| **7. Date-Aware Fallback** | `content/fallback.py` | Loads unused quotes from CSV. Event days strictly match the current event; evergreen themes match theme CSVs. |
| **8. Adaptive Poster Render** | `image_gen.py` | Measures and dynamically scales typography so text strictly fits inside the safe zone with zero overflow. |
| **9. Output & Metadata** | `scheduler/daily_runner.py` | Saves `poster.jpg` and `metadata.json` to `output/YYYY-MM-DD/`. |
| **10. Website Asset Update** | `website_assets/update_assets.py` | Deploys asset to `website_assets/latest/` and archives in `website_assets/archive/YYYY-MM-DD/`. |
| **11. Social Publishing** | `publishing/linkedin_publisher.py` | Prepares LinkedIn post and dispatches when token is present. |

---

## 4. Theme Selection

The foundation operates across 5 core **Evergreen Themes**:
1. **Peace & Justice** (`themes/peace`, `peace_justice.csv`)
2. **Climate & Environment** (`themes/climate`, `climate.csv`)
3. **Quality Education** (`themes/education`, `quality_education.csv`)
4. **Women Empowerment** (`themes/women`, `reduced_inequalities.csv`)
5. **Health & Mindfulness** (`themes/health`, `quotes.csv`)

On regular non-event days, the system strictly cycles among these 5 themes, avoiding themes used in the last 4–5 posts.

---

## 5. Date-Aware Event Selection

To eliminate seasonal errors (such as generating January events like *Lohri* in August):
- **Single Source of Truth:** `events.json` maps calendar dates (`MM-DD`) to specific cultural and national observances.
- **IST Timezone Locking:** All date evaluations use `Asia/Kolkata` (UTC+5:30) to prevent day-drift across cloud runners.
- **Event Isolation:** `Foundation Events` is **never** included in random evergreen rotation. It is triggered only when the current IST date matches an active event in `events.json`.
- **Date-Filtered Fallback:** If CSV fallback triggers on an event day, `FallbackProvider` strictly matches `Event_quotes.csv` rows for that specific event name or date. It never pops random or out-of-season rows.

---

## 6. Gemini Content Generation

The generation module (`content/generator.py`) leverages the Google GenAI SDK (`gemini-2.5-flash`):
- Injects previous quote history to prevent repetitive phrasing.
- Injects special event instructions when an event is active.
- Enforces strict constraints: inspirational tone, 10–20 word quotes, exactly 2-sentence explanations (max 35 words), and relevant hashtags.

---

## 7. AI Quality Evaluation

The evaluation engine (`content/evaluator.py`):
- Acts as a strict Quality Control Editor.
- Assesses thematic relevance, clarity, grammar, and emotional resonance.
- Returns a structured score (1–10) and reasoning. Content must achieve `>= 7/10` to pass to rendering.

---

## 8. Retry & Deduplication

- **Deduplication:** Every candidate quote is normalized and checked against `used_quotes_log.txt`.
- **Retry Mechanism:** If a quote is duplicate or receives an evaluation score `< 7`, the runner delays briefly and retries generation up to 3 times before invoking CSV fallback.

---

## 9. CSV Fallback Mechanics

When Gemini is unreachable or exhausts retry attempts:
- `FallbackProvider` accesses theme-mapped CSV datasets.
- Supports both standard column headers (`Quote`, `Caption`, `Event`, `Occasion`) and headerless legacy datasets (e.g., `quotes.csv`).
- Appends retrieved fallback quotes to `used_quotes_log.txt` to prevent repetition.
- Features a hardcoded emergency failsafe for ultimate resilience.

---

## 10. Poster Rendering & Dynamic Alignment

The rendering engine (`image_gen.py` & `rendering/poster_generator.py`) uses an **adaptive fit-to-bounds** algorithm:
- **Responsive Typography:** Proportional base font sizing with automatic step-down reduction if content length exceeds available vertical space.
- **Safe Zone Clamping:** Strict vertical bounding (`center_zone_top_ratio` to `center_zone_bottom_ratio`) and balanced margins (`margin_left_ratio`, `margin_right_ratio`) prevent text from colliding with background artwork or logos.
- **Word Wrapping:** Gracefully breaks text into lines without splitting words or losing line breaks.
- **Vertical Centering:** Centers the total composite block (Quote + Gap + Explanation) evenly within the safe zone.

---

## 11. Output Structure

```text
output/
└── YYYY-MM-DD/
    ├── poster.jpg       # High-quality rendered composite (JPEG, Q=95)
    └── metadata.json    # Full post metadata sidecar
```

`metadata.json` schema:
```json
{
  "date": "2026-08-30",
  "theme": "Quality Education",
  "quote": "Education is the light that no darkness can extinguish.",
  "explanation": "When we invest in learning, we build a fire that no ignorance can ever fully blow out.",
  "caption": "Education is the light that no darkness can extinguish.\n\nWhen we invest in learning...",
  "hashtags": ["#Education", "#Cogentic", "#JalteDiyeFoundation"],
  "image": "poster.jpg",
  "source": "Cogentic AI",
  "event": null
}
```

---

## 12. Website Integration

The website at [reallyrealeducation.org/posts.html](https://reallyrealeducation.org/posts.html) fetches the live post assets from:
- `website_assets/latest/poster.jpg`
- `website_assets/latest/metadata.json`

Historical posts are versioned in `website_assets/archive/YYYY-MM-DD/`.

---

## 13. GitHub Actions Automation

Workflow: `.github/workflows/daily_content.yml`
- **Schedule:** Automated daily trigger at **09:00 AM IST** (`30 3 * * *` UTC cron).
- **Manual Trigger:** `workflow_dispatch` enabled in GitHub Actions tab.
- **Steps:** Checks out repository, installs dependencies, executes `python main.py`, updates website assets, commits changes with `[skip ci]`, and uploads run artifacts.

---

## 14. Running & Testing

### Installation
```bash
git clone https://github.com/nupurmadaan04/Cogentic.git
cd Cogentic
python -m venv .venv
source .venv/bin/activate    # Windows: .venv\Scripts\activate
pip install -r requirements.txt
```

### Running Daily Pipeline
```bash
export GEMINI_API_KEY="your_api_key_here"   # Windows PowerShell: $env:GEMINI_API_KEY="..."
python main.py
```

### Running Test Suite
```bash
python test_pipeline.py
```

---

## 15. Configuration Reference (`config.json`)

- `gemini`: Model name (`gemini-2.5-flash`) and API key environment variable.
- `quality`: Threshold score (`passing_score: 7`), max retries (`3`), delay.
- `paths`: Output, logs, website assets, and used quote log locations.
- `website`: Asset filenames and labels.
- `themes`: Theme folder paths and CSV fallback mappings.
- `poster`: Font configurations and output compression parameters.
- `emergency_failsafe`: Hardcoded quote failsafe.
