BEGIN TRANSACTION;
CREATE TABLE job_postings (
    source TEXT NOT NULL CHECK(length(trim(source, char(9)||char(10)||char(13)||' ')) > 0),
    posting_id TEXT NOT NULL CHECK(length(trim(posting_id, char(9)||char(10)||char(13)||' ')) > 0),
    company TEXT, title TEXT, description TEXT, region TEXT, career TEXT,
    education TEXT, salary_type TEXT, salary TEXT, job_code TEXT,
    registered_at TEXT, closing_at TEXT, url TEXT,
    created_at TEXT NOT NULL,
    PRIMARY KEY (source, posting_id)
);
CREATE TABLE posting_details (
            source TEXT NOT NULL,
            posting_id TEXT NOT NULL,
            job_content TEXT, employment_type TEXT, raw_career_condition TEXT,
            education TEXT, foreign_language TEXT, major TEXT, certificate TEXT,
            computer_skill TEXT, preferred_conditions TEXT, other_preferred_conditions TEXT,
            selection_method TEXT, receipt_method TEXT, submit_documents TEXT,
            other_information TEXT, work_region TEXT, work_hours TEXT, welfare TEXT,
            salary_condition TEXT, closing_at TEXT, detail_url TEXT,
            keywords TEXT NOT NULL,
            fetched_at TEXT NOT NULL CHECK(length(trim(fetched_at)) > 0),
            PRIMARY KEY (source, posting_id),
            FOREIGN KEY (source, posting_id)
                REFERENCES job_postings(source, posting_id) ON DELETE CASCADE
        );
CREATE TABLE posting_skills (
    source TEXT NOT NULL,
    posting_id TEXT NOT NULL,
    skill TEXT NOT NULL,
    PRIMARY KEY (source, posting_id, skill),
    FOREIGN KEY (source, posting_id)
        REFERENCES job_postings(source, posting_id) ON DELETE CASCADE
);
COMMIT;
PRAGMA user_version = 2;

CREATE TABLE user_profile (
    singleton INTEGER PRIMARY KEY CHECK(singleton = 1),
    revision INTEGER NOT NULL CHECK(revision >= 1),
    owned_skills TEXT NOT NULL, target_roles TEXT NOT NULL,
    preferred_regions TEXT NOT NULL, required_regions TEXT NOT NULL
);
PRAGMA user_version = 3;
