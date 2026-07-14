"""Core test suite — exercises exactly the properties the README claims.

Run with:  ./.venv/bin/pytest careerconductor/tests/ -v

These tests need no API keys and no network: every pipeline node is a plain
function over dicts, and the repository accepts any SQLite path — the design
properties that make the system testable are themselves what's under test.
"""
from __future__ import annotations

import sqlite3

import pytest

from careerconductor.agents.selection import composite_score, run_selection
from careerconductor.config.board_detect import detect_target
from careerconductor.config.store import (
    PersonalCriteria,
    Thresholds,
    criteria_prompt_block,
)
from careerconductor.db.repository import CareerConductorDB, JobRecord, compute_job_hash


# ---------------------------------------------------------------- repository

@pytest.fixture
def db(tmp_path):
    return CareerConductorDB(db_path=str(tmp_path / "test.db"))


def _insert(db, company="Acme", title="Staff Engineer"):
    h = compute_job_hash(company, title)
    db.insert_job(JobRecord(
        job_hash=h, company_name=company, job_title=title,
        location="Lehi, UT", source_url="https://example.com", raw_payload="{}",
    ))
    return h


def test_job_hash_is_deterministic_and_case_insensitive():
    # Idempotency depends on the same posting always hashing identically.
    assert compute_job_hash("Acme", "123") == compute_job_hash("  ACME ", "123")
    assert compute_job_hash("Acme", "123") != compute_job_hash("Acme", "124")


def test_insert_is_idempotent(db):
    h = _insert(db)
    _insert(db)  # second insert of the same job must be a silent no-op
    assert db.job_exists(h)
    assert len(db.all_jobs()) == 1


def test_ratings_persist_and_flip_status(db):
    h = _insert(db)
    db.update_ratings(h, stability=8, friction=2, location_fit=9,
                      salary_floor=150000, salary_ceiling=190000,
                      salary_is_estimated=True, match=9.0, salary_fit=7.5,
                      perks="equity", notes="reports to CTO")
    row = db.all_jobs()[0]
    assert row["status"] == "analyzed"
    assert row["match_rating"] == 9.0
    assert row["salary_floor"] == 150000
    assert row["perks"] == "equity"


def test_rating_only_update_preserves_salary_and_estimated_flag(db):
    # A later re-score without salary values must not erase or mislabel
    # the salary data already on the row.
    h = _insert(db)
    db.update_ratings(h, 8, 2, 9, salary_floor=150000, salary_ceiling=190000,
                      salary_is_estimated=True)
    db.update_ratings(h, 7, 3, 8)  # no salary args this time
    row = db.all_jobs()[0]
    assert row["salary_floor"] == 150000
    assert row["salary_is_estimated"] == 1


def test_unanalyzed_jobs_requeue_contract(db):
    # Jobs whose analysis never succeeded stay visible for re-queueing;
    # successfully analyzed jobs drop out of the requeue set.
    h1, h2 = _insert(db, "A", "x"), _insert(db, "B", "y")
    db.update_ratings(h1, 8, 2, 9)
    pending = {r["job_hash"] for r in db.unanalyzed_jobs()}
    assert pending == {h2}


def test_migration_adds_new_columns_to_old_database(tmp_path):
    # Simulate a DB created before match/salary/perks columns existed.
    old = str(tmp_path / "old.db")
    conn = sqlite3.connect(old)
    conn.execute(
        "CREATE TABLE jobs_master (job_hash TEXT PRIMARY KEY, company_name TEXT NOT NULL,"
        " job_title TEXT NOT NULL, location TEXT, source_url TEXT, salary_floor INTEGER,"
        " salary_ceiling INTEGER, salary_is_estimated INTEGER DEFAULT 0,"
        " stability_rating REAL, friction_rating REAL, location_fit_rating REAL,"
        " raw_payload TEXT, scraped_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP)"
    )
    conn.commit()
    conn.close()
    CareerConductorDB(db_path=old)  # opening runs the migrations
    cols = [r[1] for r in sqlite3.connect(old).execute("PRAGMA table_info(jobs_master)")]
    assert "match_rating" in cols and "analysis_notes" in cols


# ----------------------------------------------------------------- selection

def _scored_job(i, friction=2.0):
    return {
        "company": f"C{i}", "title": "t", "job_hash": f"h{i}",
        "match_score": 5.0, "interview_friction": friction,
        "stability_score": 5.0 + (i % 5), "location_fit_score": 6.0, "salary_score": 5.0,
    }


def test_selection_gates_ranks_and_caps(tmp_path, monkeypatch):
    from careerconductor.config import store
    monkeypatch.setattr(store, "THRESHOLDS_PATH", tmp_path / "t.json")
    store.save_thresholds(Thresholds(max_artifacts_per_run=3))

    jobs = [_scored_job(i) for i in range(8)] + [_scored_job(99, friction=9.9)]
    out = run_selection({"discovered_jobs": jobs, "execution_logs": []})
    selected = out["selected_jobs"]

    assert len(selected) == 3  # capped
    assert all(j["interview_friction"] <= 6.0 for j in selected)  # gate held
    scores = [composite_score(j) for j in selected]
    assert scores == sorted(scores, reverse=True)  # best-ranked kept


# ------------------------------------------------------------- URL detection

@pytest.mark.parametrize("url,board,token", [
    ("https://boards.greenhouse.io/acme-robotics/jobs/123", "greenhouse", "acme-robotics"),
    ("https://job-boards.greenhouse.io/stripe", "greenhouse", "stripe"),
    ("https://boards.greenhouse.io/embed/job_board?for=initech", "greenhouse", "initech"),
    ("jobs.lever.co/globex", "lever", "globex"),
    ("https://jobs.eu.lever.co/globex/posting-id", "lever", "globex"),
])
def test_detect_target_supported_shapes(url, board, token):
    t = detect_target(url)
    assert t is not None and t.board_type == board and t.board_token == token


def test_detect_target_rejects_unknown_hosts():
    assert detect_target("https://example.com/careers") is None
    assert detect_target("https://greenhouse.io.evil.com/acme") is None  # suffix spoof


# ------------------------------------------------------------------ criteria

def test_criteria_prompt_block_includes_optional_fields_only_when_set():
    minimal = criteria_prompt_block(PersonalCriteria())
    assert "Dealbreakers" not in minimal
    full = criteria_prompt_block(PersonalCriteria(about="3D graphics", dealbreakers="no crypto"))
    assert "3D graphics" in full and "no crypto" in full
    assert "$120,000" in full  # min salary formatted for the model
