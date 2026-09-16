-- Exact pre-Phase-1C tables, deliberately independent of the new schema code.
CREATE TABLE job_postings (
    posting_id TEXT PRIMARY KEY, source TEXT NOT NULL, company TEXT, title TEXT,
    description TEXT, region TEXT, career TEXT, education TEXT, salary_type TEXT,
    salary TEXT, job_code TEXT, registered_at TEXT, closing_at TEXT, url TEXT,
    created_at TEXT NOT NULL
);
CREATE TABLE posting_skills (
    posting_id TEXT NOT NULL, skill TEXT NOT NULL, PRIMARY KEY (posting_id, skill)
);
