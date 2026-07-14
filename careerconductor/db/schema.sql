CREATE TABLE IF NOT EXISTS jobs_master (
    job_hash TEXT PRIMARY KEY,
    company_name TEXT NOT NULL,
    job_title TEXT NOT NULL,
    location TEXT,
    source_url TEXT,
    salary_floor INTEGER,
    salary_ceiling INTEGER,
    salary_is_estimated INTEGER DEFAULT 0,
    stability_rating REAL,
    friction_rating REAL,
    location_fit_rating REAL,
    raw_payload TEXT,
    scraped_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE IF NOT EXISTS applications_ledger (
    application_id TEXT PRIMARY KEY,
    job_hash TEXT NOT NULL,
    status TEXT NOT NULL CHECK(status IN ('discovered', 'analyzed', 'generated', 'applied', 'archived')),
    generated_resume_path TEXT,
    generated_cover_letter_path TEXT,
    referral_contacts TEXT,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY(job_hash) REFERENCES jobs_master(job_hash)
);

CREATE INDEX IF NOT EXISTS idx_ledger_job_hash ON applications_ledger(job_hash);
CREATE INDEX IF NOT EXISTS idx_ledger_status ON applications_ledger(status);

CREATE TABLE IF NOT EXISTS uploaded_files (
    upload_id TEXT PRIMARY KEY,
    file_kind TEXT NOT NULL CHECK(file_kind IN ('master_resume', 'project_database')),
    original_filename TEXT NOT NULL,
    stored_path TEXT NOT NULL,
    sha256 TEXT NOT NULL,
    size_bytes INTEGER NOT NULL,
    uploaded_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

CREATE INDEX IF NOT EXISTS idx_uploads_kind ON uploaded_files(file_kind);
