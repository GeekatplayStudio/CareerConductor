"""CareerConductor control panel — entry page. Run with: streamlit run careerconductor/ui/app.py"""
from __future__ import annotations

import sys
from pathlib import Path

# Allow `streamlit run careerconductor/ui/app.py` to resolve the careerconductor package
sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

import streamlit as st

from careerconductor.config.settings import settings
from careerconductor.config.store import CRITERIA_PATH, load_thresholds, load_whitelist
from careerconductor.ui.common import get_db, render_sidebar_status
from careerconductor.ui.theme import agent_network, apply_theme, hero, status_line

st.set_page_config(page_title="CareerConductor", layout="wide")
apply_theme()
render_sidebar_status()

hero("CareerConductor", "Multi-agent job scouting & tailoring engine — local control panel")
agent_network(height=230, active=False, label="agent network · idle")

db = get_db()
counts = db.status_counts()

col1, col2, col3, col4 = st.columns(4)
col1.metric("Discovered", counts.get("discovered", 0))
col2.metric("Analyzed", counts.get("analyzed", 0))
col3.metric("Artifacts generated", counts.get("generated", 0))
col4.metric("Applied", counts.get("applied", 0))

st.divider()

left, right = st.columns(2)
with left:
    st.subheader("Setup checklist")
    status_line(bool(settings.anthropic_api_key),
                "Anthropic API key" if settings.anthropic_api_key else "Anthropic API key — set in .env")
    status_line(bool(settings.gemini_api_key),
                "Gemini API key" if settings.gemini_api_key else "Gemini API key — optional pre-filter, set in .env")
    resume_text = Path(settings.master_resume_path).read_text() if Path(settings.master_resume_path).exists() else ""
    resume_ok = len(resume_text) > 300
    status_line(resume_ok,
                "Master resume uploaded" if resume_ok else "Master resume looks empty — go to Upload",
                warn=not resume_ok)
    targets = load_whitelist()
    status_line(bool(targets), f"Whitelist targets configured: {len(targets)}", warn=not targets)
    criteria_ok = CRITERIA_PATH.exists()
    status_line(criteria_ok,
                "Personal criteria saved" if criteria_ok
                else "Personal criteria not saved — defaults in use (Configuration page)",
                warn=not criteria_ok)

with right:
    st.subheader("Current thresholds")
    t = load_thresholds()
    st.write(f"Max interview friction: **{t.max_friction}**")
    st.write(f"Min company stability: **{t.min_stability}**")
    st.write(f"Min location fit: **{t.min_location_fit}**")
    st.write(f"Max artifacts per run: **{t.max_artifacts_per_run}**")
    st.caption("Adjust these on the Configuration page.")

st.divider()
st.info(
    "Use the sidebar to navigate: **Upload**, **Configuration**, **Run Pipeline**, "
    "**Report**, **Templates**."
)
