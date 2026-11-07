"""Upsert extracted data into SQLite."""

import json
import sqlite3
from datetime import datetime


def _ms_to_date(ts_ms) -> str:
    return datetime.fromtimestamp(ts_ms / 1000).strftime("%Y-%m-%d")


def _ms_to_minute(ts_ms) -> int:
    dt = datetime.fromtimestamp(ts_ms / 1000)
    return dt.hour * 60 + dt.minute


def load_heart_rate(conn: sqlite3.Connection, date: str, readings: list) -> int:
    conn.execute("DELETE FROM heart_rate WHERE date = ?", (date,))
    rows = [(date, r["minute"], r.get("time"), r["bpm"]) for r in readings]
    conn.executemany(
        "INSERT OR REPLACE INTO heart_rate (date, minute, time, bpm) VALUES (?, ?, ?, ?)",
        rows,
    )
    return len(rows)


def load_sleep(conn: sqlite3.Connection, sleep: dict) -> int:
    if not sleep:
        return 0
    conn.execute(
        """INSERT INTO sleep (date, fetched_from, resting_hr, sleep_score,
               deep_minutes, light_minutes, rem_minutes, duration_minutes,
               start, end, stages, nap_stages, nap_duration_minutes)
           VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
           ON CONFLICT(date) DO UPDATE SET
               fetched_from=excluded.fetched_from, resting_hr=excluded.resting_hr,
               sleep_score=excluded.sleep_score, deep_minutes=excluded.deep_minutes,
               light_minutes=excluded.light_minutes, rem_minutes=excluded.rem_minutes,
               duration_minutes=excluded.duration_minutes, start=excluded.start,
               end=excluded.end, stages=excluded.stages, nap_stages=excluded.nap_stages,
               nap_duration_minutes=excluded.nap_duration_minutes""",
        (
            sleep.get("date"),
            sleep.get("fetched_from"),
            sleep.get("resting_hr"),
            sleep.get("sleep_score"),
            sleep.get("deep_minutes"),
            sleep.get("light_minutes"),
            sleep.get("rem_minutes"),
            sleep.get("duration_minutes"),
            sleep.get("start"),
            sleep.get("end"),
            json.dumps(sleep.get("stages") or []),
            json.dumps(sleep.get("nap_stages") or []),
            sleep.get("nap_duration_minutes"),
        ),
    )
    return 1


def load_steps(conn: sqlite3.Connection, steps: dict) -> int:
    if not steps:
        return 0
    conn.execute(
        """INSERT INTO steps (date, total_steps, distance_meters, calories,
               run_distance_meters, run_calories, goal, stages)
           VALUES (?, ?, ?, ?, ?, ?, ?, ?)
           ON CONFLICT(date) DO UPDATE SET
               total_steps=excluded.total_steps, distance_meters=excluded.distance_meters,
               calories=excluded.calories, run_distance_meters=excluded.run_distance_meters,
               run_calories=excluded.run_calories, goal=excluded.goal,
               stages=excluded.stages""",
        (
            steps.get("date"),
            steps.get("total_steps"),
            steps.get("distance_meters"),
            steps.get("calories"),
            steps.get("run_distance_meters"),
            steps.get("run_calories"),
            steps.get("goal"),
            json.dumps(steps.get("stages") or []),
        ),
    )
    return 1


def load_stress(conn: sqlite3.Connection, records: list) -> int:
    count = 0
    for rec in records:
        ts = rec.get("timestamp")
        if not ts:
            continue
        date = _ms_to_date(ts)
        zones = rec.get("zone_percentages") or {}
        conn.execute(
            """INSERT INTO stress_daily (date, avg_stress, max_stress, min_stress,
                   relaxed_pct, normal_pct, medium_pct, high_pct)
               VALUES (?, ?, ?, ?, ?, ?, ?, ?)
               ON CONFLICT(date) DO UPDATE SET
                   avg_stress=excluded.avg_stress, max_stress=excluded.max_stress,
                   min_stress=excluded.min_stress, relaxed_pct=excluded.relaxed_pct,
                   normal_pct=excluded.normal_pct, medium_pct=excluded.medium_pct,
                   high_pct=excluded.high_pct""",
            (
                date,
                rec.get("avg_stress"),
                rec.get("max_stress"),
                rec.get("min_stress"),
                zones.get("relaxed"),
                zones.get("normal"),
                zones.get("medium"),
                zones.get("high"),
            ),
        )
        conn.execute("DELETE FROM stress_readings WHERE date = ?", (date,))
        reading_rows = []
        for r in rec.get("readings") or []:
            rts = r.get("time")
            if not isinstance(rts, (int, float)):
                continue
            reading_rows.append((date, _ms_to_minute(rts), r.get("value")))
        conn.executemany(
            "INSERT OR REPLACE INTO stress_readings (date, minute, value) VALUES (?, ?, ?)",
            reading_rows,
        )
        count += 1
    return count


def load_training_load(conn: sqlite3.Connection, records: list) -> int:
    count = 0
    for rec in records:
        ts = rec.get("timestamp")
        if not ts:
            continue
        date = _ms_to_date(ts)
        conn.execute(
            """INSERT INTO training_load (date, timestamp, exercise_score, total_score,
                   target_score, completion_percent, recovery_factor, atl, ctl, tsb)
               VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
               ON CONFLICT(date) DO UPDATE SET
                   timestamp=excluded.timestamp, exercise_score=excluded.exercise_score,
                   total_score=excluded.total_score, target_score=excluded.target_score,
                   completion_percent=excluded.completion_percent,
                   recovery_factor=excluded.recovery_factor, atl=excluded.atl,
                   ctl=excluded.ctl, tsb=excluded.tsb""",
            (
                date,
                ts,
                rec.get("exercise_score"),
                rec.get("total_score"),
                rec.get("target_score"),
                rec.get("completion_percent"),
                rec.get("recovery_factor"),
                rec.get("atl"),
                rec.get("ctl"),
                rec.get("tsb"),
            ),
        )
        count += 1
    return count


def load_sport_load(conn: sqlite3.Connection, records: list) -> int:
    count = 0
    for rec in records:
        date = rec.get("date")
        if not date:
            continue
        conn.execute(
            """INSERT INTO sport_load (date, daily_load, weekly_load,
                   optimal_min, optimal_max, overreaching)
               VALUES (?, ?, ?, ?, ?, ?)
               ON CONFLICT(date) DO UPDATE SET
                   daily_load=excluded.daily_load, weekly_load=excluded.weekly_load,
                   optimal_min=excluded.optimal_min, optimal_max=excluded.optimal_max,
                   overreaching=excluded.overreaching""",
            (
                date,
                rec.get("daily_load"),
                rec.get("weekly_load"),
                rec.get("optimal_min"),
                rec.get("optimal_max"),
                rec.get("overreaching"),
            ),
        )
        count += 1
    return count


def load_phn(conn: sqlite3.Connection, records: list) -> int:
    count = 0
    for rec in records:
        ts = rec.get("timestamp")
        if not ts:
            continue
        date = _ms_to_date(ts)
        conn.execute(
            """INSERT INTO phn (date, timestamp, trimp, atl, ctl, tsb)
               VALUES (?, ?, ?, ?, ?, ?)
               ON CONFLICT(date) DO UPDATE SET
                   timestamp=excluded.timestamp, trimp=excluded.trimp,
                   atl=excluded.atl, ctl=excluded.ctl, tsb=excluded.tsb""",
            (
                date,
                ts,
                rec.get("trimp"),
                rec.get("atl"),
                rec.get("ctl"),
                rec.get("tsb"),
            ),
        )
        count += 1
    return count


def mark_sync(
    conn: sqlite3.Connection,
    dtype: str,
    rows: int,
    error: str = None,
) -> None:
    """Record the outcome of a sync for one data type."""
    now = datetime.now().isoformat(timespec="seconds")
    conn.execute(
        """INSERT INTO sync_state (dtype, last_sync_at, last_error, rows_written)
           VALUES (?, ?, ?, ?)
           ON CONFLICT(dtype) DO UPDATE SET
               last_sync_at=excluded.last_sync_at, last_error=excluded.last_error,
               rows_written=sync_state.rows_written + excluded.rows_written""",
        (dtype, now, error, rows),
    )
    conn.commit()
