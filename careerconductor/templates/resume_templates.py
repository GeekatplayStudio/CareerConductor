"""Resume template registry: ten curated styles across the categories hiring
markets actually use, from ATS-safe to creative.

HOW TEMPLATES WORK HERE (teaching note):
The artifact generator produces Markdown, and the CV web-page generator produces
HTML — both via an LLM. So a "template" is not a fixed layout file; it is a pair
of style contracts injected into the generation prompts:

  style_instructions -> how the tailored Markdown resume should be structured
                        (section order, tone, what to emphasize)
  web_style          -> the visual DNA for the single-file HTML CV page
                        (palette, typography, layout direction)

This keeps templates data, not code: adding an eleventh template is appending
one entry — no new logic anywhere. The UI renders each entry's `accent` and
`preview_font` as a mini visual card so users can compare styles without
spending a single API token.
"""
from __future__ import annotations

import json
from dataclasses import asdict, dataclass
from pathlib import Path

SELECTED_TEMPLATE_PATH = Path(__file__).resolve().parents[1] / "config" / "template.json"

DEFAULT_TEMPLATE_KEY = "ats-classic"


@dataclass(frozen=True)
class ResumeTemplate:
    key: str
    name: str
    category: str
    description: str          # one line shown in the gallery
    accent: str               # hex color driving the mini preview card
    preview_font: str         # font-family hint for the preview card
    style_instructions: str   # injected into the Markdown resume prompt
    web_style: str            # injected into the HTML CV-page prompt


TEMPLATES: tuple[ResumeTemplate, ...] = (
    ResumeTemplate(
        key="ats-classic",
        name="ATS Classic",
        category="ATS-Optimized",
        description="Maximum parser compatibility — the safe default for online applications.",
        accent="#2563eb",
        preview_font="Georgia, serif",
        style_instructions=(
            "Single column, no tables or columns. Section order: Summary, Skills "
            "(comma-separated keywords), Experience (reverse-chronological, 'Title — "
            "Company — Dates' headers, 3-5 bullet achievements each), Education. "
            "Standard section names only. No graphics language, no unusual symbols."
        ),
        web_style=(
            "Clean single-column document look: white background, near-black text, "
            "one blue accent (#2563eb) for headings and links, Georgia/serif headings, "
            "system sans body, generous whitespace, print-friendly."
        ),
    ),
    ResumeTemplate(
        key="corporate-executive",
        name="Corporate Executive",
        category="Corporate",
        description="Gravitas for senior/leadership roles — outcomes, scope, P&L language.",
        accent="#1e293b",
        preview_font="'Times New Roman', serif",
        style_instructions=(
            "Open with a 3-line executive summary of scope (team size, budget, org "
            "impact). Lead every bullet with a business outcome and quantified result "
            "before the how. Include a 'Leadership Highlights' section. Formal tone, "
            "no first person."
        ),
        web_style=(
            "Executive letterhead feel: charcoal (#1e293b) header band with name in "
            "small-caps serif, ivory background, thin gold rule separators, restrained "
            "and dense typography."
        ),
    ),
    ResumeTemplate(
        key="modern-minimalist",
        name="Modern Minimalist",
        category="Modern",
        description="Whitespace-first, short lines, ruthless prioritization of signal.",
        accent="#0f766e",
        preview_font="'Helvetica Neue', sans-serif",
        style_instructions=(
            "Extreme brevity: summary under 25 words, max 3 bullets per role, every "
            "bullet under 15 words. Cut anything older than 10 years to one line. "
            "Skills as a short curated list, not a keyword dump."
        ),
        web_style=(
            "Minimalist: huge whitespace, thin sans-serif (Helvetica-like), single "
            "teal accent (#0f766e) used only for the name and section markers, no "
            "borders, no shadows, asymmetric left margin."
        ),
    ),
    ResumeTemplate(
        key="tech-engineer",
        name="Tech Engineer",
        category="Technical",
        description="For engineering readers — stack up front, systems and scale in every bullet.",
        accent="#7c3aed",
        preview_font="'SF Mono', Menlo, monospace",
        style_instructions=(
            "Lead with a 'Core Stack' section grouping technologies by proficiency. "
            "Every experience bullet names the technology used and the scale achieved "
            "(users, requests/sec, data volume, cost saved). Include a Selected "
            "Projects section with 1-line architecture summaries."
        ),
        web_style=(
            "Developer aesthetic: dark slate background, light text, violet (#7c3aed) "
            "accents, monospace for headings and stack tags rendered as small pills, "
            "code-editor vibe without being gimmicky."
        ),
    ),
    ResumeTemplate(
        key="creative-bold",
        name="Creative Bold",
        category="Creative",
        description="Personality up front — for roles where standing out beats conforming.",
        accent="#ea580c",
        preview_font="'Avenir Next', sans-serif",
        style_instructions=(
            "Open with a distinctive 2-line personal statement with voice (still "
            "professional). Reframe experience bullets as short impact stories: "
            "challenge, then what changed. Include a 'Beyond Work' line if the "
            "master resume offers material."
        ),
        web_style=(
            "Bold editorial: oversized name typography, orange (#ea580c) diagonal "
            "accent block, strong grid, generous pull-quote styling for the personal "
            "statement, sans-serif throughout."
        ),
    ),
    ResumeTemplate(
        key="startup-impact",
        name="Startup Impact",
        category="Startup",
        description="Bias-to-action framing — ownership, speed, zero-to-one wins.",
        accent="#16a34a",
        preview_font="Inter, sans-serif",
        style_instructions=(
            "Emphasize ownership and speed: bullets lead with 'Built', 'Launched', "
            "'Drove'. Quantify time-to-ship and growth numbers. Collapse big-company "
            "process language; highlight scrappy wins, breadth across the stack, and "
            "direct customer impact."
        ),
        web_style=(
            "Product-landing feel: white background, green (#16a34a) CTA-style accent "
            "chips for skills, Inter-like geometric sans, rounded cards per role, "
            "friendly but crisp."
        ),
    ),
    ResumeTemplate(
        key="academic-cv",
        name="Academic CV",
        category="Academic",
        description="Complete and formal — publications, teaching, service, no marketing tone.",
        accent="#9f1239",
        preview_font="'Palatino Linotype', serif",
        style_instructions=(
            "Comprehensive CV structure: Education first, then Research/Professional "
            "Experience, Publications & Talks (if the master resume has any), Teaching "
            "& Mentoring, Service. Neutral descriptive tone, no persuasive language, "
            "complete rather than selective."
        ),
        web_style=(
            "Scholarly: cream background, dark maroon (#9f1239) headings in Palatino-"
            "style serif, hanging-indent lists for publications, understated hairline "
            "rules, no decoration."
        ),
    ),
    ResumeTemplate(
        key="consultant-results",
        name="Consultant Results",
        category="Consulting",
        description="Case-style bullets — situation, action, quantified business result.",
        accent="#0369a1",
        preview_font="Garamond, serif",
        style_instructions=(
            "Structure every bullet as situation -> action -> quantified result "
            "(percentages, dollars, time). Group experience by engagement/problem type "
            "where possible. Include a 'Selected Results' box of the 3 strongest "
            "numbers near the top."
        ),
        web_style=(
            "Consulting-deck polish: white background, steel blue (#0369a1) accent, "
            "a highlighted key-results callout box near the top, Garamond-style serif "
            "headings with clean sans body, confident spacing."
        ),
    ),
    ResumeTemplate(
        key="designer-portfolio",
        name="Designer Portfolio",
        category="Creative",
        description="Visual-craft signaling with portfolio links woven through.",
        accent="#db2777",
        preview_font="Futura, sans-serif",
        style_instructions=(
            "Surface portfolio/work links prominently (from the master resume only — "
            "never invent URLs). Describe work in terms of craft decisions and user "
            "outcomes. Short 'Tools & Craft' section instead of a generic skills dump."
        ),
        web_style=(
            "Portfolio-grade: near-white gallery background, magenta (#db2777) accent, "
            "Futura-style geometric sans, large name lockup, project links styled as "
            "underlined gallery captions, lots of air."
        ),
    ),
    ResumeTemplate(
        key="career-changer",
        name="Career Changer",
        category="Hybrid",
        description="Skills-first hybrid — transferable strengths before chronology.",
        accent="#ca8a04",
        preview_font="'Segoe UI', sans-serif",
        style_instructions=(
            "Hybrid/functional format: open with 3 transferable skill clusters, each "
            "with 2 evidence bullets drawn from any era of experience, THEN a compact "
            "reverse-chronological history. Frame the summary around where the "
            "candidate is going, not where they've been."
        ),
        web_style=(
            "Warm and approachable: soft warm-gray background, amber (#ca8a04) accent, "
            "three skill-cluster cards at the top, humanist sans-serif, rounded "
            "corners, medium density."
        ),
    ),
)

TEMPLATES_BY_KEY = {t.key: t for t in TEMPLATES}


def categories() -> list[str]:
    """Unique categories in declaration order (drives the gallery grouping)."""
    seen: dict[str, None] = {}
    for t in TEMPLATES:
        seen.setdefault(t.category, None)
    return list(seen)


def load_selected_template() -> ResumeTemplate:
    """The persisted user choice, falling back to the ATS-safe default.

    Falls back gracefully if the saved key no longer exists (e.g. a template
    was renamed between versions) — config must never crash the pipeline.
    """
    if SELECTED_TEMPLATE_PATH.exists():
        key = json.loads(SELECTED_TEMPLATE_PATH.read_text()).get("selected", DEFAULT_TEMPLATE_KEY)
        if key in TEMPLATES_BY_KEY:
            return TEMPLATES_BY_KEY[key]
    return TEMPLATES_BY_KEY[DEFAULT_TEMPLATE_KEY]


def save_selected_template(key: str) -> None:
    if key not in TEMPLATES_BY_KEY:
        raise ValueError(f"unknown template key: {key}")
    SELECTED_TEMPLATE_PATH.write_text(json.dumps({"selected": key}, indent=2))
