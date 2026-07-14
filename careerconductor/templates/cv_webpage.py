"""CV web page generator: turns the master resume into a single-file HTML page
styled after the user's selected template.

WHY SINGLE-FILE: the output must be trivially portable — attach it to an email,
drop it on any static host (GitHub Pages, Netlify), or open it from disk. That
means every style inline in one <style> block, no external fonts, scripts, or
images. The prompt enforces this contract; _looks_like_html is a cheap guard
against the model returning prose instead of a document.
"""
from __future__ import annotations

import anthropic

from careerconductor.agents.llm import claude_call
from careerconductor.config.settings import settings
from careerconductor.config.store import criteria_prompt_block, load_criteria
from careerconductor.templates.resume_templates import ResumeTemplate

_CV_PAGE_PROMPT = """Build a personal CV web page from this resume.

RESUME (the only source of truth — do not invent employers, dates, links, or skills):
{master_resume}

CANDIDATE CONTEXT (tone/positioning only):
{criteria}

VISUAL DIRECTION — "{template_name}" style: {web_style}

HARD REQUIREMENTS:
- One complete, self-contained HTML5 document: <!DOCTYPE html> through </html>.
- ALL CSS in a single <style> block in <head>. No external resources of any kind
  (no CDN fonts, no scripts, no images) — the file must work offline from disk.
- Semantic structure (header, main, section) with the resume's real content.
- Responsive: readable on a phone (max-width container, relative units).
- Include a print stylesheet (@media print) so the page doubles as a printable CV.
- If the resume lacks something (e.g. no portfolio links), simply omit that
  element — never fabricate placeholders like "yourname@email.com".

Output ONLY the HTML document, nothing before or after it."""


def _looks_like_html(text: str) -> bool:
    lowered = text.strip().lower()
    return lowered.startswith("<!doctype html") or lowered.startswith("<html")


def _strip_code_fence(text: str) -> str:
    """Models sometimes wrap output in ```html fences despite instructions."""
    stripped = text.strip()
    if stripped.startswith("```"):
        stripped = stripped.split("\n", 1)[1] if "\n" in stripped else ""
        if stripped.rstrip().endswith("```"):
            stripped = stripped.rstrip()[:-3]
    return stripped.strip()


def generate_cv_webpage(master_resume: str, template: ResumeTemplate) -> str:
    """Generate the single-file HTML CV. Raises ValueError on non-HTML output."""
    client = anthropic.Anthropic(api_key=settings.anthropic_api_key)
    raw = claude_call(
        client,
        user_content=_CV_PAGE_PROMPT.format(
            master_resume=master_resume[:20000],
            criteria=criteria_prompt_block(load_criteria()),
            template_name=template.name,
            web_style=template.web_style,
        ),
        max_tokens=8000,
    )
    html = _strip_code_fence(raw)
    if not _looks_like_html(html):
        raise ValueError("model did not return an HTML document; try again")
    return html
