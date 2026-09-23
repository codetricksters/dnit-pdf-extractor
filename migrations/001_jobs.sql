-- Extraction jobs and per-file results.
-- Replaces the idempotent _SCHEMA_SQL previously executed by job_manager on
-- every SQLite connection.

CREATE TABLE IF NOT EXISTS jobs (
    job_id     TEXT PRIMARY KEY,
    created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    completed  BOOLEAN NOT NULL DEFAULT FALSE,
    updated_at TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE TABLE IF NOT EXISTS file_results (
    id           BIGINT GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    job_id       TEXT NOT NULL REFERENCES jobs(job_id) ON DELETE CASCADE,
    filename     TEXT NOT NULL,
    status       TEXT NOT NULL DEFAULT 'pending',
    error        TEXT,
    result_path  TEXT,
    needs_ocr    BOOLEAN,
    started_at   TIMESTAMPTZ,
    completed_at TIMESTAMPTZ,
    UNIQUE (job_id, filename)
);

CREATE INDEX IF NOT EXISTS idx_file_results_job_id ON file_results(job_id);
CREATE INDEX IF NOT EXISTS idx_file_results_status ON file_results(status);
