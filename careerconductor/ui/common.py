"""Shared helpers for the Streamlit UI pages."""
from __future__ import annotations

import streamlit as st

from careerconductor.config.settings import settings
from careerconductor.db.repository import CareerConductorDB


@st.cache_resource
def get_db() -> CareerConductorDB:
    return CareerConductorDB(db_path=settings.db_path)


def render_sidebar_status() -> None:
    db = get_db()
    st.sidebar.markdown("### Status")
    st.sidebar.write(f"Anthropic key: {'✅ set' if settings.anthropic_api_key else '❌ missing'}")
    st.sidebar.write(f"Gemini key: {'✅ set' if settings.gemini_api_key else '❌ missing'}")
    counts = db.status_counts()
    total = sum(counts.values())
    st.sidebar.write(f"Jobs tracked: {total}")
