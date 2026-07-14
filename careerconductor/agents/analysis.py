"""Analysis & valuation agent: scores discovered jobs via the Claude API.

The scoring rubric is identical for every job, so it's sent as a cached system
block — only the first call in a run pays full input price for it; subsequent
jobs read it from cache. Transient API failures retry via the shared policy.
"""
from __future__ import annotations

import json
import re

import anthropic

from careerconductor.config.settings import settings
from careerconductor.db.repository import CareerConductorDB

from .llm import cached_system_block, claude_call
from .state import CareerEngineState, JobOpportunity

_SCORING_RUBRIC = """You are evaluating job postings for a candidate who wants:
- LOW interview friction: prefers system design / architecture / portfolio discussions over
  LeetCode-style live coding or HackerRank timed tests.
- HIGH company stability: established companies with funding/revenue history over
  early-stage pre-seed startups or companies with recent large layoffs.
- Utah Salt Lake Valley location fit: Salt Lake City, Draper, South Jordan, Lehi, American Fork,
  Sandy, Provo, Orem, or fully remote score high; rigid out-of-state on-site requirements score low.
- A fair market salary estimate if the posting doesn't list one, based on the role's seniority,
  title, and the Lehi/American Fork/Salt Lake tech corridor market.

For each posting the user sends, respond with ONLY a JSON object, no prose, in exactly this shape:
{
  "interview_friction": <float 0-10, 10 = worst (heavy live coding)>,
  "stability_score": <float 0-10, 10 = best (very stable)>,
  "location_fit_score": <float 0-10, 10 = best fit>,
  "salary_floor": <int, USD annual, your best estimate if unlisted>,
  "salary_ceiling": <int, USD annual, your best estimate if unlisted>,
  "salary_is_estimated": <true|false>
}"""

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
    system = cached_system_block(_SCORING_RUBRIC)
    scored: list[JobOpportunity] = []

    for job in state.get("discovered_jobs", []):
        user_content = _JOB_TEMPLATE.format(
            company=job.get("company", ""),
            title=job.get("title", ""),
            location=job.get("location", ""),
            raw_text=(job.get("raw_text") or "")[:6000],
        )
        try:
            result = _extract_json(
                claude_call(client, system=system, user_content=user_content, max_tokens=500)
            )

            job = dict(job)
            job["interview_friction"] = float(result["interview_friction"])
            job["stability_score"] = float(result["stability_score"])
            job["location_fit_score"] = float(result["location_fit_score"])
            job["salary_range"] = {
                "floor": float(result["salary_floor"]),
                "ceiling": float(result["salary_ceiling"]),
            }
            job["salary_is_estimated"] = bool(result["salary_is_estimated"])

            db.update_ratings(
                job_hash=job["job_hash"],
                stability=job["stability_score"],
                friction=job["interview_friction"],
                location_fit=job["location_fit_score"],
                salary_floor=int(result["salary_floor"]),
                salary_ceiling=int(result["salary_ceiling"]),
                salary_is_estimated=bool(result["salary_is_estimated"]),
            )
            scored.append(job)
        except Exception as exc:  # noqa: BLE001 - one bad job shouldn't kill the batch
            logs.append(f"analysis failed for {job.get('company')} / {job.get('title')}: {exc}")

    logs.append(f"analyzed {len(scored)} of {len(state.get('discovered_jobs', []))} discovered jobs")
    return {**state, "discovered_jobs": scored, "execution_logs": logs}
