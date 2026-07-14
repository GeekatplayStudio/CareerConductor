"""Read/write helpers for the editable JSON config files (whitelist, thresholds,
personal criteria).

WHY THIS MODULE EXISTS (design note for readers):
Configuration that a user edits at runtime (through the Streamlit UI) must live
outside Python code, otherwise every change needs a code edit and process restart.
We keep each concern in its own small JSON file next to this module:

  whitelist.json   -> which company job boards to scrape
  thresholds.json  -> numeric gates + per-run artifact cap
  criteria.json    -> the candidate's personal matching criteria (fed into prompts)

Pipeline nodes call the load_* functions at *run time* (not import time), so a
change saved in the UI takes effect on the very next pipeline run without a
restart. Dataclasses give each file a typed schema; loading with `Thresholds(**data)`
means a newly added field with a default stays backward compatible with JSON
files written by an older version — the default simply fills the gap.
"""
from __future__ import annotations

import json
from dataclasses import asdict, dataclass
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[2]
WHITELIST_PATH = PROJECT_ROOT / "careerconductor" / "config" / "whitelist.json"
THRESHOLDS_PATH = PROJECT_ROOT / "careerconductor" / "config" / "thresholds.json"
CRITERIA_PATH = PROJECT_ROOT / "careerconductor" / "config" / "criteria.json"


@dataclass
class ScrapeTarget:
    company_name: str
    board_type: str  # "greenhouse" | "lever"
    board_token: str  # the slug in the board URL, e.g. boards.greenhouse.io/<token>


@dataclass
class Thresholds:
    # A scored job must pass ALL gates to be eligible for artifact generation.
    max_friction: float = 6.0
    min_stability: float = 5.0
    min_location_fit: float = 5.0
    # Cost control: even if 40 jobs pass the gates, only the best-ranked N get
    # resume/cover-letter generation (each artifact costs two Claude calls).
    max_artifacts_per_run: int = 10


@dataclass
class PersonalCriteria:
    """The candidate's own matching criteria, editable in the UI.

    These are injected verbatim into the AI prompts (prefilter + analysis), so
    plain human language works best — the model reads them like a hiring brief.
    """
    target_roles: str = (
        "Senior, Staff, or Principal software engineering roles; architecture; "
        "engineering leadership"
    )
    locations: str = (
        "Salt Lake City, Draper, South Jordan, Lehi, American Fork, Sandy, Provo, "
        "Orem (Utah Salt Lake Valley), or fully remote"
    )
    min_salary: int = 120000
    interview_preferences: str = (
        "Prefers system design / architecture / portfolio interviews; wants to avoid "
        "LeetCode-style live coding and timed HackerRank assessments"
    )
    about: str = ""        # free text: background, strengths, what energizes you
    dealbreakers: str = ""  # free text: anything that should tank the match score


def criteria_prompt_block(c: PersonalCriteria) -> str:
    """Render the criteria as a labelled block for LLM prompts.

    One formatting function shared by every node keeps the prompts consistent —
    if we add a criteria field, every agent picks it up here, in one place.
    """
    lines = [
        f"- Target roles: {c.target_roles}",
        f"- Acceptable locations: {c.locations}",
        f"- Minimum acceptable salary: ${c.min_salary:,} USD/year",
        f"- Interview preferences: {c.interview_preferences}",
    ]
    if c.about.strip():
        lines.append(f"- About the candidate: {c.about.strip()}")
    if c.dealbreakers.strip():
        lines.append(f"- Dealbreakers: {c.dealbreakers.strip()}")
    return "\n".join(lines)


def load_whitelist() -> list[ScrapeTarget]:
    if not WHITELIST_PATH.exists():
        return []
    data = json.loads(WHITELIST_PATH.read_text(encoding="utf-8"))
    return [ScrapeTarget(**t) for t in data.get("targets", [])]


def save_whitelist(targets: list[ScrapeTarget]) -> None:
    WHITELIST_PATH.write_text(json.dumps({"targets": [asdict(t) for t in targets]}, indent=2), encoding="utf-8")


def add_whitelist_target(target: ScrapeTarget) -> bool:
    """Append a target unless an equivalent one already exists. Returns True if added."""
    targets = load_whitelist()
    for t in targets:
        if t.board_type == target.board_type and t.board_token == target.board_token:
            return False  # already tracked — keep the whitelist duplicate-free
    targets.append(target)
    save_whitelist(targets)
    return True


def load_thresholds() -> Thresholds:
    if not THRESHOLDS_PATH.exists():
        return Thresholds()
    return Thresholds(**json.loads(THRESHOLDS_PATH.read_text(encoding="utf-8")))


def save_thresholds(thresholds: Thresholds) -> None:
    THRESHOLDS_PATH.write_text(json.dumps(asdict(thresholds), indent=2), encoding="utf-8")


def load_criteria() -> PersonalCriteria:
    if not CRITERIA_PATH.exists():
        return PersonalCriteria()
    return PersonalCriteria(**json.loads(CRITERIA_PATH.read_text(encoding="utf-8")))


def save_criteria(criteria: PersonalCriteria) -> None:
    CRITERIA_PATH.write_text(json.dumps(asdict(criteria), indent=2), encoding="utf-8")
