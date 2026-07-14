"""Selection node: filters scored jobs down to the shortlist worth generating artifacts for."""
from __future__ import annotations

from .state import CareerEngineState

MAX_FRICTION = 6.0
MIN_STABILITY = 5.0
MIN_LOCATION_FIT = 5.0


def run_selection(state: CareerEngineState) -> CareerEngineState:
    logs = list(state.get("execution_logs", []))
    selected = [
        job for job in state.get("discovered_jobs", [])
        if job.get("interview_friction", 10) <= MAX_FRICTION
        and job.get("stability_score", 0) >= MIN_STABILITY
        and job.get("location_fit_score", 0) >= MIN_LOCATION_FIT
    ]
    logs.append(f"selected {len(selected)} of {len(state.get('discovered_jobs', []))} scored jobs")
    return {**state, "selected_jobs": selected, "execution_logs": logs}
