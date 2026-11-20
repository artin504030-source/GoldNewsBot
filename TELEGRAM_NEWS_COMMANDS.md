# Telegram News Commands

The independent GitHub Actions workflow checks Telegram commands every 5 minutes. Commands read `news_archive.json`, reply to the requesting chat, and do not alter the existing news posting schedule.

- `/today` or `/daily`: archive news from the last 24 hours
- `/week` or `/weekly`: archive news from the last 7 days
- `/month` or `/monthly`: archive news from the last 30 days
- `/help`: command guide

Replies include up to 8 headlines newest-first, category, importance, UTC timestamp, and source link. Requires `BOT_TOKEN` in Actions secrets. GitHub scheduled runs may be delayed.
