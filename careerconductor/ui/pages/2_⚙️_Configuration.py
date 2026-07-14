"""Configuration page: whitelist scrape targets + selection thresholds."""
from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[3]))

import streamlit as st

from careerconductor.config.settings import settings
from careerconductor.config.store import (
    ScrapeTarget,
    Thresholds,
    load_thresholds,
    load_whitelist,
    save_thresholds,
    save_whitelist,
)
from careerconductor.ui.common import render_sidebar_status

st.set_page_config(page_title="Configuration — CareerConductor", page_icon="⚙️", layout="wide")
render_sidebar_status()
st.title("⚙️ Configuration")

st.subheader("API keys")
st.caption("Set in `.env` at the project root — the UI doesn't store keys.")
col1, col2 = st.columns(2)
col1.write(f"`ANTHROPIC_API_KEY`: {'✅ set' if settings.anthropic_api_key else '❌ not set'}")
col2.write(f"`GEMINI_API_KEY`: {'✅ set' if settings.gemini_api_key else '❌ not set (pre-filter will be skipped)'}")

st.divider()

st.subheader("Whitelist targets")
st.caption(
    "Companies to scrape via their official Greenhouse/Lever public job-board API. "
    "Find the token from the careers page URL, e.g. boards.greenhouse.io/**token** "
    "or jobs.lever.co/**token**."
)

targets = load_whitelist()

if "target_rows" not in st.session_state:
    st.session_state.target_rows = [
        {"company_name": t.company_name, "board_type": t.board_type, "board_token": t.board_token}
        for t in targets
    ]

edited = st.data_editor(
    st.session_state.target_rows,
    num_rows="dynamic",
    use_container_width=True,
    column_config={
        "company_name": st.column_config.TextColumn("Company"),
        "board_type": st.column_config.SelectboxColumn("Board type", options=["greenhouse", "lever"]),
        "board_token": st.column_config.TextColumn("Board token"),
    },
    key="whitelist_editor",
)

if st.button("Save whitelist", type="primary"):
    clean_rows = [
        r for r in edited
        if r.get("company_name") and r.get("board_type") and r.get("board_token")
    ]
    save_whitelist([ScrapeTarget(**r) for r in clean_rows])
    st.session_state.target_rows = clean_rows
    st.success(f"Saved {len(clean_rows)} whitelist target(s).")

st.divider()

st.subheader("Selection thresholds")
st.caption("A scored job must satisfy all three to reach artifact generation.")
current = load_thresholds()

max_friction = st.slider(
    "Max interview friction (higher = more live-coding tolerance)",
    min_value=0.0, max_value=10.0, value=current.max_friction, step=0.5,
)
min_stability = st.slider(
    "Min company stability", min_value=0.0, max_value=10.0, value=current.min_stability, step=0.5,
)
min_location_fit = st.slider(
    "Min location fit", min_value=0.0, max_value=10.0, value=current.min_location_fit, step=0.5,
)

if st.button("Save thresholds", type="primary"):
    save_thresholds(Thresholds(
        max_friction=max_friction, min_stability=min_stability, min_location_fit=min_location_fit,
    ))
    st.success("Thresholds saved.")

st.divider()
st.subheader("Location priority terms")
st.caption("Reference only — used in agent prompts as the target-geography description.")
st.write(", ".join(settings.location_priority_terms))
