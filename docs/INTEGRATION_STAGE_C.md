# Stage C — Legacy RSS dry-run adapter

This additive adapter is the first safe connection to the existing news pipeline. It reads the existing `FEEDS` dictionary from `news_bot.py` using Python AST literal parsing, without importing or executing that module. It then fetches one explicitly selected feed and prints a small preview.

## Run

```bash
python scripts/legacy_dry_run.py --source "Geopolitical News" --limit 3
```

Use an exact source label from `FEEDS`. The tool only reads the RSS endpoint and prints title, publication time, and link. It does not send Telegram messages, call translation or AI services, change `seen_news.json` or the archive, or run scheduled jobs.

## Safety boundary

- One source per run; limit is 1–20 items.
- No import of `news_bot.py` (that module requires Telegram configuration at import time).
- No write access to production state files.
- No Telegram API calls.

## Next stage

Add classification and translation behind injected interfaces, test with recorded fixtures, and only then compare shadow output against the existing publisher. Telegram delivery remains disabled until a separate staging-bot test.
