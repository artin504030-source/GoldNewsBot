# Gold Priced-In Analyst

- Reads Telegram `channel_post` updates using its own bot token and persistent update offset.
- Processes only messages containing the exact Gold Reports headings:
  - `پیش‌تحلیل رویداد اقتصادی`
  - `نتیجه رویداد اقتصادی`
- Replies to the matching original post and attaches a Yahoo Finance COMEX gold futures chart (`GC=F`).
- Uses a conservative evidence label; price movement alone is not proof that an event was priced in.
- Requires the bot to be an administrator in the target channel so Telegram delivers channel post updates and permits replies.
- Runs every five minutes on GitHub Actions. No changes to Gold Reports or other bots.
- Yahoo Finance is a delayed public data source; GC=F is a futures proxy, not broker XAUUSD.
