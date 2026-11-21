# Integration Stage E — Translation Boundary

## Added
- Added a provider-neutral NewsTranslator protocol.
- Added translate_news_item(), which translates the headline and full article body separately into Persian and returns a new immutable NewsItem.
- Added a translated_title field to NewsItem and taught the Persian formatter to use it automatically.
- Empty source text or empty provider responses fail closed with TranslationError; no fabricated translation or partial post is emitted.
- Added tests using a deterministic fake translator. No external translation service or API key is required for tests.

## Safety boundaries
- No production translation provider is configured yet.
- No network calls, Telegram sends, archive writes, or workflow changes are made by this stage.
- The translation service is not yet wired into the live pipeline. Provider selection, timeout/rate-limit policy, quality checks and shadow-mode comparison remain the next tasks.

## Test
Run: python -m unittest discover -s tests -p "test_translation.py"
