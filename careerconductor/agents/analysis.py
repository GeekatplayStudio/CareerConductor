"""Analysis & valuation agent: scores discovered jobs against the candidate's
personal criteria via the Claude API.

HOW THE PROMPT IS STRUCTURED (teaching note):
- The scoring rubric — including the candidate's criteria — is identical for
  every job in a run, so it goes in the SYSTEM block marked for prompt caching.
  Only the first call pays full input price for it; every later job reads it
  from cache at a fraction of the cost.
- The per-job content (company/title/posting text) goes in the USER message,
  which changes per call and therefore can't be cached.
- We ask for strict JSON and parse defensively (_extract_json) because models
  occasionally wrap JSON in prose despite instructions; a regex for the outer
  braces recovers those cases instead of failing the job.
- One bad job must never kill the batch: each job is scored inside its own
  try/except, and failures are logged and skipped.
"""
from __future__ import annotations

import json
import re

import anthropic

from careerconductor.config.settings import settings
from careerconductor.config.store import criteria_prompt_block, load_criteria
from careerconductor.db.repository import CareerConductorDB

from .llm import cached_system_block, claude_call
from .state import CareerEngineState, JobOpportunity

_SCORING_RUBRIC_TEMPLATE = """You are evaluating job postings for this candidate:

{criteria}

Score every posting the user sends on these dimensions (all floats 0-10):
- match_score: how well the role fits the candidate's target roles, background, and
  dealbreakers above. 10 = written for them, 0 = wrong career entirely.
- interview_friction: 10 = worst (heavy LeetCode/live-coding signals), 0 = pure
  system-design/portfolio process. Score against the candidate's interview preferences.
- stability_score: 10 = long operating history, strong funding/revenue; 0 = pre-seed,
  layoffs, or existential risk signals.
- location_fit_score: 10 = matches the candidate's acceptable locations; 0 = rigid
  on-site far away with no remote option.
- salary_score: 10 = comfortably above the candidate's minimum; 5 = right at it;
  0 = clearly below. If the posting lists no salary, estimate a fair market range
  for the role's seniority and the local market first, then score against that.

Also extract:
- salary_floor / salary_ceiling: integers, USD annual. Use the posting's numbers if
  listed, otherwise your market estimate (and set salary_is_estimated=true).
- perks: one short line of notable bonuses/benefits (equity, 4-day week, sabbatical,
  bonus structure), or "" if nothing stands out.
- notes: one short line on anything else the candidate might have missed — good or
  bad — e.g. "role reports to CTO", "posting is 90 days old", "on-call heavy".

Respond with ONLY a JSON object, no prose:
{{
  "match_score": <float>, "interview_friction": <float>, "stability_score": <float>,
  "location_fit_score": <float>, "salary_score": <float>,
  "salary_floor": <int>, "salary_ceiling": <int>, "salary_is_estimated": <bool>,
  "perks": "<string>", "notes": "<string>"
}}"""

_JOB_TEMPLATE = """Company: {company}
Title: {title}
Location: {location}
Raw text:
{raw_text}"""


def _extract_json(text: str) -> dict:
    match = re.search(r"\{.*\}", text, re.DOTALL)
    if not match:
        raise ValueError(f"no JSON object found in model response: {text!r}")
    return json.loads(match.group(0))


def run_analysis(state: CareerEngineState, db: CareerConductorDB) -> CareerEngineState:
    logs = list(state.get("execution_logs", []))
    client = anthropic.Anthropic(api_key=settings.anthropic_api_key)

    # Criteria are loaded at run time (not import time) so edits saved in the UI
    # apply to the very next run without restarting the process.
    rubric = _SCORING_RUBRIC_TEMPLATE.format(criteria=criteria_prompt_block(load_criteria()))
    system = cached_system_block(rubric)
    scored: list[JobOpportunity] = []

    for job in state.get("discovered_jobs", []):
        user_content = _JOB_TEMPLATE.format(
            company=job.get("company", ""),
            title=job.get("title", ""),
            location=job.get("location", ""),
            raw_text=(job.get("raw_text") or "")[:6000],  # cap: postings can be huge
        )
        try:
            result = _extract_json(
                claude_call(client, system=system, user_content=user_content, max_tokens=700)
            )

            job = dict(job)  # copy: never mutate state entries in place
            job["match_score"] = float(result["match_score"])
            job["interview_friction"] = float(result["interview_friction"])
            job["stability_score"] = float(result["stability_score"])
            job["location_fit_score"] = float(result["location_fit_score"])
            job["salary_score"] = float(result["salary_score"])
            job["salary_range"] = {
                "floor": float(result["salary_floor"]),
                "ceiling": float(result["salary_ceiling"]),
            }
            job["salary_is_estimated"] = bool(result["salary_is_estimated"])
            job["perks"] = str(result.get("perks", ""))
            job["notes"] = str(result.get("notes", ""))

            # Persist immediately so a crash mid-batch loses nothing already scored.
            db.update_ratings(
                job_hash=job["job_hash"],
                stability=job["stability_score"],
                friction=job["interview_friction"],
                location_fit=job["location_fit_score"],
                salary_floor=int(result["salary_floor"]),
                salary_ceiling=int(result["salary_ceiling"]),
                salary_is_estimated=bool(result["salary_is_estimated"]),
                match=job["match_score"],
                salary_fit=job["salary_score"],
                perks=job["perks"],
                notes=job["notes"],
            )
            scored.append(job)
        except Exception as exc:  # noqa: BLE001 - one bad job shouldn't kill the batch
            logs.append(f"analysis failed for {job.get('company')} / {job.get('title')}: {exc}")

    logs.append(f"analyzed {len(scored)} of {len(state.get('discovered_jobs', []))} discovered jobs")
    return {**state, "discovered_jobs": scored, "execution_logs": logs}
