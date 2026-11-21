# Stage B — Safe Integration Preflight

This patch is additive. It does not replace `news_bot.py`, modify Telegram workflows, migrate JSON state, or change production behavior.

## Why this step

The current repository already has a working legacy publisher, Telegram command handler, JSON archive/state, and scheduled GitHub Actions workflows. Importing `news_bot.py` from a new application package is unsafe because it validates Telegram credentials during module import and its `main()` path can publish messages. This preflight therefore inspects files and JSON without importing the publisher or making network calls.

## Run

From the repository root:

```bash
python scripts/foundation_preflight.py
```

To additionally require runtime secrets in the current process environment (the values are never printed):

```bash
python scripts/foundation_preflight.py --require-runtime-secrets
```

## Checks

- Expected legacy entry points and scheduled workflow exist.
- `news_archive.json` and `seen_news.json` parse as JSON lists.
- `.env` presence is reported without reading or displaying its contents.
- Runtime-secret check is optional and reports only configured/missing status.

## Next integration gates

1. Run preflight on a clean clone and record the baseline.
2. Add a dry-run adapter around the existing news processing functions after their call contracts are covered by tests.
3. Add archive/state backup and checksum before any storage migration.
4. Run Telegram delivery tests with a mock sender and a separate staging bot.
5. Keep current scheduled workflows as the production path until shadow comparison and rollback are proven.
