import unittest
from unittest.mock import patch

from goldnewsbot.integration import fetch_and_classify_article


class NewsIntegrationTests(unittest.TestCase):
    @patch("goldnewsbot.integration.preview_article")
    @patch("goldnewsbot.integration.resolve_article_url")
    def test_keeps_short_partial_text_and_publisher_link(self, resolve, preview):
        resolve.return_value = "https://www.publisher.example/story"
        preview.return_value = {
            "body": "Two short paragraphs of actual publisher article text.",
            "url": "https://www.publisher.example/story",
            "categories": ["geopolitics"],
            "related_markets": ["oil", "gold"],
            "matched_terms": ["shipping"],
        }
        result = fetch_and_classify_article(
            "https://news.google.com/rss/articles/example?oc=5",
            "Tanker incident",
            "One-line RSS summary",
        )
        self.assertEqual(result["body"], preview.return_value["body"])
        self.assertFalse(result["full_article"])
        self.assertEqual(result["url"], "https://www.publisher.example/story")
        resolve.assert_called_once()
        preview.assert_called_once_with("https://www.publisher.example/story", "Tanker incident", min_chars=1)

    @patch("goldnewsbot.integration.preview_article")
    def test_uses_rss_only_when_publisher_text_is_unavailable(self, preview):
        preview.return_value = {"body": "", "url": "https://publisher.example/story"}
        result = fetch_and_classify_article(
            "https://publisher.example/story", "Tanker incident", "RSS excerpt"
        )
        self.assertEqual(result["body"], "RSS excerpt")
        self.assertFalse(result["full_article"])


if __name__ == "__main__":
    unittest.main()
