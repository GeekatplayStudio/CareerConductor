# CareerConductor

A local-first, multi-agent job scouting and application-tailoring engine.
It scrapes company job boards you whitelist, scores every posting against
**your** personal criteria with AI, and generates a tailored resume and cover
letter for the best matches — while a SQLite ledger guarantees you never
process the same posting twice.

Built with **LangGraph** (agent orchestration), **Claude API** (scoring,
artifact generation, and CV web-page generation, with prompt caching),
**Gemini API** (cheap batch pre-filtering), and **Streamlit** (control panel UI).

> This repo is intentionally written as a teaching example: every module has
> a "why it's built this way" note at the top, and design decisions are
> explained inline where they happen. Read the source top-down starting at
> `careerconductor/agents/orchestrator.py`.

---

## Architecture

```
                    ┌──────────────────────────────┐
                    │  Super Agent (LangGraph)      │
                    │  agents/orchestrator.py       │
                    └──────────────┬───────────────┘
                                   │  immutable state dict flows node → node
   ┌───────────┬───────────────┬──┴─────────┬──────────────────┬─────────────┐
   ▼           ▼               ▼            ▼                  ▼             ▼
 scrape     prefilter       analyze       select       generate_artifacts  referral
 (official  (Gemini,        (Claude,     (rank by       (Claude, cached    notes
 board      30 jobs/call,   cached       composite      resume+letter      (manual
 APIs,      fail-open)      rubric,      score, cap N)  per job)           lookup list)
 dedup                      criteria-
 via hash)                  driven)
   │                           │                            │
   └───────────────────────────┴────────────────────────────┘
                               ▼
                    SQLite (db/repository.py)
        jobs_master · applications_ledger · uploaded_files
```

Two features sit outside the graph and run on demand from the UI rather than
as pipeline stages: the **Templates** page (`templates/resume_templates.py`)
picks the style `generate_artifacts` tailors resumes into, and the **CV web
page generator** (`templates/cv_webpage.py`) turns your master resume into a
downloadable, self-contained HTML page in that same style.

**Key design decisions** (each explained in detail where implemented):

| Decision | Where | Why |
|---|---|---|
| Official job-board APIs, no anti-bot evasion | `scrapers/` | Reliable, ToS-clean, self-identifying user-agent + rate limiting |
| Hash-based idempotency | `db/repository.py` | Re-runs never reprocess or re-apply; `sha256(company + job id)` is the primary key |
| Cheap model screens, expensive model scores | `agents/prefilter_node.py` | Gemini drops obvious misfits in 30-job batches before Claude spends tokens |
| Prompt caching for repeated context | `agents/llm.py` | Scoring rubric + master resume are static per run — cache once, reuse per job |
| Retries only on transient errors | `agents/llm.py` | Rate limits/5xx retry with backoff; auth/bad-request errors surface immediately |
| Fail-open pre-filter | `agents/prefilter_node.py` | A screening-stage outage must never silently lose a good job |
| Per-job try/except in batch loops | `agents/analysis.py` | One malformed posting can't kill the whole run |
| Ranked cap on artifact generation | `agents/selection.py` | Cost control: only the best N eligible jobs get (2 Claude calls each) |
| Runtime-loaded JSON config | `config/store.py` | UI edits apply on the next run, no restart, no code changes |
| ALTER TABLE migrations, errors ignored if applied | `db/repository.py` | Dependency-free schema upgrades for a single-user local DB |
| Never-analyzed jobs re-queue automatically | `agents/scraping_node.py` | A transient scoring failure must not permanently lose a posting to hash dedup |
| Templates are data, not code | `templates/resume_templates.py` | Adding a resume style is one registry entry — no new logic anywhere |
| UI-selector collisions avoided with hash-suffixed labels | `ui/pages/4_Report.py` | Two postings can share company+title; dropdown keys must stay unique |
| UTF-8 Encoding | Everywhere | Specify `encoding="utf-8"` in all I/O to support non-ASCII characters on Windows/macOS/Linux |
| SQLite Foreign Keys | `db/repository.py` | Explicitly enforce `PRAGMA foreign_keys = ON` to protect ledger integrity |
| File existence checks | `ui/pages/3_Run_Pipeline.py` & `main.py` | Pre-checks prevent pipeline crashes when starting from a fresh environment |

## Quick start

**Mac** — double-click (or run from a terminal):
```
install.command  then edit .env with your keys, then:
start.command
```

**Linux / Terminal**
```bash
./install.sh     # step-by-step: checks Python, creates .venv, installs, seeds .env
# edit .env and add your API keys
./start.sh       # opens the control panel at http://localhost:8501
```

**Windows** — double-click (or run from a terminal in the project folder):
```
install.bat      then edit .env with your keys, then:
start.bat
```

API keys (both pay-as-you-go / free-tier, **not** consumer subscriptions):
- `ANTHROPIC_API_KEY` — console.anthropic.com (required)
- `GEMINI_API_KEY` — aistudio.google.com (optional; skips pre-filter if absent)

## Using the control panel

1. **Upload** — drop in your master resume (`.md`/`.txt`) and project database
   (`.json`). Every upload is content-hashed and recorded in the `uploaded_files`
   table, so you can always see what's live and when it changed.
2. **Configuration** —
   - *Personal criteria*: plain-language description of what you want (roles,
     locations, minimum salary, interview style, dealbreakers). These lines are
     injected verbatim into every AI prompt.
   - *Whitelist*: paste any `boards.greenhouse.io/...`,
     `job-boards.greenhouse.io/...`, or `jobs.lever.co/...` careers URL
     (Greenhouse embed URLs work too). The app detects the platform, **verifies
     it against the official API**, and adds it. Manual grid editing also available.
   - *Thresholds*: score gates + the per-run artifact cap.
3. **Run Pipeline** — one button; live log; a 3D agent-network animation that
   goes from idle to "working" while the graph runs; results link.
4. **Report** — pipeline funnel, stability/friction scatter, salary chart,
   a score-profile radar comparing your top 5 candidates head-to-head, a
   pay-vs-fit quadrant, a discovery timeline, the ranked top-candidates table
   (match/salary-fit scores, perks, AI notes), artifact preview/download, and
   status management (applied/archived).
5. **Templates** — ten resume styles across categories (ATS-optimized,
   corporate, modern, technical, creative, startup, academic, consulting,
   hybrid). The selected style steers every generated resume's structure and
   tone. Also generates a **self-contained HTML CV web page** in that style —
   preview it in-app and download the single file (host anywhere, prints cleanly).

Everything persists locally: configuration in JSON files under
`careerconductor/config/`, all job data in `careerconductor.db` (SQLite).
Configure once — subsequent runs only need the Run button.

The interface itself (`ui/theme.py`) is a dark glassmorphism theme shared by
every page: gradient headers, glass panels with a 3D hover tilt, and the
canvas-based agent-network visualization — no external CSS/JS dependencies,
so it works fully offline.

## CLI (headless) run

```bash
./scripts/run_pipeline.sh     # same pipeline, no UI — cron-friendly (Mac/Linux)
```

## Tests

```bash
./.venv/bin/pytest careerconductor/tests/ -v      # Mac/Linux
.venv\Scripts\pytest careerconductor\tests\ -v     # Windows
```

No API keys or network needed: pipeline nodes are plain functions over dicts and
the repository accepts any SQLite path, so everything runs against throwaway
fixtures — that testability is itself one of the design points being demonstrated.
Covers: hash idempotency, rating persistence, schema migration on a pre-upgrade
database, the requeue-on-failure contract, selection gate/rank/cap behavior,
whitelist URL detection, the template registry, and criteria prompt rendering.

## Scoring model

Each posting gets five 0–10 scores plus a salary estimate and two free-text fields:

| Dimension | Meaning |
|---|---|
| `match_rating` | Fit vs. your personal criteria (roles, background, dealbreakers) |
| `stability_rating` | Company longevity/funding signals |
| `friction_rating` | Interview process pain — 10 = heavy live coding (lower is better) |
| `location_fit_rating` | Fit vs. your acceptable locations |
| `salary_rating` | Compensation vs. your stated minimum |
| `perks` / `analysis_notes` | Free-text: notable benefits + anything you might have missed |

Composite ranking (used identically in `agents/selection.py`,
`db/repository.top_candidates`, and the Report page):

```
score = match + stability − friction + location_fit + salary_fit
```

Jobs must pass the three threshold gates to be eligible; the top
`max_artifacts_per_run` by score get a tailored resume + cover letter.

## Project layout

```
install.sh / start.sh          # Linux: setup and launch, run from repo root
install.command / start.command # Mac: same, double-clickable from Finder
install.bat / start.bat        # Windows: same, double-clickable
careerconductor/
├── agents/            # LangGraph nodes — one file per pipeline stage
│   ├── orchestrator.py    # builds the graph; START HERE when reading
│   ├── state.py           # the typed state dict that flows between nodes
│   ├── scraping_node.py   # official-API scraping + dedup + requeue-on-failure
│   ├── prefilter_node.py  # Gemini batch relevance screen (fail-open)
│   ├── analysis.py        # Claude scoring vs. personal criteria
│   ├── selection.py       # threshold gates + ranked cap
│   ├── artifact_generator.py  # tailored resume + cover letter
│   ├── referral_notes.py  # manual-lookup referral list (ToS-safe)
│   └── llm.py             # shared Claude call: retries + prompt caching
├── config/            # runtime-editable JSON config + loaders
│   ├── store.py           # dataclass schemas + load/save helpers
│   └── board_detect.py    # pasted URL -> verified ScrapeTarget
├── db/                # SQLite persistence
│   ├── schema.sql         # tables, commented column-by-column
│   └── repository.py      # all queries; migration mechanism
├── scrapers/          # Greenhouse + Lever official API clients
├── templates/          # resume style registry + CV web page generator
│   ├── resume_templates.py    # 10 styles as data; selection persisted
│   └── cv_webpage.py          # single-file HTML CV generation
├── ui/                # Streamlit control panel (pages/ = sidebar entries)
│   ├── app.py              # dashboard / entry page
│   ├── theme.py             # shared glass theme + 3D agent-network component
│   ├── common.py            # sidebar status, shared DB accessor
│   └── pages/                # Upload, Configuration, Run Pipeline, Report, Templates
├── tests/              # pytest suite — no API keys/network required
└── main.py            # CLI entrypoint
scripts/               # headless cron runner (run_pipeline.sh)
```

## What this project deliberately does NOT do

- **No anti-bot evasion** (fingerprint spoofing, human-emulation mouse curves).
  Official public APIs are more reliable and don't put you in an arms race.
- **No consumer-subscription automation** (driving claude.ai/gemini web UIs via
  session cookies). That violates ToS and breaks on every UI change; the metered
  APIs with caching cost single-digit dollars for a full job search.
- **No LinkedIn scraping.** The referral stage produces a "check these companies
  manually" list instead.
