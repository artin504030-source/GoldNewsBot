# Integration Stage D — Persian Telegram News Post Format

## Added
- Added goldnewsbot/news_post.py, a pure formatter for the approved Persian news layout.
- The post includes a clear headline, full translated article body, market-impact analysis, affected instruments, source, English-formatted UTC publication date, source link, @silent0trader signature, and a non-advice disclaimer.
- Optional analysis fields (urgency, importance, tone, confidence, direct and indirect impact) are supported.
- Added unit tests for the expected layout and safe fallbacks.

## Safety boundaries
- This stage only formats data already supplied to it.
- It does not fetch RSS, translate text, invoke AI, send Telegram messages, write archives, or change existing workflows.
- The legacy news_bot.py remains untouched.
- The formatter is not wired into the production pipeline yet. Integration will happen only after translation/analysis adapters and shadow-mode tests are ready.

## Test
Run: python -m unittest tests.test_news_post
