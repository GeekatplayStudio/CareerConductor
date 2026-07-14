"""Process-level settings: env-derived keys, file paths, model choices.

SCOPE NOTE (why this module is small): anything a user edits at runtime lives in
config/store.py (whitelist, thresholds, personal criteria) and is loaded fresh
on every pipeline run. This module holds only values that are fixed for the
lifetime of the process — environment variables read once at import, and paths
derived from the repo layout. Keeping the two kinds of config separate means
"edit in the UI, applies next run" is true for everything in store.py, and
"restart to change" is true for everything here.
"""
from __future__ import annotations

import os
from dataclasses import dataclass
from pathlib import Path

from dotenv import load_dotenv

load_dotenv()

PROJECT_ROOT = Path(__file__).resolve().parents[2]


@dataclass
class Settings:
    db_path: str = os.environ.get("CAREERCONDUCTOR_DB_PATH", str(PROJECT_ROOT / "careerconductor.db"))
    anthropic_api_key: str = os.environ.get("ANTHROPIC_API_KEY", "")
    anthropic_model: str = "claude-sonnet-5"
    gemini_api_key: str = os.environ.get("GEMINI_API_KEY", "")
    gemini_model: str = "gemini-2.5-flash"
    # Optional: included in the scraper's User-Agent so board operators can
    # reach you about your traffic — a politeness convention for well-behaved bots.
    contact_email: str = os.environ.get("CONTACT_EMAIL", "")
    master_resume_path: str = str(PROJECT_ROOT / "careerconductor" / "config" / "master_resume.md")
    project_database_path: str = str(PROJECT_ROOT / "careerconductor" / "config" / "project_database.json")
    artifact_output_dir: str = str(PROJECT_ROOT / "careerconductor" / "artifacts" / "output")
    min_request_delay_seconds: float = 2.0  # politeness floor between API calls to any one host


settings = Settings()
