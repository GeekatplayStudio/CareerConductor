"""Cheap relevance pre-filter using the Gemini API (free tier) before spending Claude
tokens on full analysis. This is the "lightweight local execution" layer from the PRD's
backup execution engine — obviously-irrelevant postings (wrong seniority, wrong
location, wrong discipline) get dropped here instead of scored in full.
"""
from __future__ import annotations

import json
import re

from google import genai

from careerconductor.config.settings import settings

from .state import CareerEngineState, JobOpportunity

_PREFILTER_PROMPT = """Quick relevance check only — not a full evaluation. Answer whether this
posting is even worth a detailed look for a senior/staff-level software engineer targeting
Utah's Salt Lake Valley (Salt Lake City, Draper, South Jordan, Lehi, American Fork, Sandy,
Provo, Orem) or fully remote roles.

Reject only if CLEARLY wrong fit: junior/entry-level titles, unrelated discipline (e.g. sales,
retail), or a rigid on-site requirement far outside Utah with no remote option. When in doubt, keep it.

Company: {company}
Title: {title}
Location: {location}

Respond with ONLY JSON: {{"relevant": true|false, "reason": "<one short phrase>"}}"""


def _extract_json(text: str) -> dict:
    match = re.search(r"\{.*\}", text, re.DOTALL)
    if not match:
        raise ValueError(f"no JSON object found in model response: {text!r}")
    return json.loads(match.group(0))


def run_prefilter(state: CareerEngineState) -> CareerEngineState:
    logs = list(state.get("execution_logs", []))
    jobs = state.get("discovered_jobs", [])

    if not settings.gemini_api_key:
        logs.append("prefilter skipped: GEMINI_API_KEY not set")
        return {**state, "execution_logs": logs}

    client = genai.Client(api_key=settings.gemini_api_key)
    kept: list[JobOpportunity] = []
    dropped = 0

    for job in jobs:
        prompt = _PREFILTER_PROMPT.format(
            company=job.get("company", ""),
            title=job.get("title", ""),
            location=job.get("location", ""),
        )
        try:
            response = client.models.generate_content(
                model=settings.gemini_model,
                contents=prompt,
            )
            result = _extract_json(response.text)
            if result.get("relevant", True):
                kept.append(job)
            else:
                dropped += 1
        except Exception as exc:  # noqa: BLE001 - fail open, let full analysis decide
            logs.append(f"prefilter failed for {job.get('company')} / {job.get('title')}: {exc}")
            kept.append(job)

    logs.append(f"prefilter: kept {len(kept)}, dropped {dropped} of {len(jobs)} discovered jobs")
    return {**state, "discovered_jobs": kept, "execution_logs": logs}
