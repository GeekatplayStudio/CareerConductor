"""Upload page: master resume + project database, with upload history tracking."""
from __future__ import annotations

import hashlib
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[3]))

import streamlit as st

from careerconductor.config.settings import settings
from careerconductor.ui.common import get_db, render_sidebar_status
from careerconductor.ui.theme import apply_theme, hero

st.set_page_config(page_title="Upload — CareerConductor", layout="wide")
apply_theme()
render_sidebar_status()
hero("Upload", "Master resume and project database — content-hashed and tracked")

if "flash" in st.session_state:
    st.success(st.session_state.pop("flash"))

db = get_db()
UPLOAD_HISTORY_DIR = Path(settings.master_resume_path).parent / "uploads"
UPLOAD_HISTORY_DIR.mkdir(parents=True, exist_ok=True)


def _save_upload(uploaded_file, file_kind: str, canonical_path: Path) -> None:
    content = uploaded_file.getvalue()
    sha256 = hashlib.sha256(content).hexdigest()
    history_path = UPLOAD_HISTORY_DIR / f"{file_kind}__{sha256[:12]}__{uploaded_file.name}"
    history_path.write_bytes(content)
    canonical_path.write_bytes(content)
    # file_kind is part of the id so the same bytes uploaded as resume AND as
    # project DB produce two distinct history rows, not a primary-key collision.
    db.record_upload(
        upload_id=f"up_{file_kind}_{sha256[:16]}",
        file_kind=file_kind,
        original_filename=uploaded_file.name,
        stored_path=str(canonical_path),
        sha256=sha256,
        size_bytes=len(content),
    )


tab1, tab2 = st.tabs(["Master Resume", "Project Database"])

with tab1:
    st.subheader("Master Resume")
    st.caption(
        "Markdown or plain text. The artifact generator tailors from this file only — "
        "it does not invent experience that isn't here."
    )
    current = Path(settings.master_resume_path)
    if current.exists() and current.read_text(encoding="utf-8").strip():
        with st.expander("Current content", expanded=False):
            st.code(current.read_text(encoding="utf-8"), language="markdown")

    resume_file = st.file_uploader("Upload resume (.md or .txt)", type=["md", "txt"], key="resume_upload")
    if resume_file is not None:
        if st.button("Save as master resume", type="primary"):
            _save_upload(resume_file, "master_resume", current)
            st.session_state.flash = f"Saved {resume_file.name} as master resume."
            st.rerun()

with tab2:
    st.subheader("Project Database")
    st.caption('JSON with shape: {"projects": [{"name": ..., "tags": [...], "summary": ..., "keywords": [...]}]}')
    current_db = Path(settings.project_database_path)
    if current_db.exists():
        with st.expander("Current content", expanded=False):
            st.json(json.loads(current_db.read_text(encoding="utf-8")))

    db_file = st.file_uploader("Upload project database (.json)", type=["json"], key="projectdb_upload")
    if db_file is not None:
        try:
            parsed = json.loads(db_file.getvalue().decode("utf-8"))
            if "projects" not in parsed:
                st.error('JSON must have a top-level "projects" key.')
            else:
                st.write(f"Parsed {len(parsed['projects'])} project entries.")
                if st.button("Save as project database", type="primary"):
                    _save_upload(db_file, "project_database", current_db)
                    st.session_state.flash = f"Saved {db_file.name} as project database."
                    st.rerun()
        except json.JSONDecodeError as exc:
            st.error(f"Invalid JSON: {exc}")

st.divider()
st.subheader("Upload history")
uploads = db.list_uploads()
if not uploads:
    st.caption("Nothing uploaded yet.")
else:
    st.dataframe(
        [
            {
                "kind": u["file_kind"],
                "filename": u["original_filename"],
                "size (bytes)": u["size_bytes"],
                "sha256": u["sha256"][:12],
                "uploaded_at": u["uploaded_at"],
            }
            for u in uploads
        ],
        use_container_width=True,
        hide_index=True,
    )
