CREATE TABLE IF NOT EXISTS cases (
    id TEXT PRIMARY KEY,
    created_at TEXT NOT NULL,
    status TEXT NOT NULL CHECK (status IN ('open', 'ran', 'bound', 'closed'))
);

CREATE TABLE IF NOT EXISTS documents (
    id TEXT PRIMARY KEY,
    case_id TEXT NOT NULL REFERENCES cases(id),
    name TEXT NOT NULL,
    body_text TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS runs (
    id TEXT PRIMARY KEY,
    case_id TEXT NOT NULL REFERENCES cases(id),
    prompt_version TEXT NOT NULL,
    model TEXT NOT NULL,
    status TEXT NOT NULL CHECK (status IN ('completed', 'budget_exhausted', 'failed')),
    started_at TEXT NOT NULL,
    finished_at TEXT
);

CREATE TABLE IF NOT EXISTS steps (
    id INTEGER PRIMARY KEY,
    run_id TEXT NOT NULL REFERENCES runs(id),
    position INTEGER NOT NULL,
    kind TEXT NOT NULL CHECK (kind IN ('model', 'tool')),
    name TEXT NOT NULL,
    request_json TEXT NOT NULL,
    response_json TEXT NOT NULL,
    latency_ms INTEGER NOT NULL
);

CREATE TABLE IF NOT EXISTS facts (
    id TEXT PRIMARY KEY,
    case_id TEXT NOT NULL REFERENCES cases(id),
    run_id TEXT NOT NULL REFERENCES runs(id),
    name TEXT NOT NULL,
    value TEXT NOT NULL,
    document_id TEXT NOT NULL REFERENCES documents(id),
    quote TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS memos (
    id TEXT PRIMARY KEY,
    case_id TEXT NOT NULL REFERENCES cases(id),
    run_id TEXT NOT NULL REFERENCES runs(id),
    recommendation TEXT NOT NULL,
    reasons_json TEXT NOT NULL,
    missing_json TEXT NOT NULL,
    conflicts_json TEXT NOT NULL,
    carrier TEXT,
    premium REAL,
    created_at TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS policies (
    id TEXT PRIMARY KEY,
    case_id TEXT NOT NULL REFERENCES cases(id),
    insured_name TEXT NOT NULL,
    effective_on TEXT NOT NULL,
    expires_on TEXT NOT NULL,
    premium REAL NOT NULL,
    carrier TEXT NOT NULL,
    bound_at TEXT NOT NULL
);
