"""CLI entrypoint: run one full CareerConductor pass."""
from __future__ import annotations

import json
from pathlib import Path

from careerconductor.agents.orchestrator import build_graph
from careerconductor.config.settings import settings
from careerconductor.config.store import load_whitelist
from careerconductor.db.repository import CareerConductorDB


def load_initial_state() -> dict:
    master_resume_raw = Path(settings.master_resume_path).read_text(encoding="utf-8")
    project_database = json.loads(Path(settings.project_database_path).read_text(encoding="utf-8")).get("projects", [])
    return {
        "master_resume_raw": master_resume_raw,
        "project_database": project_database,
        "discovered_jobs": [],
        "selected_jobs": [],
        "execution_logs": [],
    }


def main() -> None:
    if not settings.anthropic_api_key:
        raise SystemExit("ANTHROPIC_API_KEY is not set. Copy .env.example to .env and fill it in.")
    if not load_whitelist():
        print("No whitelist targets configured (careerconductor/config/whitelist.json) — nothing to scrape.")

    resume_path = Path(settings.master_resume_path)
    project_db_path = Path(settings.project_database_path)
    if not resume_path.exists():
        raise SystemExit(f"Error: Master resume file not found at {settings.master_resume_path}. Please upload it first.")
    if not project_db_path.exists():
        raise SystemExit(f"Error: Project database file not found at {settings.project_database_path}. Please upload it first.")

    db = CareerConductorDB(db_path=settings.db_path)
    graph = build_graph(db)

    final_state = graph.invoke(load_initial_state())

    print("\n--- execution log ---")
    for line in final_state.get("execution_logs", []):
        print(line)

    top = db.top_candidates(limit=10)
    if top:
        print("\n--- top candidates ---")
        for row in top:
            print(f"{row['company_name']} / {row['job_title']} "
                  f"(stability={row['stability_rating']}, friction={row['friction_rating']}, "
                  f"location_fit={row['location_fit_rating']})")


if __name__ == "__main__":
    main()
