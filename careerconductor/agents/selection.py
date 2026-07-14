"""Selection node: filters scored jobs down to the shortlist worth generating artifacts for."""
from __future__ import annotations

from careerconductor.config.store import load_thresholds

from .state import CareerEngineState


def run_selection(state: CareerEngineState) -> CareerEngineState:
    logs = list(state.get("execution_logs", []))
    thresholds = load_thresholds()
    selected = [
        job for job in state.get("discovered_jobs", [])
        if job.get("interview_friction", 10) <= thresholds.max_friction
        and job.get("stability_score", 0) >= thresholds.min_stability
        and job.get("location_fit_score", 0) >= thresholds.min_location_fit
    ]
    logs.append(f"selected {len(selected)} of {len(state.get('discovered_jobs', []))} scored jobs")
    return {**state, "selected_jobs": selected, "execution_logs": logs}
