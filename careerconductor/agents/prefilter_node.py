"""Cheap relevance pre-filter: a fast, inexpensive model (Gemini free tier) screens
postings BEFORE the expensive scoring model (Claude) sees them.

WHY A TWO-MODEL CASCADE: screening only needs company/title/location — a cheap
model handles that reliably — while real scoring needs the full posting text and
careful judgment. Dropping obvious misfits early cuts the expensive stage's
input by whatever fraction of postings are clearly irrelevant (often most).

DESIGN RULES THIS NODE FOLLOWS:
- Batched: one API call per BATCH_SIZE postings, not one per posting, keeping a
  hundreds-of-jobs run at a handful of requests (far under free-tier limits).
- Fail-open: on ANY failure (API down, unusable response) the affected jobs are
  KEPT. A screening stage must never be the reason a good job disappears; the
  worst case of failing open is just a slightly larger Claude bill.
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
            # Tolerant parse: models sometimes return "index" as a string or emit
            # a malformed element. Coerce per element and skip bad ones — a job
            # with no usable verdict fails open below rather than erroring out.
            verdicts: dict[int, bool] = {}
            for v in _extract_json_array(response.text):
                try:
                    verdicts[int(v["index"])] = bool(v.get("relevant", True))
                except (KeyError, TypeError, ValueError):
                    continue
            if not verdicts:
                logs.append(f"prefilter batch at {start}: no usable verdicts; keeping batch")
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
