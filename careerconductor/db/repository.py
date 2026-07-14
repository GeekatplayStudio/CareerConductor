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
        conn.row_factory = sqlite3.Row
        try:
            yield conn
            conn.commit()
        finally:
            conn.close()

    def _init_schema(self) -> None:
        with self._connect() as conn:
            conn.executescript(_SCHEMA_PATH.read_text())

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
        self, job_hash: str, stability: float, friction: float, location_fit: float
    ) -> None:
        with self._connect() as conn:
            conn.execute(
                """
                UPDATE jobs_master
                SET stability_rating = ?, friction_rating = ?, location_fit_rating = ?
                WHERE job_hash = ?
                """,
                (stability, friction, location_fit, job_hash),
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
                ORDER BY (j.stability_rating - j.friction_rating + j.location_fit_rating) DESC
                LIMIT ?
                """,
                (limit,),
            ).fetchall()
