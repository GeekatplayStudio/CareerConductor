"""SQLite repository layer for CareerConductor. Owns all persistence and idempotency checks."""
from __future__ import annotations

import hashlib
import json
import sqlite3
from contextlib import contextmanager
from dataclasses import dataclass
from pathlib import Path
from typing import Iterator, Optional

_SCHEMA_PATH = Path(__file__).parent / "schema.sql"


def compute_job_hash(company_name: str, job_id_or_url: str) -> str:
    key = f"{company_name.strip().lower()}::{job_id_or_url.strip().lower()}"
    return hashlib.sha256(key.encode("utf-8")).hexdigest()


@dataclass
class JobRecord:
    job_hash: str
    company_name: str
    job_title: str
    location: str
    source_url: str
    raw_payload: str
    salary_floor: Optional[int] = None
    salary_ceiling: Optional[int] = None
    salary_is_estimated: bool = False
    stability_rating: Optional[float] = None
    friction_rating: Optional[float] = None
    location_fit_rating: Optional[float] = None


class CareerConductorDB:
    def __init__(self, db_path: str = "./careerconductor.db"):
        self.db_path = db_path
        self._init_schema()

    @contextmanager
    def _connect(self) -> Iterator[sqlite3.Connection]:
        conn = sqlite3.connect(self.db_path)
        conn.execute("PRAGMA foreign_keys = ON;")
        conn.row_factory = sqlite3.Row
        try:
            yield conn
            conn.commit()
        finally:
            conn.close()

    # Columns added after the first release. CREATE TABLE IF NOT EXISTS won't touch
    # an existing table, so upgrades apply each ALTER and ignore the "duplicate
    # column" error when it already ran — a minimal, dependency-free migration story.
    _MIGRATIONS = (
        "ALTER TABLE jobs_master ADD COLUMN match_rating REAL",
        "ALTER TABLE jobs_master ADD COLUMN salary_rating REAL",
        "ALTER TABLE jobs_master ADD COLUMN perks TEXT",
        "ALTER TABLE jobs_master ADD COLUMN analysis_notes TEXT",
    )

    def _init_schema(self) -> None:
        with self._connect() as conn:
            conn.executescript(_SCHEMA_PATH.read_text())
            for statement in self._MIGRATIONS:
                try:
                    conn.execute(statement)
                except sqlite3.OperationalError as exc:
                    if "duplicate column" not in str(exc).lower():
                        raise

    def job_exists(self, job_hash: str) -> bool:
        with self._connect() as conn:
            row = conn.execute(
                "SELECT 1 FROM jobs_master WHERE job_hash = ?", (job_hash,)
            ).fetchone()
            return row is not None

    def insert_job(self, job: JobRecord) -> None:
        with self._connect() as conn:
            conn.execute(
                """
                INSERT OR IGNORE INTO jobs_master (
                    job_hash, company_name, job_title, location, source_url,
                    salary_floor, salary_ceiling, salary_is_estimated,
                    stability_rating, friction_rating, location_fit_rating, raw_payload
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    job.job_hash, job.company_name, job.job_title, job.location, job.source_url,
                    job.salary_floor, job.salary_ceiling, int(job.salary_is_estimated),
                    job.stability_rating, job.friction_rating, job.location_fit_rating,
                    job.raw_payload,
                ),
            )
            conn.execute(
                """
                INSERT OR IGNORE INTO applications_ledger (application_id, job_hash, status)
                VALUES (?, ?, 'discovered')
                """,
                (f"app_{job.job_hash[:16]}", job.job_hash),
            )

    def update_ratings(
        self, job_hash: str, stability: float, friction: float, location_fit: float,
        salary_floor: Optional[int] = None, salary_ceiling: Optional[int] = None,
        salary_is_estimated: bool = False,
        match: Optional[float] = None, salary_fit: Optional[float] = None,
        perks: Optional[str] = None, notes: Optional[str] = None,
    ) -> None:
        with self._connect() as conn:
            conn.execute(
                """
                UPDATE jobs_master
                SET stability_rating = ?, friction_rating = ?, location_fit_rating = ?,
                    salary_floor = COALESCE(?, salary_floor),
                    salary_ceiling = COALESCE(?, salary_ceiling),
                    -- The estimated flag describes the salary values; when no new
                    -- values are supplied (floor IS NULL) the old flag must survive
                    -- too, or a rating-only update would mislabel real salary data.
                    salary_is_estimated = CASE WHEN ? IS NULL THEN salary_is_estimated ELSE ? END,
                    match_rating = ?, salary_rating = ?, perks = ?, analysis_notes = ?
                WHERE job_hash = ?
                """,
                (stability, friction, location_fit, salary_floor, salary_ceiling,
                 salary_floor, int(salary_is_estimated), match, salary_fit, perks, notes,
                 job_hash),
            )
            conn.execute(
                "UPDATE applications_ledger SET status = 'analyzed', updated_at = CURRENT_TIMESTAMP "
                "WHERE job_hash = ? AND status = 'discovered'",
                (job_hash,),
            )

    def set_generated_artifacts(
        self, job_hash: str, resume_path: str, cover_letter_path: str
    ) -> None:
        with self._connect() as conn:
            conn.execute(
                """
                UPDATE applications_ledger
                SET status = 'generated', generated_resume_path = ?, generated_cover_letter_path = ?,
                    updated_at = CURRENT_TIMESTAMP
                WHERE job_hash = ?
                """,
                (resume_path, cover_letter_path, job_hash),
            )

    def top_candidates(self, limit: int = 20) -> list[sqlite3.Row]:
        with self._connect() as conn:
            return conn.execute(
                """
                SELECT j.*, a.status FROM jobs_master j
                JOIN applications_ledger a ON a.job_hash = j.job_hash
                WHERE j.stability_rating IS NOT NULL
                -- Same composite formula as agents/selection.py::composite_score.
                -- COALESCE keeps rows scored by an older version (no match/salary
                -- ratings) sortable instead of sinking them to NULL.
                ORDER BY (COALESCE(j.match_rating, 0) + j.stability_rating
                          - j.friction_rating + j.location_fit_rating
                          + COALESCE(j.salary_rating, 0)) DESC
                LIMIT ?
                """,
                (limit,),
            ).fetchall()

    def unanalyzed_jobs(self) -> list[sqlite3.Row]:
        """Jobs scraped in an earlier run whose analysis never succeeded.

        Status stays 'discovered' until update_ratings flips it to 'analyzed', so
        this catches postings lost to transient API failures — the scraper re-queues
        them instead of skipping them forever as "already seen".
        """
        with self._connect() as conn:
            return conn.execute(
                """
                SELECT j.* FROM jobs_master j
                JOIN applications_ledger a ON a.job_hash = j.job_hash
                WHERE a.status = 'discovered'
                """
            ).fetchall()

    def all_jobs(self) -> list[sqlite3.Row]:
        with self._connect() as conn:
            return conn.execute(
                """
                SELECT j.*, a.status, a.generated_resume_path, a.generated_cover_letter_path
                FROM jobs_master j
                JOIN applications_ledger a ON a.job_hash = j.job_hash
                ORDER BY j.scraped_at DESC
                """
            ).fetchall()

    def status_counts(self) -> dict[str, int]:
        with self._connect() as conn:
            rows = conn.execute(
                "SELECT status, COUNT(*) AS n FROM applications_ledger GROUP BY status"
            ).fetchall()
            return {row["status"]: row["n"] for row in rows}

    def set_status(self, job_hash: str, status: str) -> None:
        with self._connect() as conn:
            conn.execute(
                "UPDATE applications_ledger SET status = ?, updated_at = CURRENT_TIMESTAMP "
                "WHERE job_hash = ?",
                (status, job_hash),
            )

    def record_upload(
        self, upload_id: str, file_kind: str, original_filename: str,
        stored_path: str, sha256: str, size_bytes: int,
    ) -> None:
        with self._connect() as conn:
            # OR REPLACE (not IGNORE): re-uploading identical content refreshes the
            # history row's filename and timestamp instead of silently vanishing —
            # the audit trail should reflect the latest upload event.
            conn.execute(
                """
                INSERT OR REPLACE INTO uploaded_files
                    (upload_id, file_kind, original_filename, stored_path, sha256, size_bytes)
                VALUES (?, ?, ?, ?, ?, ?)
                """,
                (upload_id, file_kind, original_filename, stored_path, sha256, size_bytes),
            )

    def list_uploads(self, file_kind: Optional[str] = None) -> list[sqlite3.Row]:
        with self._connect() as conn:
            if file_kind:
                return conn.execute(
                    "SELECT * FROM uploaded_files WHERE file_kind = ? ORDER BY uploaded_at DESC",
                    (file_kind,),
                ).fetchall()
            return conn.execute(
                "SELECT * FROM uploaded_files ORDER BY uploaded_at DESC"
            ).fetchall()
