"""Selection node: filters scored jobs down to the shortlist worth generating artifacts for."""
from __future__ import annotations

from careerconductor.config.store import load_thresholds

from .state import CareerEngineState


def composite_score(job: dict) -> float:
    """Ranking score used to pick which eligible jobs get artifacts first.

    Keep this in sync with the ORDER BY in repository.top_candidates() — the UI's
    "Top candidates" ranking and the pipeline's artifact ordering must agree, or
    the report would show a different top-10 than the one that got resumes.
    """
    return (
        job.get("match_score", 0)
        + job.get("stability_score", 0)
        - job.get("interview_friction", 10)
        + job.get("location_fit_score", 0)
        + job.get("salary_score", 0)
    )


def run_selection(state: CareerEngineState) -> CareerEngineState:
    logs = list(state.get("execution_logs", []))
    thresholds = load_thresholds()
    eligible = [
        job for job in state.get("discovered_jobs", [])
        if job.get("interview_friction", 10) <= thresholds.max_friction
        and job.get("stability_score", 0) >= thresholds.min_stability
        and job.get("location_fit_score", 0) >= thresholds.min_location_fit
    ]
    eligible.sort(key=composite_score, reverse=True)
    selected = eligible[:thresholds.max_artifacts_per_run]
    logs.append(
        f"selected {len(selected)} of {len(state.get('discovered_jobs', []))} scored jobs"
        + (f" (capped from {len(eligible)} eligible; best-ranked kept)"
           if len(eligible) > len(selected) else "")
    )
    return {**state, "selected_jobs": selected, "execution_logs": logs}
