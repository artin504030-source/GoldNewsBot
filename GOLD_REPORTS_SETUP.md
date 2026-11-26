# Gold Reports Bot (standalone)

This is a separate bot implementation. It does not import, trigger, or modify Gold News, Gold Prices, Gold Market, or Gold News Analyst.

## GitHub secrets
- `GOLD_REPORTS_BOT_TOKEN`: token from a dedicated Telegram bot created for Gold Reports.
- `CHANNEL_ID`: destination channel ID. The dedicated bot must be an administrator with permission to post and pin messages.

## Automation
- Daily at 09:00 Asia/Kabul: Saturday = current-month calendar, Sunday = upcoming-week outlook, Monday-Friday = today's events.
- Every 10 minutes: checks high-impact events, sends a pre-release scenario report within 60 minutes of release, and sends a post-release update when an actual value appears.
- Each sent message is pinned. Pin failures are logged separately; posting is not treated as pin success.

## Data and limitations
- Calendar events are read from the Forex Factory monthly calendar page (including forecast, previous and actual when present).
- Analyst material is discovered through Google News RSS queries for the event and economic forecasts. The bot preserves publisher names and article links.
- The “analyst direction” is a transparent keyword signal from article titles/descriptions, **not a formal consensus poll**. If evidence is weak or balanced, the bot says no clear direction.
- Source pages may change markup or limit automated access. A failed calendar fetch fails the run rather than fabricating data.
- Release times on Forex Factory are interpreted in Europe/London and converted to Kabul time; verify event times against the official releasing institution.

## Manual test
Run the workflow manually with `mode=daily` or `mode=monitor`.
