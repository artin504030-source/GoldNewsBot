import sys
import tempfile
import unittest
from pathlib import Path
from unittest.mock import Mock
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from scripts.legacy_dry_run import load_feed_registry, fetch_preview

class LegacyDryRunTests(unittest.TestCase):
    def test_reads_feed_registry_without_importing_bot(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "news_bot.py"
            path.write_text('FEEDS = {"Example": "https://example.test/rss"}\nraise RuntimeError("must not execute")', encoding="utf-8")
            self.assertEqual(load_feed_registry(path), {"Example": "https://example.test/rss"})

    def test_fetches_and_limits_preview(self):
        response = Mock()
        response.content = b'<rss version="2.0"><channel><item><title>One</title><link>https://a.test/1</link></item><item><title>Two</title><link>https://a.test/2</link></item></channel></rss>'
        response.raise_for_status.return_value = None
        getter = Mock(return_value=response)
        items = fetch_preview("https://example.test/rss", limit=1, http_get=getter)
        self.assertEqual(len(items), 1)
        self.assertEqual(items[0]["title"], "One")
        getter.assert_called_once()

    def test_rejects_invalid_limit(self):
        with self.assertRaises(ValueError):
            fetch_preview("https://example.test/rss", limit=0, http_get=Mock())

if __name__ == "__main__":
    unittest.main()
