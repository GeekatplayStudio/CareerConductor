CREATE TABLE IF NOT EXISTS jobs_master (
    job_hash TEXT PRIMARY KEY,          -- sha256(company + job id/url): idempotency key
    company_name TEXT NOT NULL,
    job_title TEXT NOT NULL,
    location TEXT,
    source_url TEXT,
    salary_floor INTEGER,               -- listed in posting, or AI-estimated
    salary_ceiling INTEGER,
    salary_is_estimated INTEGER DEFAULT 0,
    stability_rating REAL,              -- all ratings 0-10, filled by the analysis agent
    friction_rating REAL,               -- 10 = worst (heavy live-coding interviews)
    location_fit_rating REAL,
    match_rating REAL,                  -- fit vs. the candidate's personal criteria
    salary_rating REAL,                 -- comp vs. the candidate's minimum expectation
    perks TEXT,                         -- notable bonuses/benefits spotted by the AI
    analysis_notes TEXT,                -- anything else the AI flagged as worth knowing
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
