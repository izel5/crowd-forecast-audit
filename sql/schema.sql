-- One row per resolved binary market.
CREATE TABLE IF NOT EXISTS markets (
    platform      TEXT,
    market_id     TEXT,
    question      TEXT,
    slug          TEXT,
    category      TEXT,
    yes_token     TEXT,       -- token whose price we track (outcome 0)
    outcome_label TEXT,       -- label of outcome 0, e.g. "Yes" or a team name
    resolved_yes  INTEGER,    -- 1 if outcome 0 won, else 0
    created_at    TIMESTAMPTZ,
    end_at        TIMESTAMPTZ,
    closed_at     TIMESTAMPTZ,
    volume        DOUBLE,
    raw           TEXT,       -- full API record, so categories can be re-derived later
    PRIMARY KEY (platform, market_id)
);

-- Price history for outcome 0 (implied probability, 0 to 1).
CREATE TABLE IF NOT EXISTS prices (
    platform  TEXT,
    market_id TEXT,
    ts        TIMESTAMPTZ,
    price     DOUBLE,
    PRIMARY KEY (platform, market_id, ts)
);

-- Tracks which markets already have price history, so fetches can resume.
CREATE TABLE IF NOT EXISTS fetch_log (
    platform   TEXT,
    market_id  TEXT,
    status     TEXT,          -- ok | empty | error
    n_points   INTEGER,
    fetched_at TIMESTAMPTZ,
    PRIMARY KEY (platform, market_id)
);
