"""Configuration page: personal criteria, whitelist targets (paste-a-URL or manual
grid), and selection thresholds.

Everything on this page persists to small JSON files (see config/store.py), so
it survives restarts — configure once, run forever. Each parameter group lives
in its own glass "sheet" (theme-styled expander with a 3D hover lift).
"""
from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[3]))

import streamlit as st

from careerconductor.config.board_detect import detect_target, verify_target
from careerconductor.config.settings import settings
from careerconductor.config.store import (
    PersonalCriteria,
    ScrapeTarget,
    Thresholds,
    add_whitelist_target,
    load_criteria,
    load_thresholds,
    load_whitelist,
    save_criteria,
    save_thresholds,
    save_whitelist,
)
from careerconductor.ui.common import render_sidebar_status
from careerconductor.ui.theme import apply_theme, hero, status_line

st.set_page_config(page_title="Configuration — CareerConductor", layout="wide")
apply_theme()
render_sidebar_status()
hero("Configuration", "Criteria, targets, and thresholds — set once, persists forever")

# Flash pattern: messages set before st.rerun() would vanish with the rerun,
# so they're stashed in session_state and shown on the next render instead.
if "flash" in st.session_state:
    st.success(st.session_state.pop("flash"))

col1, col2 = st.columns(2)
with col1:
    status_line(bool(settings.anthropic_api_key),
                "ANTHROPIC_API_KEY " + ("set" if settings.anthropic_api_key else "not set"))
with col2:
    status_line(bool(settings.gemini_api_key),
                "GEMINI_API_KEY " + ("set" if settings.gemini_api_key
                                     else "not set (pre-filter will be skipped)"))
st.caption("Keys live in `.env` at the project root — the UI doesn't store them.")

# ------------------------------------------------------- Personal criteria
with st.expander("Personal criteria", expanded=True):
    st.caption(
        "Plain language works best — these lines are injected verbatim into the AI "
        "prompts that screen and score every posting, like a hiring brief about you."
    )
    c = load_criteria()
    target_roles = st.text_area("Target roles", value=c.target_roles, height=68)
    locations = st.text_area("Acceptable locations", value=c.locations, height=68)
    min_salary = st.number_input(
        "Minimum acceptable salary (USD/year)", min_value=0, max_value=1_000_000,
        value=c.min_salary, step=5000,
    )
    interview_preferences = st.text_area("Interview preferences", value=c.interview_preferences, height=68)
    about = st.text_area(
        "About you (optional)", value=c.about, height=100,
        placeholder="Background, strengths, industries you know, what energizes you...",
    )
    dealbreakers = st.text_area(
        "Dealbreakers (optional)", value=c.dealbreakers, height=68,
        placeholder="e.g. no crypto companies, no >25% travel, no on-call...",
    )

    if st.button("Save criteria", type="primary"):
        save_criteria(PersonalCriteria(
            target_roles=target_roles, locations=locations, min_salary=int(min_salary),
            interview_preferences=interview_preferences, about=about, dealbreakers=dealbreakers,
        ))
        st.session_state.flash = "Personal criteria saved — next pipeline run uses them."
        st.rerun()

# -------------------------------------------------------- Whitelist targets
with st.expander("Whitelist targets", expanded=True):
    st.caption(
        "Paste any careers-page URL. The app detects the platform (Greenhouse or "
        "Lever), verifies it against the official public API, and adds it — no "
        "manual token hunting needed."
    )

    pasted_url = st.text_input(
        "Careers page URL",
        placeholder="https://boards.greenhouse.io/acme  ·  https://jobs.lever.co/acme",
    )
    if st.button("Add & verify", type="primary", disabled=not pasted_url.strip()):
        target = detect_target(pasted_url)
        if target is None:
            st.error(
                "Couldn't recognize that URL. Supported: boards.greenhouse.io/<company>, "
                "job-boards.greenhouse.io/<company>, jobs.lever.co/<company>. "
                "Company sites often link to one of these from their careers page."
            )
        else:
            with st.spinner(f"Verifying {target.board_token} on {target.board_type}..."):
                result = verify_target(target)
            if not result.ok:
                st.error(result.message)
            elif add_whitelist_target(target):
                st.session_state.flash = f"Added {target.company_name} — {result.message}"
                st.rerun()
            else:
                st.info(f"{target.company_name} is already on the whitelist. ({result.message})")

    targets = load_whitelist()
    st.markdown(f"**Current whitelist ({len(targets)})** — edit or remove rows below, then save.")

    edited = st.data_editor(
        [
            {"company_name": t.company_name, "board_type": t.board_type, "board_token": t.board_token}
            for t in targets
        ],
        num_rows="dynamic",
        use_container_width=True,
        column_config={
            "company_name": st.column_config.TextColumn("Company"),
            "board_type": st.column_config.SelectboxColumn("Board type", options=["greenhouse", "lever"]),
            "board_token": st.column_config.TextColumn("Board token"),
        },
        key="whitelist_editor",
    )

    if st.button("Save whitelist"):
        clean_rows = [
            r for r in edited
            if r.get("company_name") and r.get("board_type") and r.get("board_token")
        ]
        save_whitelist([ScrapeTarget(**r) for r in clean_rows])
        st.session_state.flash = f"Saved {len(clean_rows)} whitelist target(s)."
        st.rerun()

# ---------------------------------------------------- Selection thresholds
with st.expander("Selection thresholds", expanded=True):
    st.caption(
        "A scored job must pass all three score gates to be eligible; the best-ranked "
        "eligible jobs up to the per-run cap get artifacts generated."
    )
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
    max_artifacts = st.slider(
        "Max artifacts per run (cost control — best-ranked jobs kept)",
        min_value=1, max_value=50, value=current.max_artifacts_per_run, step=1,
    )

    if st.button("Save thresholds", type="primary", key="save_thresholds"):
        save_thresholds(Thresholds(
            max_friction=max_friction, min_stability=min_stability,
            min_location_fit=min_location_fit, max_artifacts_per_run=max_artifacts,
        ))
        st.session_state.flash = "Thresholds saved."
        st.rerun()
