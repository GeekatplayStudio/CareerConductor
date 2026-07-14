"""Run Pipeline page: triggers one full scrape -> analyze -> select -> generate pass."""
from __future__ import annotations

import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[3]))

import streamlit as st

from careerconductor.agents.orchestrator import build_graph
from careerconductor.config.settings import settings
from careerconductor.config.store import load_whitelist
from careerconductor.ui.common import get_db, render_sidebar_status
from careerconductor.ui.theme import agent_network, apply_theme, hero

st.set_page_config(page_title="Run Pipeline — CareerConductor", layout="wide")
apply_theme()
render_sidebar_status()
hero("Run Pipeline", "scrape → prefilter → analyze → select → generate → referrals")

db = get_db()
targets = load_whitelist()

if not settings.anthropic_api_key:
    st.error("ANTHROPIC_API_KEY is not set. Add it to `.env` and restart the app.")
elif not targets:
    st.warning("No whitelist targets configured. Go to Configuration to add at least one.")
else:
    st.write(f"Ready to scrape **{len(targets)}** whitelisted target(s).")
    if not settings.gemini_api_key:
        st.caption("GEMINI_API_KEY not set — the cheap pre-filter step will be skipped (fine, just costs a bit more).")

    resume_path = Path(settings.master_resume_path)
    project_db_path = Path(settings.project_database_path)
    files_exist = resume_path.exists() and project_db_path.exists()

    if not files_exist:
        if not resume_path.exists():
            st.error("Master resume is missing. Please go to the **Upload** page to upload one.")
        if not project_db_path.exists():
            st.error("Project database is missing. Please go to the **Upload** page to upload one.")
        st.button("Run full pipeline now", type="primary", disabled=True)
        run_clicked = False
    else:
        run_clicked = st.button("Run full pipeline now", type="primary")

    # The same network visual as the dashboard, but "hot" while agents work:
    # faster rotation, dense signal pulses — a live status display, not decoration.
    agent_network(
        height=220,
        active=run_clicked,
        label="agent network · working" if run_clicked else "agent network · standing by",
    )

    if run_clicked:
        resume_text = resume_path.read_text(encoding="utf-8")
        project_database = json.loads(project_db_path.read_text(encoding="utf-8")).get("projects", [])

        initial_state = {
            "master_resume_raw": resume_text,
            "project_database": project_database,
            "discovered_jobs": [],
            "selected_jobs": [],
            "execution_logs": [],
        }

        with st.status("Running CareerConductor pipeline...", expanded=True) as status:
            graph = build_graph(db)
            final_state = graph.invoke(initial_state)
            for line in final_state.get("execution_logs", []):
                st.write(line)
            status.update(label="Pipeline run complete", state="complete")

        st.success(
            f"Discovered {len(final_state.get('discovered_jobs', []))} jobs, "
            f"selected {len(final_state.get('selected_jobs', []))} for artifact generation."
        )
        st.page_link("pages/4_Report.py", label="View results on the Report page →")
