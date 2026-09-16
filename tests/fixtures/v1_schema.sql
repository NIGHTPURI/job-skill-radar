-- Fixed Phase 2D schema; independent of the current migration implementation.
CREATE TABLE job_postings (
    source TEXT NOT NULL CHECK(length(trim(source, char(9)||char(10)||char(13)||' ')) > 0),
    posting_id TEXT NOT NULL CHECK(length(trim(posting_id, char(9)||char(10)||char(13)||' ')) > 0),
    company TEXT, title TEXT, description TEXT, region TEXT, career TEXT,
    education TEXT, salary_type TEXT, salary TEXT, job_code TEXT,
    registered_at TEXT, closing_at TEXT, url TEXT,
    created_at TEXT NOT NULL,
    PRIMARY KEY (source, posting_id)
);
CREATE TABLE posting_skills (
    source TEXT NOT NULL,
    posting_id TEXT NOT NULL,
    skill TEXT NOT NULL,
    PRIMARY KEY (source, posting_id, skill),
    FOREIGN KEY (source, posting_id)
        REFERENCES job_postings(source, posting_id) ON DELETE CASCADE
);
PRAGMA user_version = 1;
