"""Database connection helpers."""

import os
import sqlite3
from datetime import datetime
from pathlib import Path

from .schema import SCHEMA

DEFAULT_DB_PATH = Path.home() / ".zepp-insights" / "zepp.db"


def get_db_path() -> Path:
    """Resolve the database file path. Honors ZEPP_INSIGHTS_DB."""
    env = os.getenv("ZEPP_INSIGHTS_DB")
    return Path(env) if env else DEFAULT_DB_PATH


def connect(path: Path = None) -> sqlite3.Connection:
    """Open (and initialize) the zepp-insights database."""
    db_path = Path(path) if path else get_db_path()
    db_path.parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(str(db_path))
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA journal_mode=WAL")
    conn.executescript(SCHEMA)
    return conn


def get_data_version(conn: sqlite3.Connection) -> int:
    """Current data_version (0 if never synced)."""
    row = conn.execute("SELECT value FROM meta WHERE key = 'data_version'").fetchone()
    return int(row["value"]) if row else 0


def bump_data_version(conn: sqlite3.Connection) -> int:
    """Increment data_version after a successful sync. Returns the new value."""
    current = get_data_version(conn)
    new = current + 1
    conn.execute(
        "INSERT INTO meta (key, value) VALUES ('data_version', ?) "
        "ON CONFLICT(key) DO UPDATE SET value = excluded.value",
        (str(new),),
    )
    conn.commit()
    return new
