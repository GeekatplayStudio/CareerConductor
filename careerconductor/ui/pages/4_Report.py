"""Report page: pipeline funnel, scoring charts, score-profile radar, salary/score
quadrant, discovery timeline, top candidates, artifacts, and status management."""
from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[3]))

import pandas as pd
import plotly.express as px
import plotly.graph_objects as go
import streamlit as st

from careerconductor.ui.common import get_db, render_sidebar_status
from careerconductor.ui.theme import ACCENT, ACCENT_2, apply_theme, hero

# One styling pass for every chart on the page: transparent glass background,
# light text, and a fixed accent colorway so all figures read as one system.
COLORWAY = [ACCENT, ACCENT_2, "#f0abfc", "#34d399", "#fbbf24", "#fb7185", "#60a5fa"]


def _style(fig):
    fig.update_layout(
        paper_bgcolor="rgba(0,0,0,0)",
        plot_bgcolor="rgba(15,21,40,0.35)",
        font_color="#cbd5e1",
        colorway=COLORWAY,
        margin=dict(t=30, r=10, l=10, b=10),
        legend=dict(bgcolor="rgba(0,0,0,0)"),
    )
    fig.update_xaxes(gridcolor="rgba(148,163,184,.12)", zerolinecolor="rgba(148,163,184,.2)")
    fig.update_yaxes(gridcolor="rgba(148,163,184,.12)", zerolinecolor="rgba(148,163,184,.2)")
    return fig


st.set_page_config(page_title="Report — CareerConductor", layout="wide")
apply_theme()
render_sidebar_status()
hero("Report", "Everything the agents found, scored, and generated")

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
st.plotly_chart(_style(fig_funnel), use_container_width=True)

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
        st.plotly_chart(_style(fig_scatter), use_container_width=True)

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
        st.plotly_chart(_style(fig_salary), use_container_width=True)

st.divider()

# ------------------------------------------------- deeper analytical charts
scored_full = scored.copy()
if not scored_full.empty:
    scored_full["composite"] = (
        scored_full["match_rating"].fillna(0)
        + scored_full["stability_rating"]
        - scored_full["friction_rating"]
        + scored_full["location_fit_rating"]
        + scored_full["salary_rating"].fillna(0)
    )

col3, col4 = st.columns(2)

with col3:
    st.subheader("Score profiles — top 5 head-to-head")
    st.caption("Radar of all five dimensions. Friction is inverted (10 − friction) so bigger is always better.")
    if scored_full.empty:
        st.caption("No scored jobs yet.")
    else:
        radar_dims = ["Match", "Stability", "Low friction", "Location", "Salary fit"]
        fig_radar = go.Figure()
        for _, r in scored_full.nlargest(5, "composite").iterrows():
            fig_radar.add_trace(go.Scatterpolar(
                r=[
                    r["match_rating"] or 0, r["stability_rating"],
                    10 - r["friction_rating"], r["location_fit_rating"],
                    r["salary_rating"] or 0,
                ],
                theta=radar_dims,
                fill="toself",
                opacity=0.55,
                name=f"{r['company_name']} — {r['job_title'][:24]}",
            ))
        fig_radar.update_layout(
            polar=dict(
                bgcolor="rgba(15,21,40,0.35)",
                radialaxis=dict(range=[0, 10], gridcolor="rgba(148,163,184,.18)"),
                angularaxis=dict(gridcolor="rgba(148,163,184,.18)"),
            ),
            height=420,
        )
        st.plotly_chart(_style(fig_radar), use_container_width=True)

with col4:
    st.subheader("Pay vs. fit quadrant")
    st.caption("Top-right = well paid AND well matched. Bubble size = stability; midlines at the medians.")
    quad = scored_full.dropna(subset=["salary_ceiling"]) if not scored_full.empty else scored_full
    if quad.empty:
        st.caption("No salary data yet.")
    else:
        fig_quad = px.scatter(
            quad, x="composite", y="salary_ceiling",
            size=quad["stability_rating"].clip(lower=1), color="company_name",
            hover_data=["job_title", "location", "perks"],
            labels={"composite": "Composite fit score", "salary_ceiling": "Salary ceiling (USD)"},
            height=420,
        )
        fig_quad.add_hline(y=quad["salary_ceiling"].median(), line_dash="dot",
                           line_color="rgba(148,163,184,.5)")
        fig_quad.add_vline(x=quad["composite"].median(), line_dash="dot",
                           line_color="rgba(148,163,184,.5)")
        st.plotly_chart(_style(fig_quad), use_container_width=True)

st.subheader("Discovery timeline")
st.caption("Postings entering the ledger over time — spot which scrape runs actually found new roles.")
timeline = df.copy()
timeline["scraped_day"] = pd.to_datetime(timeline["scraped_at"]).dt.date
by_day = timeline.groupby("scraped_day").size().reset_index(name="new_jobs")
by_day["cumulative"] = by_day["new_jobs"].cumsum()
fig_time = go.Figure()
fig_time.add_trace(go.Bar(x=by_day["scraped_day"], y=by_day["new_jobs"],
                          name="New postings", marker_color=ACCENT, opacity=0.75))
fig_time.add_trace(go.Scatter(x=by_day["scraped_day"], y=by_day["cumulative"],
                              name="Total tracked", mode="lines+markers",
                              line=dict(color=ACCENT_2, width=3)))
st.plotly_chart(_style(fig_time), use_container_width=True)

st.divider()

st.subheader("Top candidates")
top = db.top_candidates(limit=15)
if not top:
    st.caption("No scored jobs yet.")
else:
    top_df = pd.DataFrame([dict(r) for r in top])
    # Same composite formula as selection.composite_score / repository.top_candidates.
    # fillna(0) mirrors SQL's COALESCE for rows scored by an older version.
    top_df["score"] = (
        top_df["match_rating"].fillna(0)
        + top_df["stability_rating"]
        - top_df["friction_rating"]
        + top_df["location_fit_rating"]
        + top_df["salary_rating"].fillna(0)
    )
    top_df = top_df[[
        "score", "company_name", "job_title", "location", "match_rating",
        "stability_rating", "friction_rating", "location_fit_rating", "salary_rating",
        "salary_floor", "salary_ceiling", "perks", "analysis_notes", "status", "source_url",
    ]]
    st.caption(
        "Score = match + stability − friction + location fit + salary fit "
        "(the same formula the pipeline ranks by)."
    )
    st.dataframe(
        top_df,
        use_container_width=True,
        hide_index=True,
        column_config={
            "score": st.column_config.NumberColumn("Score", format="%.1f"),
            "match_rating": st.column_config.NumberColumn("Match", format="%.1f"),
            "salary_rating": st.column_config.NumberColumn("Salary fit", format="%.1f"),
            "salary_floor": st.column_config.NumberColumn("Salary floor", format="$%d"),
            "salary_ceiling": st.column_config.NumberColumn("Salary ceiling", format="$%d"),
            "perks": st.column_config.TextColumn("Perks"),
            "analysis_notes": st.column_config.TextColumn("AI notes"),
            "source_url": st.column_config.LinkColumn("Posting", display_text="open"),
        },
    )

st.divider()

st.subheader("Generated artifacts")
generated = [r for r in rows if r["generated_resume_path"]]
if not generated:
    st.caption("No artifacts generated yet.")
else:
    # Label includes the hash prefix: two postings can share company+title
    # (e.g. same role in two locations), and dict keys must stay unique or a
    # collision would silently show/download the wrong job's artifacts.
    options = {
        f"{r['company_name']} — {r['job_title']} [{r['job_hash'][:8]}]": r for r in generated
    }
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
                content = path.read_text(encoding="utf-8")
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
# Hash prefix in the label for the same collision reason as the artifact viewer.
status_options = {
    f"{r['company_name']} — {r['job_title']} ({r['status']}) [{r['job_hash'][:8]}]": r
    for r in rows
}
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
    "company_name", "job_title", "location", "status", "match_rating",
    "stability_rating", "friction_rating", "location_fit_rating", "salary_rating",
    "salary_floor", "salary_ceiling", "salary_is_estimated", "perks",
    "analysis_notes", "source_url", "scraped_at",
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
