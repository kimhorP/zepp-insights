"""Sync orchestration: pull date ranges from Zepp into SQLite."""

import time
from datetime import datetime, timedelta

from db import bump_data_version, connect

from .client import ZeppClient
from . import extract, load

ALL_DTYPES = ["heart-rate", "sleep", "steps", "stress", "training-load", "sport-load", "phn"]
RECENT_DAYS = 7
BACKFILL_DAYS = 90
DATE_FMT = "%Y-%m-%d"
_REQUEST_PAUSE = 0.1


def iter_dates(from_date: str, to_date: str):
    d = datetime.strptime(from_date, DATE_FMT)
    end = datetime.strptime(to_date, DATE_FMT)
    while d <= end:
        yield d.strftime(DATE_FMT)
        d += timedelta(days=1)


def count_days(from_date: str, to_date: str) -> int:
    d1 = datetime.strptime(from_date, DATE_FMT)
    d2 = datetime.strptime(to_date, DATE_FMT)
    return (d2 - d1).days + 1


def today() -> str:
    return datetime.now().strftime(DATE_FMT)


def _sync_per_day(client, conn, dtype, from_date, to_date, extract_fn):
    """Pull one metric once per day in the range."""
    dates = list(iter_dates(from_date, to_date))
    rows = 0
    for i, date in enumerate(dates):
        data = extract_fn(client, date)
        if dtype == "heart-rate":
            rows += load.load_heart_rate(conn, date, data or [])
        elif dtype == "sleep":
            rows += load.load_sleep(conn, data)
        elif dtype == "steps":
            rows += load.load_steps(conn, data)
        if i < len(dates) - 1:
            time.sleep(_REQUEST_PAUSE)
    return rows


def _sync_range_call(client, conn, dtype, from_date, to_date, extract_fn, load_fn):
    """Pull one metric with a single from/to API call."""
    data = extract_fn(client, from_date, to_date) or []
    return load_fn(conn, data)


def sync_range(
    client: ZeppClient,
    conn=None,
    from_date: str = None,
    to_date: str = None,
    dtypes: list = None,
) -> dict:
    """Sync the given date range. Returns {dtype: {ok, rows|error}}.

    Each dtype commits independently; a failure in one does not roll back
    the others. On any success, data_version is bumped.
    """
    own_conn = conn is None
    if own_conn:
        conn = connect()
    if not to_date:
        to_date = today()
    if not from_date:
        from_date = (datetime.strptime(to_date, DATE_FMT) - timedelta(days=RECENT_DAYS)).strftime(DATE_FMT)
    dtypes = dtypes or ALL_DTYPES

    results = {}
    try:
        for dtype in dtypes:
            try:
                with conn:  # one transaction per dtype
                    if dtype == "heart-rate":
                        rows = _sync_per_day(client, conn, dtype, from_date, to_date,
                                             extract.extract_heart_rate)
                    elif dtype == "sleep":
                        rows = _sync_per_day(client, conn, dtype, from_date, to_date,
                                             extract.extract_sleep)
                    elif dtype == "steps":
                        rows = _sync_per_day(client, conn, dtype, from_date, to_date,
                                             extract.extract_steps)
                    elif dtype == "stress":
                        rows = _sync_range_call(client, conn, dtype, from_date, to_date,
                                                extract.extract_stress, load.load_stress)
                    elif dtype == "training-load":
                        rows = _sync_range_call(client, conn, dtype, from_date, to_date,
                                                extract.extract_training_load, load.load_training_load)
                    elif dtype == "sport-load":
                        rows = _sync_range_call(client, conn, dtype, from_date, to_date,
                                                extract.extract_sport_load, load.load_sport_load)
                    elif dtype == "phn":
                        rows = _sync_range_call(client, conn, dtype, from_date, to_date,
                                                extract.extract_phn, load.load_phn)
                    else:
                        raise ValueError(f"Unknown dtype: {dtype}")
                load.mark_sync(conn, dtype, rows)
                results[dtype] = {"ok": True, "rows": rows}
            except Exception as e:  # noqa: BLE001 - per-dtype isolation by design
                try:
                    load.mark_sync(conn, dtype, 0, error=str(e))
                except Exception:
                    pass
                results[dtype] = {"ok": False, "error": str(e)}

        if any(r.get("ok") for r in results.values()):
            bump_data_version(conn)
    finally:
        if own_conn:
            conn.close()
    return results


def sync_recent(client: ZeppClient, conn=None, dtypes: list = None) -> dict:
    """Re-pull the last RECENT_DAYS days plus today (what the worker runs)."""
    to_date = today()
    from_date = (datetime.strptime(to_date, DATE_FMT) - timedelta(days=RECENT_DAYS)).strftime(DATE_FMT)
    return sync_range(client, conn, from_date=from_date, to_date=to_date, dtypes=dtypes)


def ensure_backfill(client: ZeppClient, conn) -> None:
    """First run: backfill BACKFILL_DAYS of history if the DB has no data."""
    row = conn.execute("SELECT COUNT(*) AS n FROM sync_state").fetchone()
    has_sync = row and row["n"] > 0
    if has_sync:
        return
    to_date = today()
    from_date = (datetime.strptime(to_date, DATE_FMT) - timedelta(days=BACKFILL_DAYS)).strftime(DATE_FMT)
    sync_range(client, conn, from_date=from_date, to_date=to_date)
