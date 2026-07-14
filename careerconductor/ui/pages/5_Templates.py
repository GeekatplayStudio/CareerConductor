"""Templates page: pick the visual/structural style for generated resumes, and
generate a downloadable single-file CV web page in that style.

The gallery previews are pure CSS cards built from each template's accent color
and font hint — comparing styles costs zero API tokens; only the CV web page
button calls the model.
"""
from __future__ import annotations

import html
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[3]))

import streamlit as st
import streamlit.components.v1 as components

from careerconductor.config.settings import settings
from careerconductor.templates.cv_webpage import generate_cv_webpage
from careerconductor.templates.resume_templates import (
    TEMPLATES,
    categories,
    load_selected_template,
    save_selected_template,
)
from careerconductor.ui.common import render_sidebar_status
from careerconductor.ui.theme import apply_theme, hero

st.set_page_config(page_title="Templates — CareerConductor", layout="wide")
apply_theme()
render_sidebar_status()
hero("Resume Templates", "Pick the style that ships with every tailored resume")

if "flash" in st.session_state:
    st.success(st.session_state.pop("flash"))

selected = load_selected_template()
st.markdown(
    f"Current template: **{selected.name}** ({selected.category}) — every tailored "
    "resume the pipeline generates follows this style."
)
st.divider()


def _preview_card(t) -> str:
    """A miniature faux-resume rendered from the template's visual DNA."""
    return f"""
    <div style="border:1px solid #d4d4d8;border-radius:8px;overflow:hidden;
                font-family:{t.preview_font};background:#ffffff;color:#18181b;">
      <div style="background:{t.accent};height:8px;"></div>
      <div style="padding:12px 14px;">
        <div style="font-weight:700;font-size:15px;color:{t.accent};">Jordan Doe</div>
        <div style="font-size:10px;color:#52525b;margin-bottom:8px;">{html.escape(t.category)} style</div>
        <div style="height:5px;background:#e4e4e7;border-radius:3px;width:90%;margin:4px 0;"></div>
        <div style="height:5px;background:#e4e4e7;border-radius:3px;width:75%;margin:4px 0;"></div>
        <div style="height:5px;background:{t.accent}33;border-radius:3px;width:60%;margin:4px 0;"></div>
        <div style="height:5px;background:#e4e4e7;border-radius:3px;width:85%;margin:4px 0;"></div>
      </div>
    </div>"""


# Gallery grouped by category, three cards per row.
for category in categories():
    st.subheader(category)
    group = [t for t in TEMPLATES if t.category == category]
    cols = st.columns(3)
    for i, t in enumerate(group):
        with cols[i % 3]:
            st.markdown(_preview_card(t), unsafe_allow_html=True)
            st.markdown(f"**{t.name}**")
            st.caption(t.description)
            is_current = t.key == selected.key
            if st.button(
                "✓ Selected" if is_current else "Use this template",
                key=f"pick_{t.key}",
                type="primary" if is_current else "secondary",
                disabled=is_current,
            ):
                save_selected_template(t.key)
                st.session_state.flash = f"Template set to {t.name}."
                st.rerun()

st.divider()

# ------------------------------------------------------------ CV web page
st.subheader("CV web page")
st.caption(
    "Generate a self-contained HTML page of your master resume in the selected "
    "template's style — host it anywhere (GitHub Pages, Netlify) or send the file "
    "directly. No external dependencies; it even prints cleanly."
)

resume_path = Path(settings.master_resume_path)
resume_text = resume_path.read_text() if resume_path.exists() else ""

if not settings.anthropic_api_key:
    st.warning("ANTHROPIC_API_KEY is not set — add it to `.env` to generate the page.")
elif len(resume_text.strip()) < 200:
    st.warning("Master resume looks empty — upload it on the Upload page first.")
else:
    if st.button(f"Generate CV web page ({selected.name} style)", type="primary"):
        with st.spinner("Generating your CV web page..."):
            try:
                html_doc = generate_cv_webpage(resume_text, selected)
            except Exception as exc:  # noqa: BLE001 - surface as a friendly message
                st.error(f"Generation failed: {exc}")
            else:
                out_dir = Path(settings.artifact_output_dir)
                out_dir.mkdir(parents=True, exist_ok=True)
                out_path = out_dir / f"cv_webpage_{selected.key}.html"
                out_path.write_text(html_doc)
                # Session state survives the download-button rerun, so the preview
                # and button don't vanish after generation.
                st.session_state.cv_html = html_doc
                st.session_state.cv_name = out_path.name

    if "cv_html" in st.session_state:
        st.download_button(
            "Download HTML file",
            st.session_state.cv_html,
            file_name=st.session_state.cv_name,
            mime="text/html",
            type="primary",
        )
        st.markdown("**Preview:**")
        components.html(st.session_state.cv_html, height=600, scrolling=True)
