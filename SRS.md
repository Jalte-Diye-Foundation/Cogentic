# Software Requirements Specification (SRS)

## Cogentic AI — Daily Automated Content Pipeline

**Document version:** 1.0
**Owner:** Jalte Diye Foundation
**Repository:** `Jalte-Diye-Foundation/Cogentic`

---

## 1. Introduction

### 1.1 Purpose

This document specifies the functional and non-functional requirements of
Cogentic AI, an automated system that generates, evaluates, renders, and
publishes one educational/social-impact quote post per day for the Jalte
Diye Foundation, for consumption by the
[reallyrealeducation.org](https://reallyrealeducation.org) website and (in
future) LinkedIn.

### 1.2 Scope

Cogentic AI is responsible for:
- Selecting a daily content theme (calendar-event-aware, with anti-repeat
  rotation).
- Generating a quote, short explanation, long-form explanation, and hashtags
  using the Google Gemini API.
- Evaluating the generated content's quality using a second Gemini call, with
  a bounded retry loop.
- Falling back to curated, pre-written CSV content (and ultimately a
  hardcoded emergency quote) if AI generation cannot produce acceptable
  content.
- Rendering a poster image (quote + short explanation only) using Pillow.
- Persisting the day's post as both a "latest" (overwritten daily) and
  "archived" (permanent, per-date) record inside the git repository.
- Preparing (but not yet fully implementing) a LinkedIn publishing step.

Out of scope: the `really-real-education` website repository itself (a
consumer of this system's output, maintained separately), and any UI/CMS.

### 1.3 Intended Audience

New developers or maintainers of the Cogentic repository who need to
understand, extend, or debug the daily content pipeline.

### 1.4 Definitions

| Term | Meaning |
|------|---------|
| Theme | One of six content categories (Peace & Justice, Climate & Environment, Quality Education, Health & Mindfulness, Women Empowerment, Foundation Events) |
| Poster | The rendered `.jpg` image containing the quote and short explanation |
| `latest/` | `website_assets/latest/` — always reflects the most recent post, overwritten every run |
| `archive/` | `website_assets/archive/<YYYY-MM-DD>/` — permanent, one folder per calendar date, never overwritten |
| Event day | A date present in `events.json`, forcing a specific theme |
| Fallback | Non-AI content sourced from a per-theme CSV file, or a hardcoded emergency quote |

---

## 2. Overall Description

### 2.1 Product Perspective

Cogentic is a standalone Python application triggered daily by a GitHub
Actions scheduled workflow (`.github/workflows/daily_content.yml`). It has no
persistent server, database, or UI. Its "database" is the git repository
itself: `website_assets/archive/` acts as the historical record and the
system's own memory (recent themes/quotes), and `used_quotes_log.txt` is a
flat-file global dedup ledger.

### 2.2 Product Functions (summary)

1. Determine today's theme (event override, or anti-repeat random rotation).
2. Select a random background image matching the theme.
3. Generate quote/explanation/long_explanation/hashtags via Gemini.
4. Evaluate the generated content via a second Gemini call; retry on failure.
5. Fall back to CSV or emergency content if generation/evaluation cannot
   succeed after retries.
6. Render a poster image with the quote and short explanation.
7. Persist output for the day to `output/`, then to `website_assets/latest/`
   and `website_assets/archive/<date>/`.
8. Commit and push the updated assets back to `main`.
9. (Optional/partial) Prepare and publish a LinkedIn post.

### 2.3 Users

- **Automated user:** the GitHub Actions scheduler (primary, daily, 03:30 UTC
  / 09:00 AM IST).
- **Human user:** a developer/maintainer triggering `workflow_dispatch`
  manually, or running `main.py` / `preview_tomorrow.py` locally for testing.
- **Downstream consumer:** the `really-real-education` repository's sync
  script, which reads `website_assets/latest/metadata.json` and
  `website_assets/archive/<date>/poster.jpg` over
  `raw.githubusercontent.com`.

### 2.4 Constraints

- Requires a valid `GEMINI_API_KEY` (repository secret in CI, environment
  variable locally) to perform AI generation/evaluation; without it, the
  pipeline cannot run at all (fallback paths still require a `ContentGenerator`
  instance to exist, which requires the key).
- LinkedIn publishing requires `LINKEDIN_ACCESS_TOKEN`; without it, the step
  is skipped (not an error).
- Runs on GitHub Actions' `ubuntu-latest` runner with Python 3.11.
- Must produce **at most one** archived post per calendar date.

---

## 3. Functional Requirements

### FR-1 — Theme Selection
**FR-1.1** The system SHALL check `events.json` for an entry matching today's
date (`MM-DD`). If found, the system SHALL use that entry's `theme` and pass
the event details into content generation.
**FR-1.2** If no event exists for today, the system SHALL randomly select a
theme from `config.json`'s `themes` map, EXCLUDING any theme used in the last
5 dates found in `website_assets/archive/`.
**FR-1.3** If all themes were used recently (no theme is excludable), the
system SHALL fall back to selecting from the full theme list.

### FR-2 — Background Selection
**FR-2.1** The system SHALL randomly select one image file from the selected
theme's configured folder under `themes/`, restricted to supported image
extensions (`.jpg`, `.jpeg`, `.png`, `.webp` by default).
**FR-2.2** If the theme folder is missing or has no valid images, the system
SHALL raise an error and halt (no silent skip).

### FR-3 — AI Content Generation
**FR-3.1** The system SHALL call the Gemini API requesting a JSON object with
`quote`, `explanation`, `long_explanation`, and `hashtags` fields, for the
selected theme (and event, if applicable).
**FR-3.2** The prompt SHALL instruct Gemini to avoid repeating the most
recent 15 quotes (read from `website_assets/archive/*/metadata.json`).
**FR-3.3** The system SHALL enforce word-count safety limits: `quote` ≤ 20
words, `explanation` ≤ 35 words, `long_explanation` ≤ 220 words, truncating
if Gemini exceeds them.
**FR-3.4** If the response is missing `quote` or `explanation`, or is not
valid JSON, the system SHALL treat this as a generation failure and route to
the retry/fallback logic.

### FR-4 — Quality Evaluation
**FR-4.1** The system SHALL send the generated `quote`/`explanation` to
Gemini a second time, requesting a `{score (1-10), reasoning}` JSON,
evaluating alignment with theme, clarity, and emotional impact.
**FR-4.2** Content SHALL be considered acceptable only if `score >=
passing_score` (default 7, configurable in `config.json`).

### FR-5 — Retry Logic
**FR-5.1** The system SHALL retry generation + evaluation up to
`max_retries` times (default 3) if content is rejected (duplicate quote or
low score), waiting `retry_delay_seconds` between attempts.
**FR-5.2** Duplicate quotes (already present in `used_quotes_log.txt`) SHALL
be treated as a rejected attempt without an evaluation call.
**FR-5.3** On accepted content, the system SHALL immediately append the
quote to `used_quotes_log.txt` to prevent any future reuse.

### FR-6 — Fallback Content
**FR-6.1** If all retries are exhausted, or an exception occurs during
generation/evaluation, the system SHALL retrieve a quote from the
theme-specific CSV file (`config.json` → `themes.<theme>.csv_fallback`),
excluding quotes already in `used_quotes_log.txt`.
**FR-6.2** If an event is active, the system SHALL prefer CSV rows whose
`occasion` column matches the event name, falling back to any unused row if
none match.
**FR-6.3** If the CSV file is missing, or has no unused rows, the system
SHALL use the hardcoded `emergency_failsafe` quote from `config.json`.
**FR-6.4** All fallback paths (CSV and emergency) SHALL synthesize a
non-empty `long_explanation` (since neither source provides one natively).

### FR-7 — Poster Rendering
**FR-7.1** The system SHALL render the `quote` and `explanation` (never
`long_explanation`) onto the selected background image using theme-specific
colors, alignment, and font settings.
**FR-7.2** Text SHALL be word-wrapped to fit within the image's configured
margins and vertically centered as a combined block.
**FR-7.3** The rendered poster SHALL be saved as a `.jpg` file at
`output/<YYYY-MM-DD>/poster.jpg`.

### FR-8 — Output Persistence
**FR-8.1** The system SHALL write `output/<date>/metadata.json` containing
`date`, `theme`, `quote`, `explanation`, `long_explanation`, `caption`,
`hashtags`, `image`, `source`, and `event` (or `null`).
**FR-8.2** A subsequent step (`website_assets/update_assets.py`) SHALL copy
the poster and write metadata to BOTH `website_assets/latest/` (overwritten
every run) AND `website_assets/archive/<date>/` (never overwritten once
written for a given date).

### FR-9 — One Post Per Calendar Day
**FR-9.1** Before generating any content, the system SHALL check whether
`website_assets/archive/<today>/` already exists and is non-empty. If so, the
system SHALL skip all generation/rendering steps and exit successfully
without modifying any files.
**FR-9.2** This check SHALL be based on `website_assets/archive/`, not
`output/`, because `output/` is not persisted across separate CI job runs and
therefore cannot reliably detect a same-day duplicate run.

### FR-10 — Automation & Commit
**FR-10.1** The GitHub Actions workflow SHALL run automatically once daily
(03:30 UTC / 09:00 AM IST) and SHALL also support manual triggering via
`workflow_dispatch`.
**FR-10.2** After a successful run, the workflow SHALL commit and push
`website_assets/latest/`, `website_assets/archive/`, and
`used_quotes_log.txt` to `main`, using a commit message tagged `[skip ci]` to
avoid re-triggering itself.
**FR-10.3** If there are no changes to commit (e.g. the run was skipped per
FR-9), the workflow SHALL exit cleanly without creating an empty commit.

### FR-11 — LinkedIn Publishing (partial/optional)
**FR-11.1** If `LINKEDIN_ACCESS_TOKEN` is not configured, the system SHALL
log and print a "skipped: token not configured" message and exit
successfully.
**FR-11.2** If configured, the system SHALL build a caption from
`website_assets/latest/metadata.json`, preferring `long_explanation` over
`explanation` when present, plus formatted hashtags.
**FR-11.3** The actual LinkedIn API call (image upload + UGC post creation)
is a documented integration point, not required to be fully implemented at
this stage.

### FR-12 — Logging
**FR-12.1** The system SHALL log every stage (theme/background selection,
Gemini responses, evaluation scores, fallback usage, output paths, errors
with stack traces) to `logs/cogentic.log` and stdout.

---

## 4. Non-Functional Requirements

| ID | Requirement |
|----|-------------|
| NFR-1 | **Configurability** — all thresholds, paths, theme definitions, and font/layout settings SHALL live in `config.json`, not hardcoded in Python. |
| NFR-2 | **Idempotency** — re-running the pipeline for a date that is already archived SHALL be a safe no-op (see FR-9). |
| NFR-3 | **Resilience** — a Gemini API outage or malformed response SHALL NOT crash the pipeline; it SHALL fall back to CSV/emergency content. |
| NFR-4 | **Auditability** — every post SHALL be permanently retrievable from `website_assets/archive/<date>/`, and every quote used SHALL be recorded in `used_quotes_log.txt`. |
| NFR-5 | **Portability** — the pipeline SHALL run identically via GitHub Actions or a local developer machine, given the same environment variables. |
| NFR-6 | **Separation of concerns** — poster-visible text (`quote`, `explanation`) and web-only text (`long_explanation`) SHALL be tracked as distinct fields throughout the pipeline and never conflated. |
| NFR-7 | **No secrets in source** — API keys SHALL only be supplied via environment variables / GitHub Actions secrets, never committed to the repository. |

---

## 5. External Interfaces

### 5.1 Google Gemini API
- Used by `content/generator.py` (content generation) and
  `content/evaluator.py` (quality scoring).
- Model configured in `config.json` → `gemini.model` (currently
  `gemini-2.5-flash`).
- Authentication via `GEMINI_API_KEY` environment variable.

### 5.2 LinkedIn API (partial)
- Used by `publishing/linkedin_publisher.py`.
- Authentication via `LINKEDIN_ACCESS_TOKEN` environment variable.
- Endpoint base configured in `config.json` → `linkedin.api_base_url`.

### 5.3 `really-real-education` Repository (downstream consumer)
- Reads `website_assets/latest/metadata.json` and
  `website_assets/archive/<date>/poster.jpg` from this repository's `main`
  branch via `raw.githubusercontent.com`.
- Any change to the `metadata.json` schema (field names/types) is a
  cross-repository breaking change and must be coordinated with that repo's
  `scripts/sync-cogentic-content.js`.

---

## 6. Data Requirements

### 6.1 `metadata.json` Schema (canonical)

| Field | Type | Description |
|-------|------|--------------|
| `date` | string (`YYYY-MM-DD`) | The calendar date this post is for |
| `theme` | string | One of the six configured theme names |
| `quote` | string | 10–20 word quote (drawn on poster) |
| `explanation` | string | 2-sentence, ≤35-word explanation (drawn on poster) |
| `long_explanation` | string | 8–10 sentence, 150–200 word web-only explanation |
| `caption` | string | Combined quote+explanation, used for social captions |
| `hashtags` | array of strings | 4–6 hashtags |
| `image` | string | Relative path to the poster image |
| `source` | string | Always `"Cogentic AI"` |
| `event` | string or `null` | Name of the calendar event, if any (output-side only) |

### 6.2 Persistent Files

| File/Folder | Committed to git? | Purpose |
|---|---|---|
| `output/<date>/` | No | Transient per-run working directory |
| `logs/cogentic.log` | No | Transient per-run log |
| `website_assets/latest/` | Yes | "Current" post state, overwritten daily |
| `website_assets/archive/<date>/` | Yes | Permanent per-date record; pipeline's own memory |
| `used_quotes_log.txt` | Yes | Flat, append-only global dedup ledger |
| `events.json` | Yes | Static calendar-to-theme mapping |
| `config.json` | Yes | Static runtime configuration |

---

## 7. Assumptions and Dependencies

- Assumes `GEMINI_API_KEY` is valid and has sufficient quota for 1 generation
  call + up to 3 evaluation calls per day (more on retries).
- Assumes the GitHub Actions runner has write access to push to `main`
  (`contents: write` permission, configured in the workflow file).
- Assumes theme folders under `themes/` always contain at least one valid
  background image for each configured theme.
- Assumes CSV fallback files are periodically curated/refreshed by
  maintainers so they don't run out of unused quotes over time.

## 8. Known Limitations (as of this document's writing)

- LinkedIn publishing is prepared but the actual API call is not yet
  implemented (see FR-11.3).
- CSV fallback and emergency `long_explanation` text is templated/synthesized
  rather than uniquely AI-generated, since those paths don't call Gemini.
- There is no automated test suite; `test_alignment.py` and
  `preview_tomorrow.py` are manual developer utilities, not CI-gated tests.
