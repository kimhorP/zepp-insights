"""SQLite schema for zepp-insights.

Single database file shared by the ETL, analytics, and AI layers.
"""

SCHEMA = """
CREATE TABLE IF NOT EXISTS heart_rate (
    date    TEXT NOT NULL,
    minute  INTEGER NOT NULL,
    time    TEXT,
    bpm     INTEGER NOT NULL,
    PRIMARY KEY (date, minute)
);

CREATE TABLE IF NOT EXISTS sleep (
    date                 TEXT PRIMARY KEY,
    fetched_from         TEXT,
    resting_hr           INTEGER,
    sleep_score          INTEGER,
    deep_minutes         INTEGER,
    light_minutes        INTEGER,
    rem_minutes          INTEGER,
    duration_minutes     INTEGER,
    start                TEXT,
    end                  TEXT,
    stages               TEXT,
    nap_stages           TEXT,
    nap_duration_minutes INTEGER
);

CREATE TABLE IF NOT EXISTS steps (
    date                TEXT PRIMARY KEY,
    total_steps         INTEGER,
    distance_meters     INTEGER,
    calories            INTEGER,
    run_distance_meters INTEGER,
    run_calories        INTEGER,
    goal                INTEGER,
    stages              TEXT
);

CREATE TABLE IF NOT EXISTS stress_daily (
    date        TEXT PRIMARY KEY,
    avg_stress  INTEGER,
    max_stress  INTEGER,
    min_stress  INTEGER,
    relaxed_pct INTEGER,
    normal_pct  INTEGER,
    medium_pct  INTEGER,
    high_pct    INTEGER
);

CREATE TABLE IF NOT EXISTS stress_readings (
    date   TEXT NOT NULL,
    minute INTEGER NOT NULL,
    value  INTEGER NOT NULL,
    PRIMARY KEY (date, minute)
);

CREATE TABLE IF NOT EXISTS training_load (
    date               TEXT PRIMARY KEY,
    timestamp          INTEGER,
    exercise_score     INTEGER,
    total_score        INTEGER,
    target_score       INTEGER,
    completion_percent REAL,
    recovery_factor    REAL,
    atl                REAL,
    ctl                REAL,
    tsb                REAL
);

CREATE TABLE IF NOT EXISTS sport_load (
    date          TEXT PRIMARY KEY,
    daily_load    INTEGER,
    weekly_load   INTEGER,
    optimal_min   INTEGER,
    optimal_max   INTEGER,
    overreaching  INTEGER
);

CREATE TABLE IF NOT EXISTS phn (
    date      TEXT PRIMARY KEY,
    timestamp INTEGER,
    trimp     REAL,
    atl       REAL,
    ctl       REAL,
    tsb       REAL
);

CREATE TABLE IF NOT EXISTS sync_state (
    dtype        TEXT PRIMARY KEY,
    last_sync_at TEXT,
    last_error   TEXT,
    rows_written INTEGER NOT NULL DEFAULT 0
);

CREATE TABLE IF NOT EXISTS meta (
    key   TEXT PRIMARY KEY,
    value TEXT
);

CREATE TABLE IF NOT EXISTS insights (
    kind         TEXT NOT NULL,
    period       TEXT NOT NULL,
    content      TEXT NOT NULL,
    model        TEXT,
    data_version INTEGER,
    generated_at TEXT,
    PRIMARY KEY (kind, period)
);

CREATE TABLE IF NOT EXISTS chat_messages (
    id         INTEGER PRIMARY KEY AUTOINCREMENT,
    role       TEXT NOT NULL,
    content    TEXT NOT NULL,
    created_at TEXT
);
"""
