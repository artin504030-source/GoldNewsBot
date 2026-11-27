import unittest
from unittest.mock import patch
from apps.gold_news_analyst import __main__ as analyst

class ArchivedPressConferenceFallbackTests(unittest.TestCase):
    def item(self):
        return {
            "content_type": "economic_press_conference_transcript",
            "link": "https://www.centralbank.example/press-conference",
            "summary": "The central bank discussed monetary policy and the economic outlook. " * 10,
        }

    @patch("goldnewsbot.safe_fetch.fetch_public_page", side_effect=RuntimeError("publisher unavailable"))
    def test_uses_archived_transcript_when_publisher_fetch_fails(self, _fetch):
        item = self.item()
        result = analyst.fetch_article(item, enabled=True)
        self.assertEqual(result["status"], "archived_transcript_fallback")
        self.assertEqual(result["body"], item["summary"][:24000])
        self.assertIn("آرشیو", result["error"])

    @patch("goldnewsbot.pipeline_preview.extract_text", return_value="too short")
    @patch("goldnewsbot.safe_fetch.fetch_public_page", return_value=("<html></html>", "https://www.centralbank.example/press-conference"))
    def test_uses_archived_transcript_when_page_has_no_substantial_text(self, _fetch, _extract):
        item = self.item()
        result = analyst.fetch_article(item, enabled=True)
        self.assertEqual(result["status"], "archived_transcript_fallback")
        self.assertEqual(result["body"], item["summary"][:24000])

if __name__ == "__main__":
    unittest.main()
