"""Report page: pipeline funnel, scoring charts, salary ranges, top candidates, logs."""
from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[3]))

import pandas as pd
import plotly.express as px
import streamlit as st

from careerconductor.ui.common import get_db, render_sidebar_status

st.set_page_config(page_title="Report — CareerConductor", page_icon="📊", layout="wide")
render_sidebar_status()
st.title("📊 Report")

if "flash" in st.session_state:
    st.success(st.session_state.pop("flash"))

db = get_db()
rows = db.all_jobs()

if not rows:
    st.info("No jobs tracked yet. Run the pipeline from the **Run Pipeline** page first.")
    st.stop()

df = pd.DataFrame([dict(r) for r in rows])

STATUS_ORDER = ["discovered", "analyzed", "generated", "applied", "archived"]
counts = db.status_counts()

st.subheader("Pipeline funnel")
funnel_df = pd.DataFrame(
    {"stage": STATUS_ORDER, "count": [counts.get(s, 0) for s in STATUS_ORDER]}
)
fig_funnel = px.funnel(funnel_df, x="count", y="stage")
st.plotly_chart(fig_funnel, use_container_width=True)

st.divider()

scored = df.dropna(subset=["stability_rating", "friction_rating", "location_fit_rating"])

col1, col2 = st.columns(2)

with col1:
    st.subheader("Stability vs. interview friction")
    if scored.empty:
        st.caption("No scored jobs yet.")
    else:
        fig_scatter = px.scatter(
            scored, x="friction_rating", y="stability_rating",
            size="location_fit_rating", color="company_name",
            hover_data=["job_title", "location"],
            labels={"friction_rating": "Interview friction (lower is better)",
                    "stability_rating": "Company stability"},
        )
        st.plotly_chart(fig_scatter, use_container_width=True)

with col2:
    st.subheader("Salary ranges by company")
    salary_df = df.dropna(subset=["salary_floor", "salary_ceiling"])
    if salary_df.empty:
        st.caption("No salary data yet.")
    else:
        salary_df = salary_df.sort_values("salary_ceiling", ascending=False).head(20)
        fig_salary = px.bar(
            salary_df, x="job_title", y=["salary_floor", "salary_ceiling"],
            barmode="group", hover_data=["company_name"],
        )
        st.plotly_chart(fig_salary, use_container_width=True)

st.divider()

st.subheader("Top candidates")
top = db.top_candidates(limit=15)
if not top:
    st.caption("No scored jobs yet.")
else:
    top_df = pd.DataFrame([dict(r) for r in top])
    top_df["score"] = (
        top_df["stability_rating"] - top_df["friction_rating"] + top_df["location_fit_rating"]
    )
    top_df = top_df[[
        "score", "company_name", "job_title", "location", "stability_rating",
        "friction_rating", "location_fit_rating", "salary_floor",
        "salary_ceiling", "status", "source_url",
    ]]
    st.caption("Score = stability − friction + location fit (same formula the pipeline ranks by).")
    st.dataframe(
        top_df,
        use_container_width=True,
        hide_index=True,
        column_config={
            "score": st.column_config.NumberColumn("Score", format="%.1f"),
            "salary_floor": st.column_config.NumberColumn("Salary floor", format="$%d"),
            "salary_ceiling": st.column_config.NumberColumn("Salary ceiling", format="$%d"),
            "source_url": st.column_config.LinkColumn("Posting", display_text="open"),
        },
    )

st.divider()

st.subheader("Generated artifacts")
generated = [r for r in rows if r["generated_resume_path"]]
if not generated:
    st.caption("No artifacts generated yet.")
else:
    options = {f"{r['company_name']} — {r['job_title']}": r for r in generated}
    choice = st.selectbox("Job", list(options.keys()))
    row = options[choice]
    col_resume, col_letter = st.columns(2)
    for col, label, path_key in (
        (col_resume, "Resume", "generated_resume_path"),
        (col_letter, "Cover letter", "generated_cover_letter_path"),
    ):
        with col:
            st.markdown(f"**{label}**")
            path = Path(row[path_key]) if row[path_key] else None
            if path is None or not path.exists():
                st.warning(f"File not found: {row[path_key]}")
            else:
                content = path.read_text()
                st.download_button(
                    f"Download {label.lower()} (.md)", content,
                    file_name=path.name, mime="text/markdown",
                    key=f"dl_{path_key}_{row['job_hash']}",
                )
                with st.expander(f"Preview {label.lower()}", expanded=False):
                    st.markdown(content)

st.divider()

st.subheader("Update application status")
st.caption("Mark a job as applied once you've submitted, or archive ones you're skipping.")
status_options = {f"{r['company_name']} — {r['job_title']} ({r['status']})": r for r in rows}
status_choice = st.selectbox("Job", list(status_options.keys()), key="status_job")
status_row = status_options[status_choice]
new_status = st.selectbox("New status", ["applied", "archived", "generated", "analyzed"], key="status_value")
if st.button("Update status", type="primary"):
    db.set_status(status_row["job_hash"], new_status)
    st.session_state.flash = (
        f"{status_row['company_name']} — {status_row['job_title']} → {new_status}"
    )
    st.rerun()

st.divider()

st.subheader("All tracked jobs")
status_filter = st.multiselect(
    "Filter by status", STATUS_ORDER, default=STATUS_ORDER, key="all_jobs_status_filter",
)
df = df[df["status"].isin(status_filter)]
display_cols = [
    "company_name", "job_title", "location", "status", "stability_rating",
    "friction_rating", "location_fit_rating", "salary_floor", "salary_ceiling",
    "salary_is_estimated", "source_url", "scraped_at",
]
st.dataframe(
    df[[c for c in display_cols if c in df.columns]],
    use_container_width=True,
    hide_index=True,
    column_config={
        "salary_floor": st.column_config.NumberColumn("Salary floor", format="$%d"),
        "salary_ceiling": st.column_config.NumberColumn("Salary ceiling", format="$%d"),
        "source_url": st.column_config.LinkColumn("Posting", display_text="open"),
    },
)
