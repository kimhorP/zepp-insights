# zepp-insights

Pull health data from your Amazfit/Zepp watch into a local SQLite database.
The dashboard and AI interpretation layers are not built yet — this is the
ETL + database stage.

## Layout

```
etl/    Zepp API client + sync (pull into SQLite)
db/     SQLite schema and connection helpers
notebooks/  pandas exploration notebooks
```

## Quick start

```bash
# 1. Credentials (one-time) — see .env.example
python -m etl login

# 2. Pull data into the database
python -m etl sync --from 2026-04-01 --to 2026-11-07   # all types
python -m etl sync --type sleep                          # one type only
python -m etl sync                                       # last 7 days

# 3. Explore in a notebook
jupyter notebook notebooks/explore.ipynb
```

The database lives at `~/.zepp-insights/zepp.db` (override with `ZEPP_INSIGHTS_DB`).

## CLI

```bash
python -m etl sync --from 2026-01-01 --to 2026-01-31
python -m etl sync --type heart-rate
python -m etl export --format csv --output data.csv
python -m etl status
```

## Data types pulled

heart-rate, sleep, steps, stress, training-load, sport-load, phn

Re-syncing is always safe — it upserts, so no duplicates.

## License

MIT. See [LICENSE](LICENSE).

---

*This project is not affiliated with Zepp Health, Huami, or Amazfit.*