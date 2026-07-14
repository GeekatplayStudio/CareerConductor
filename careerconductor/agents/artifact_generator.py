"""Artifact generation agent: produces a tailored resume + cover letter per selected job.

The master resume + project database are identical across every job in a run, so they're
sent as a cached system block (Anthropic prompt caching) — only the first call pays full
input price for that content; every subsequent resume/cover-letter call in the same run
reads it from cache at a fraction of the cost.
"""
from __future__ import annotations

import json
import re
from pathlib import Path

import anthropic

from careerconductor.config.settings import settings
from careerconductor.db.repository import CareerConductorDB
from careerconductor.templates.resume_templates import load_selected_template

from .llm import cached_system_block, claude_call
from .state import CareerEngineState

_CANDIDATE_CONTEXT_TEMPLATE = """MASTER RESUME:
{master_resume}

PROJECT DATABASE (JSON):
{project_database}"""

# {template_style} is filled at run time from the user's Templates-page choice,
# so the same tailoring rules apply regardless of visual style — the template
# only controls structure/tone, never permits inventing content.
_RESUME_INSTRUCTIONS_TEMPLATE = """You are tailoring a resume for a specific job application. Use ONLY the
experience, projects, and skills present in the master resume and project database above — do not
invent accomplishments. Extract target keywords from the job description, surface and prioritize
the most relevant past accomplishments, and deprioritize irrelevant technical components. Output
clean, parsed Markdown with no aesthetic clutter (no tables of icons, no emoji, no horizontal
rules beyond simple section breaks).

TEMPLATE STYLE — "{template_name}": {template_style}"""

_COVER_LETTER_INSTRUCTIONS = """Write a professional, punchy cover letter (under 350 words) for
this job application, using only the background above. Focus entirely on system architectural
wins, operational business impact, and technical community leadership. No generic filler, no
"I am excited to apply" boilerplate opening."""

_JOB_TEMPLATE = """{instructions}

TARGET JOB — {company} / {title}:
{raw_text}

Output only the {artifact_kind} in Markdown."""


def _slugify(text: str) -> str:
    return re.sub(r"[^a-z0-9]+", "-", text.lower()).strip("-")


def _generate(client: anthropic.Anthropic, cached_context: str, instructions: str,
              artifact_kind: str, job: dict, max_tokens: int) -> str:
    return claude_call(
        client,
        system=cached_system_block(cached_context),
        user_content=_JOB_TEMPLATE.format(
            instructions=instructions,
            company=job.get("company", ""),
            title=job.get("title", ""),
            raw_text=(job.get("raw_text") or "")[:6000],
            artifact_kind=artifact_kind,
        ),
        max_tokens=max_tokens,
    )


def run_artifact_generation(state: CareerEngineState, db: CareerConductorDB) -> CareerEngineState:
    logs = list(state.get("execution_logs", []))
    client = anthropic.Anthropic(api_key=settings.anthropic_api_key)

    output_dir = Path(settings.artifact_output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)

    cached_context = _CANDIDATE_CONTEXT_TEMPLATE.format(
        master_resume=state.get("master_resume_raw", ""),
        project_database=json.dumps(state.get("project_database", [])),
    )

    # Loaded at run time so a template picked in the UI applies to the next run.
    template = load_selected_template()
    resume_instructions = _RESUME_INSTRUCTIONS_TEMPLATE.format(
        template_name=template.name, template_style=template.style_instructions,
    )
    logs.append(f"resume template: {template.name} ({template.category})")

    for job in state.get("selected_jobs", []):
        company_slug = _slugify(job.get("company", "unknown"))
        title_slug = _slugify(job.get("title", "role"))
        base_name = f"{company_slug}__{title_slug}__{job.get('job_hash', '')[:8]}"

        try:
            resume_text = _generate(
                client, cached_context, resume_instructions, "tailored resume", job, max_tokens=2000
            )
            cover_letter_text = _generate(
                client, cached_context, _COVER_LETTER_INSTRUCTIONS, "cover letter", job, max_tokens=800
            )

            resume_path = output_dir / f"{base_name}__resume.md"
            cover_letter_path = output_dir / f"{base_name}__cover_letter.md"
            resume_path.write_text(resume_text, encoding="utf-8")
            cover_letter_path.write_text(cover_letter_text, encoding="utf-8")

            db.set_generated_artifacts(
                job_hash=job["job_hash"],
                resume_path=str(resume_path),
                cover_letter_path=str(cover_letter_path),
            )
            logs.append(f"generated artifacts for {job.get('company')} / {job.get('title')}")
        except Exception as exc:  # noqa: BLE001
            logs.append(f"artifact generation failed for {job.get('company')} / {job.get('title')}: {exc}")

    return {**state, "execution_logs": logs}
