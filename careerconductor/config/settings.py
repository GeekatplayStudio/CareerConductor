"""Runtime configuration: whitelist targets, local file paths, model settings."""
from __future__ import annotations

import os
from dataclasses import dataclass, field
from pathlib import Path

from dotenv import load_dotenv

from careerconductor.config.store import ScrapeTarget, load_whitelist

load_dotenv()

PROJECT_ROOT = Path(__file__).resolve().parents[2]


@dataclass
class Settings:
    db_path: str = os.environ.get("CAREERCONDUCTOR_DB_PATH", str(PROJECT_ROOT / "careerconductor.db"))
    anthropic_api_key: str = os.environ.get("ANTHROPIC_API_KEY", "")
    anthropic_model: str = "claude-sonnet-5"
    gemini_api_key: str = os.environ.get("GEMINI_API_KEY", "")
    gemini_model: str = "gemini-2.5-flash"
    master_resume_path: str = str(PROJECT_ROOT / "careerconductor" / "config" / "master_resume.md")
    project_database_path: str = str(PROJECT_ROOT / "careerconductor" / "config" / "project_database.json")
    artifact_output_dir: str = str(PROJECT_ROOT / "careerconductor" / "artifacts" / "output")
    min_request_delay_seconds: float = 2.0  # politeness floor between API calls to any one host
    location_priority_terms: tuple[str, ...] = (
        "salt lake", "draper", "south jordan", "lehi", "american fork", "sandy",
        "provo", "orem", "remote",
    )
    whitelist_targets: list[ScrapeTarget] = field(default_factory=load_whitelist)


settings = Settings()
