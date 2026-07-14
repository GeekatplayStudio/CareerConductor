"""Artifact generation agent: produces a tailored resume + cover letter per selected job."""
from __future__ import annotations

import re
from pathlib import Path

import anthropic

from careerconductor.config.settings import settings
from careerconductor.db.repository import CareerConductorDB

from .state import CareerEngineState

_RESUME_PROMPT = """You are tailoring a resume for a specific job application. Use ONLY the
experience, projects, and skills present in the master resume and project database below —
do not invent accomplishments. Extract target keywords from the job description, surface and
prioritize the most relevant past accomplishments, and deprioritize irrelevant technical
components. Output clean, parsed Markdown with no aesthetic clutter (no tables of icons, no
emoji, no horizontal rules beyond simple section breaks).

MASTER RESUME:
{master_resume}

PROJECT DATABASE (JSON):
{project_database}

TARGET JOB — {company} / {title}:
{raw_text}

Output only the tailored resume in Markdown."""

_COVER_LETTER_PROMPT = """Write a professional, punchy cover letter (under 350 words) for this
job application. Focus entirely on system architectural wins, operational business impact, and
technical community leadership drawn from the accomplishments below. No generic filler, no
"I am excited to apply" boilerplate opening.

CANDIDATE BACKGROUND:
{master_resume}

PROJECT DATABASE (JSON):
{project_database}

TARGET JOB — {company} / {title}:
{raw_text}

Output only the cover letter in Markdown."""


def _slugify(text: str) -> str:
    return re.sub(r"[^a-z0-9]+", "-", text.lower()).strip("-")


def run_artifact_generation(state: CareerEngineState, db: CareerConductorDB) -> CareerEngineState:
    logs = list(state.get("execution_logs", []))
    client = anthropic.Anthropic(api_key=settings.anthropic_api_key)

    output_dir = Path(settings.artifact_output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)

    master_resume = state.get("master_resume_raw", "")
    project_database = state.get("project_database", [])

    for job in state.get("selected_jobs", []):
        company_slug = _slugify(job.get("company", "unknown"))
        title_slug = _slugify(job.get("title", "role"))
        base_name = f"{company_slug}__{title_slug}__{job.get('job_hash', '')[:8]}"

        prompt_kwargs = dict(
            master_resume=master_resume,
            project_database=project_database,
            company=job.get("company", ""),
            title=job.get("title", ""),
            raw_text=(job.get("raw_text") or "")[:6000],
        )

        try:
            resume_response = client.messages.create(
                model=settings.anthropic_model,
                max_tokens=2000,
                messages=[{"role": "user", "content": _RESUME_PROMPT.format(**prompt_kwargs)}],
            )
            cover_letter_response = client.messages.create(
                model=settings.anthropic_model,
                max_tokens=800,
                messages=[{"role": "user", "content": _COVER_LETTER_PROMPT.format(**prompt_kwargs)}],
            )

            resume_path = output_dir / f"{base_name}__resume.md"
            cover_letter_path = output_dir / f"{base_name}__cover_letter.md"
            resume_path.write_text(resume_response.content[0].text)
            cover_letter_path.write_text(cover_letter_response.content[0].text)

            db.set_generated_artifacts(
                job_hash=job["job_hash"],
                resume_path=str(resume_path),
                cover_letter_path=str(cover_letter_path),
            )
            logs.append(f"generated artifacts for {job.get('company')} / {job.get('title')}")
        except Exception as exc:  # noqa: BLE001
            logs.append(f"artifact generation failed for {job.get('company')} / {job.get('title')}: {exc}")

    return {**state, "execution_logs": logs}
