# zepp-insights Layered Architecture Design

Date: 2026-11-07
Status: Approved

## Goal

Reorganize the codebase into three clear layers — ETL (pull data into a DB), analytics (dashboard metrics), and AI (interpretation) — with a web layer on top, and make the dashboard auto-sync when new data lands.

## Decisions

- **Data flow:** SQLite is the single source of truth. ETL writes it, analytics and AI only read it, the web layer serves from it. Nothing calls the Zepp API outside `etl/`.
- **Auto-sync:** background thread inside the Flask server runs `sync_recent()` every 20 minutes; the dashboard polls a status endpoint and refreshes itself when `data_version` changes.
- **AI:** local Ollama only (`localhost:11434`). Two capabilities: cached daily/weekly insight reports, and on-demand chat over recent metrics.
- **Layout:** layer packages at the repo root. The existing `zepp_export` package is dissolved into `etl/`.

## Physical layout

```
zepp-insights/
├── etl/                    # EXTRACT from Zepp → load into SQLite
│   ├── client.py           #   ZeppClient (was zepp_export/client.py)
│   ├── decoders.py         #   binary decoders
│   ├── exceptions.py
│   ├── export.py           #   CSV / Apple Health file exports
│   ├── extract.py          #   per-dtype pullers wrapping ZeppClient
│   ├── load.py             #   SQLite upserts
│   ├── sync.py             #   sync_recent(), sync_range()
│   └── __main__.py         #   CLI: python -m etl sync / login / status / export
├── db/                     # shared infrastructure
│   ├── schema.py           #   CREATE TABLE statements, data_version
│   └── connection.py       #   single sqlite file: ~/.zepp-insights/zepp.db
├── analytics/              # pure functions: DB rows → metrics
│   ├── daily.py            #   daily summary cards
│   ├── training.py         #   ATL/CTL/TSB, TRIMP
│   ├── sleep.py
│   ├── stress.py
│   └── heart_rate.py
├── ai/
│   ├── ollama.py           #   thin HTTP client
│   ├── context.py          #   builds metric context from analytics
│   ├── report.py           #   insight reports, cached in DB
│   └── chat.py             #   on-demand Q&A
├── web/
│   ├── server.py           #   Flask app: reads only db/analytics/ai
│   ├── sync_worker.py      #   background sync thread
│   └── dashboard/          #   render-only static frontend
├── docs/
└── tests/
```

Dependency rule (arrows only point one way):

```
web → ai → analytics → db ← etl ← (Zepp API)
```

## Database schema (SQLite)

| Table | Key | Contents |
|---|---|---|
| `heart_rate` | (date, minute) | bpm readings |
| `sleep` | date | score, rhr, deep/light/rem minutes, duration, stages (JSON) |
| `steps` | date | total, distance, calories, goal |
| `stress_daily` | date | avg/max/min, zone percentages |
| `stress_readings` | (date, minute) | 5-minute stress values |
| `training_load` | date | atl, ctl, tsb, exercise_score |
| `sport_load` | date | daily/weekly load, optimal range |
| `phn` | date | trimp, atl, ctl, tsb |
| `sync_state` | dtype | last_sync_at, last_error, rows_written |
| `insights` | (kind, period) | generated report text, model, data_version |
| `chat_messages` | id | chat session history |

- All ETL writes are upserts; re-syncing a date is always safe.
- `data_version` (integer, bumped on every successful sync) drives AI report cache invalidation and dashboard refresh.

## ETL layer

- `sync_range(from, to)` — pulls each dtype via `ZeppClient`, upserts, updates `sync_state`. One transaction per dtype so a failure in one type does not roll back others.
- `sync_recent()` — re-pulls the last 7 days plus today (recent days change as the watch syncs).
- CLI: `python -m etl sync --from YYYY-MM-DD --to YYYY-MM-DD`, plus `login`, `status`, `export`.
- First run auto-backfills 90 days. The old `~/.zepp-export/data/` JSON cache is not imported; it becomes orphaned.

## Analytics layer

Pure functions over DB rows, e.g.:

- `analytics.daily.summary(conn, date) -> dict`
- `analytics.training.load_series(conn, from_date, to_date) -> list`
- `analytics.sleep.daily(conn, date)`, `analytics.stress.daily(...)`, `analytics.heart_rate.daily(...)`

TRIMP and zone math currently in `dashboard/static/*.js` moves here. The same functions feed both the REST API and AI prompts — one definition of every metric. Dashboard JS becomes render-only.

## AI layer (Ollama)

- **Reports:** after each successful sync with a changed `data_version`, regenerate today's and yesterday's daily insight (plus a weekly report on Mondays). Context comes from analytics metrics for the period. Stored in `insights`; the dashboard serves the cached text. If Ollama is down, the report endpoint returns 503, the dashboard shows "AI unavailable", and the next sync retries.
- **Chat:** `POST /api/ai/chat` sends the question plus a context block (last 14 days of analytics summaries) to Ollama with a system prompt instructing it to answer only from the provided data. History persists in `chat_messages`. No function-calling framework.

## Web layer + auto-sync

Endpoints (all DB-only):

- `GET /api/daily/<date>` — combined daily summary
- `GET /api/heart-rate/<date>`, `/api/sleep/<date>`, `/api/steps/<date>`, `/api/stress/<date>`
- `GET /api/training-load?from=&to=`, `/api/sport-load`, `/api/phn`
- `GET /api/insights/<date>` — cached AI report
- `POST /api/ai/chat`
- `GET /api/sync/status` — `data_version`, `last_sync_at`, `last_error`
- `POST /api/sync` — manual trigger

`sync_worker.py`: daemon thread, every 20 minutes runs `sync_recent()`, bumps `data_version`, records per-dtype errors in `sync_state`.

Dashboard auto-sync: polls `/api/sync/status` every 60 seconds; when `data_version` changes it reloads the current view. A banner shows sync freshness or the last error.

## Error handling

- **Auth expired:** sync stops after repeated failures; `sync_status.last_error` surfaces in the dashboard banner with a hint to run `python -m etl login`.
- **Partial sync:** per-dtype `sync_state` records which types failed; successful types keep their data.
- **Ollama down:** report endpoint returns 503; chat returns a friendly error; dashboard degrades to charts-only.

## Testing

- Analytics: pure-function unit tests against fixture SQLite databases (`tmp_path`).
- ETL: upsert idempotency tests (sync the same range twice, row counts unchanged); `extract`/`load` tested with a mocked `ZeppClient`.
- AI: mocked Ollama HTTP responses; report caching keyed by `data_version`.
- Web: Flask tests against a temp DB (replaces the current mock-client server tests).
- Existing `test_decoders.py` and `test_export.py` stay, with imports updated to `etl.*`.

## Migration / rollout

1. Create new packages; move `zepp_export` code into `etl/`.
2. Update `pyproject.toml` package discovery (`etl*`, `db*`, `analytics*`, `ai*`, `web*`), tests, examples, README.
3. Delete `zepp_export/`.
4. First `python -m etl sync` backfills 90 days into the new DB.
