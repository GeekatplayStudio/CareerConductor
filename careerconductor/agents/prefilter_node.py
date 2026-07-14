"""Cheap relevance pre-filter using the Gemini API (free tier) before spending Claude
tokens on full analysis. This is the "lightweight local execution" layer from the PRD's
backup execution engine — obviously-irrelevant postings (wrong seniority, wrong
location, wrong discipline) get dropped here instead of scored in full.

Jobs are screened in batches (one API call per BATCH_SIZE jobs) to stay far under
free-tier rate limits even when a scrape run discovers hundreds of postings.
"""
from __future__ import annotations

import json
import re

from google import genai

from careerconductor.config.settings import settings
from careerconductor.config.store import criteria_prompt_block, load_criteria

from .state import CareerEngineState, JobOpportunity

BATCH_SIZE = 30

_PREFILTER_PROMPT = """Quick relevance screen only — not a full evaluation. The candidate:

{criteria}

For EACH numbered posting below, decide whether it is even worth a detailed look for this
candidate. Reject only if CLEARLY wrong fit: wrong seniority, unrelated discipline (e.g.
sales, retail), or a rigid on-site requirement incompatible with the candidate's locations.
When in doubt, keep it — a later, more careful stage does the real scoring.

Postings:
{postings}

Respond with ONLY a JSON array, one entry per posting, in input order:
[{{"index": <int>, "relevant": true|false}}, ...]"""


def _extract_json_array(text: str) -> list:
    match = re.search(r"\[.*\]", text, re.DOTALL)
    if not match:
        raise ValueError(f"no JSON array found in model response: {text!r}")
    return json.loads(match.group(0))


def _format_batch(jobs: list[JobOpportunity]) -> str:
    lines = []
    for i, job in enumerate(jobs):
        lines.append(
            f"{i}. Company: {job.get('company', '')} | Title: {job.get('title', '')} "
            f"| Location: {job.get('location', '')}"
        )
    return "\n".join(lines)


def run_prefilter(state: CareerEngineState) -> CareerEngineState:
    logs = list(state.get("execution_logs", []))
    jobs = state.get("discovered_jobs", [])

    if not settings.gemini_api_key:
        logs.append("prefilter skipped: GEMINI_API_KEY not set")
        return {**state, "execution_logs": logs}
    if not jobs:
        return {**state, "execution_logs": logs}

    client = genai.Client(api_key=settings.gemini_api_key)
    kept: list[JobOpportunity] = []
    dropped = 0

    # Loaded at run time so criteria edits saved in the UI apply on the next run.
    criteria_block = criteria_prompt_block(load_criteria())

    for start in range(0, len(jobs), BATCH_SIZE):
        batch = jobs[start:start + BATCH_SIZE]
        try:
            response = client.models.generate_content(
                model=settings.gemini_model,
                contents=_PREFILTER_PROMPT.format(
                    criteria=criteria_block, postings=_format_batch(batch),
                ),
            )
            verdicts = {v["index"]: bool(v.get("relevant", True))
                        for v in _extract_json_array(response.text)}
            for i, job in enumerate(batch):
                if verdicts.get(i, True):  # missing verdict -> fail open
                    kept.append(job)
                else:
                    dropped += 1
        except Exception as exc:  # noqa: BLE001 - fail open, let full analysis decide
            logs.append(f"prefilter batch starting at {start} failed ({exc}); keeping batch")
            kept.extend(batch)

    logs.append(f"prefilter: kept {len(kept)}, dropped {dropped} of {len(jobs)} discovered jobs")
    return {**state, "discovered_jobs": kept, "execution_logs": logs}
