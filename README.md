# CareerConductor

A local-first, multi-agent job scouting and application-tailoring engine.
It scrapes company job boards you whitelist, scores every posting against
**your** personal criteria with AI, and generates a tailored resume and cover
letter for the best matches — while a SQLite ledger guarantees you never
process the same posting twice.

Built with **LangGraph** (agent orchestration), **Claude API** (scoring +
artifact generation, with prompt caching), **Gemini API** (cheap batch
pre-filtering), and **Streamlit** (control panel UI).

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

## Quick start

```bash
./scripts/install.sh          # creates .venv, installs the package, seeds .env from the template
# edit .env and add your API keys
./scripts/run_ui.sh           # opens the control panel at http://localhost:8501
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
3. **Run Pipeline** — one button; live log; results link.
4. **Report** — pipeline funnel, stability/friction scatter, salary chart,
   ranked top-candidates table (with match/salary-fit scores, perks, and AI
   notes), artifact preview/download, and status management (applied/archived).

Everything persists locally: configuration in JSON files under
`careerconductor/config/`, all job data in `careerconductor.db` (SQLite).
Configure once — subsequent runs only need the Run button.

## CLI (headless) run

```bash
./scripts/run_pipeline.sh     # same pipeline, no UI — cron-friendly
```

## Tests

```bash
./.venv/bin/pytest careerconductor/tests/ -v
```

No API keys or network needed: pipeline nodes are plain functions over dicts and
the repository accepts any SQLite path, so everything runs against throwaway
fixtures — that testability is itself one of the design points being demonstrated.

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
careerconductor/
├── agents/            # LangGraph nodes — one file per pipeline stage
│   ├── orchestrator.py    # builds the graph; START HERE when reading
│   ├── state.py           # the typed state dict that flows between nodes
│   ├── scraping_node.py   # official-API scraping + dedup
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
├── ui/                # Streamlit control panel (pages/ = sidebar entries)
└── main.py            # CLI entrypoint
scripts/               # install / run helpers
```

## What this project deliberately does NOT do

- **No anti-bot evasion** (fingerprint spoofing, human-emulation mouse curves).
  Official public APIs are more reliable and don't put you in an arms race.
- **No consumer-subscription automation** (driving claude.ai/gemini web UIs via
  session cookies). That violates ToS and breaks on every UI change; the metered
  APIs with caching cost single-digit dollars for a full job search.
- **No LinkedIn scraping.** The referral stage produces a "check these companies
  manually" list instead.
