"""Global state schema shared across LangGraph nodes."""
from __future__ import annotations

from typing import Dict, List, TypedDict


class JobOpportunity(TypedDict, total=False):
    job_id: str
    job_hash: str
    title: str
    company: str
    location: str
    source_url: str
    raw_text: str
    salary_range: Dict[str, float]
    salary_is_estimated: bool
    # Analysis-agent scores, all 0-10. total=False because jobs flow through the
    # graph partially filled: scraping sets identity fields, analysis adds these.
    match_score: float          # fit vs. the candidate's personal criteria
    stability_score: float
    interview_friction: float   # 10 = worst (heavy live coding)
    location_fit_score: float
    salary_score: float         # comp vs. the candidate's minimum expectation
    perks: str
    notes: str


class CareerEngineState(TypedDict, total=False):
    whitelist_urls: List[str]
    master_resume_raw: str
    project_database: List[Dict]
    historical_applications: List[str]
    discovered_jobs: List[JobOpportunity]
    selected_jobs: List[JobOpportunity]
    execution_logs: List[str]
