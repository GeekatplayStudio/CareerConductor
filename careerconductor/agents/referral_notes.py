"""Referral tracking (manual-lookup replacement for automated LinkedIn scraping).

Automating extraction of LinkedIn connections violates LinkedIn's ToS. Instead this
node just records which selected-job companies are worth checking for warm intros
so you can look them up yourself in the LinkedIn UI.
"""
from __future__ import annotations

from .state import CareerEngineState


def run_referral_notes(state: CareerEngineState) -> CareerEngineState:
    logs = list(state.get("execution_logs", []))
    companies = sorted({job.get("company", "") for job in state.get("selected_jobs", [])})
    if companies:
        logs.append(
            "Referral check needed (manual, LinkedIn UI): " + ", ".join(companies)
        )
    return {**state, "execution_logs": logs}
