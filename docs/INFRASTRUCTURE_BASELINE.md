# GoldNewsBot — Infrastructure Baseline (Phase 1)

## Purpose
Establish a small, testable application boundary before integrating live feeds,
AI translation/analysis, scheduled jobs, or the production Telegram channel.

## Current structure

- `app/core/config.py`: stable configuration entry point.
- `app/platform/database.py`: persistence adapter boundary.
- `app/platform/health.py`: safe runtime checks.
- `app/main.py`: operational CLI.
- `goldnewsbot/`: domain models, pipeline contracts, Telegram adapter, formatting,
  SQLite implementation, and compatibility APIs.
- `tests/`: isolated tests; no live Telegram credentials or network calls required.

## Environment

Configuration is supplied through environment variables. Secrets belong in local
`.env` files or the CI secret store; never commit them. `.env.example` contains
only blank placeholders. Health output deliberately omits secret values and paths.

## Data and reliability

SQLite is the phase-1 local/staging store. WAL mode, a busy timeout, parameterized
queries, and a quick integrity check are enabled. The processed-news key is a
SHA-256 fingerprint derived from the canonical URL. No production database has
been migrated and no existing history files have been modified.

## Operational commands

```bash
python -m unittest discover -s tests -v
python -m compileall -q app goldnewsbot tests
python -m app.main health
# Compatibility command:
python -m goldnewsbot --health
```

## Not enabled yet

- Live news-source polling and source credentials.
- AI translation, classification, geopolitical/fundamental analysis.
- Automated publication to the live Telegram channel.
- Production scheduler / GitHub Actions wiring.
- PostgreSQL deployment, production backups, and migration of existing JSON data.

These are deliberately separate rollout stages. The scaffold must first be merged
into a development branch and exercised in staging. `main` remains untouched.
