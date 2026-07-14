"""Shared helpers for the Streamlit UI pages."""
from __future__ import annotations

import streamlit as st

from careerconductor.config.settings import settings
from careerconductor.db.repository import CareerConductorDB


@st.cache_resource
def get_db() -> CareerConductorDB:
    return CareerConductorDB(db_path=settings.db_path)


def _sidebar_dot(ok: bool, text: str) -> None:
    # Flat single-color marker: filled cyan dot = set, hollow slate dot = missing.
    dot = "&#9679;" if ok else "&#9675;"
    color = "#22d3ee" if ok else "#64748b"
    st.sidebar.markdown(
        f'<div style="margin:2px 0;color:#cbd5e1;font-size:0.92em;">'
        f'<span style="color:{color};">{dot}</span>&nbsp;&nbsp;{text}</div>',
        unsafe_allow_html=True,
    )


def render_sidebar_status() -> None:
    db = get_db()
    st.sidebar.markdown("### Status")
    _sidebar_dot(bool(settings.anthropic_api_key), "Anthropic key")
    _sidebar_dot(bool(settings.gemini_api_key), "Gemini key")
    counts = db.status_counts()
    st.sidebar.markdown(
        f'<div style="margin-top:6px;color:#94a3b8;font-size:0.92em;">'
        f'Jobs tracked: {sum(counts.values())}</div>',
        unsafe_allow_html=True,
    )
