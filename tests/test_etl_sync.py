"""Tests for ETL load/sync: upsert idempotency with a mocked ZeppClient."""

import pytest

from db import connect, get_data_version
from etl import load, sync


@pytest.fixture
def conn(tmp_path):
    c = connect(tmp_path / "etl.db")
    yield c
    c.close()


class MockClient:
    """Returns deterministic data for every call."""

    def get_heart_rate(self, date):
        return [{"minute": 360, "time": "06:00", "bpm": 70}]

    def get_sleep(self, date):
        return {"date": date, "sleep_score": 80, "resting_hr": 52,
                "stages": [], "nap_stages": []}

    def get_steps(self, date):
        return {"date": date, "total_steps": 1000, "distance_meters": 800,
                "calories": 50, "stages": []}

    def get_stress(self, from_date, to_date):
        return [{
            "timestamp": 1738800000000,
            "avg_stress": 30, "max_stress": 60, "min_stress": 10,
            "zone_percentages": {"relaxed": 50, "normal": 30, "medium": 15, "high": 5},
            "readings": [{"time": 1738800000000, "value": 30}],
        }]

    def get_training_load(self, from_date, to_date):
        return [{"timestamp": 1738800000000, "atl": 40.0, "ctl": 35.0, "tsb": -5.0}]

    def get_sport_load(self, from_date, to_date):
        return [{"date": "2026-02-06", "daily_load": 70, "weekly_load": 400,
                 "optimal_min": 300, "optimal_max": 600}]

    def get_phn(self, from_date, to_date):
        return [{"timestamp": 1738800000000, "trimp": 11.0, "atl": 40.0,
                 "ctl": 35.0, "tsb": -5.0}]


@pytest.fixture
def client():
    return MockClient()


class TestLoad:
    def test_heart_rate_upsert_idempotent(self, conn):
        readings = [{"minute": 360, "time": "06:00", "bpm": 70}]
        load.load_heart_rate(conn, "2026-02-06", readings)
        load.load_heart_rate(conn, "2026-02-06", readings)
        n = conn.execute("SELECT COUNT(*) FROM heart_rate").fetchone()[0]
        assert n == 1

    def test_sleep_upsert(self, conn):
        sleep = {"date": "2026-02-06", "sleep_score": 80, "stages": []}
        load.load_sleep(conn, sleep)
        load.load_sleep(conn, {**sleep, "sleep_score": 85})
        row = conn.execute("SELECT sleep_score FROM sleep").fetchone()
        assert row[0] == 85
        assert conn.execute("SELECT COUNT(*) FROM sleep").fetchone()[0] == 1

    def test_mark_sync_accumulates(self, conn):
        load.mark_sync(conn, "steps", 5)
        load.mark_sync(conn, "steps", 3)
        row = conn.execute("SELECT rows_written, last_error FROM sync_state "
                           "WHERE dtype = 'steps'").fetchone()
        assert row[0] == 8
        assert row[1] is None

    def test_mark_sync_records_error(self, conn):
        load.mark_sync(conn, "sleep", 0, error="token expired")
        row = conn.execute("SELECT last_error FROM sync_state "
                           "WHERE dtype = 'sleep'").fetchone()
        assert row[0] == "token expired"


class TestSyncRange:
    def test_sync_range_populates_tables(self, client, conn):
        results = sync.sync_range(client, conn,
                                  from_date="2026-02-06", to_date="2026-02-06")
        assert all(r["ok"] for r in results.values())
        assert conn.execute("SELECT COUNT(*) FROM heart_rate").fetchone()[0] == 1
        assert conn.execute("SELECT COUNT(*) FROM sleep").fetchone()[0] == 1
        assert conn.execute("SELECT COUNT(*) FROM steps").fetchone()[0] == 1
        assert conn.execute("SELECT COUNT(*) FROM stress_daily").fetchone()[0] == 1
        assert conn.execute("SELECT COUNT(*) FROM training_load").fetchone()[0] == 1
        assert conn.execute("SELECT COUNT(*) FROM sport_load").fetchone()[0] == 1
        assert conn.execute("SELECT COUNT(*) FROM phn").fetchone()[0] == 1

    def test_sync_range_twice_idempotent(self, client, conn):
        sync.sync_range(client, conn, from_date="2026-02-06", to_date="2026-02-06")
        counts_before = _all_counts(conn)
        sync.sync_range(client, conn, from_date="2026-02-06", to_date="2026-02-06")
        assert _all_counts(conn) == counts_before

    def test_sync_bumps_data_version(self, client, conn):
        assert get_data_version(conn) == 0
        sync.sync_range(client, conn, from_date="2026-02-06", to_date="2026-02-06")
        assert get_data_version(conn) == 1

    def test_partial_failure_keeps_other_dtypes(self, client, conn):
        class FailingSleep(MockClient):
            def get_sleep(self, date):
                raise RuntimeError("sleep API down")

        results = sync.sync_range(FailingSleep(), conn,
                                  from_date="2026-02-06", to_date="2026-02-06")
        assert results["sleep"]["ok"] is False
        assert results["heart-rate"]["ok"] is True
        assert conn.execute("SELECT COUNT(*) FROM heart_rate").fetchone()[0] == 1
        row = conn.execute("SELECT last_error FROM sync_state "
                           "WHERE dtype = 'sleep'").fetchone()
        assert "sleep API down" in row[0]
        # at least one dtype succeeded -> version bumped
        assert get_data_version(conn) == 1

    def test_all_failures_do_not_bump_version(self, conn):
        class AllFail:
            def __getattr__(self, name):
                if name.startswith("get_"):
                    def fail(*a, **k):
                        raise RuntimeError("down")
                    return fail
                raise AttributeError(name)

        results = sync.sync_range(AllFail(), conn,
                                  from_date="2026-02-06", to_date="2026-02-06")
        assert not any(r["ok"] for r in results.values())
        assert get_data_version(conn) == 0


def _all_counts(conn):
    tables = ["heart_rate", "sleep", "steps", "stress_daily", "stress_readings",
              "training_load", "sport_load", "phn"]
    return {t: conn.execute(f"SELECT COUNT(*) FROM {t}").fetchone()[0]
            for t in tables}
