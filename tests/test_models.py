import unittest
from goldnewsbot.models import NewsItem

class NewsItemTests(unittest.TestCase):
    def test_stable_fingerprint_for_same_url(self):
        first = NewsItem("Title A", "https://example.com/a", "Example")
        second = NewsItem("Title B", "https://example.com/a", "Example")
        self.assertEqual(first.fingerprint, second.fingerprint)

    def test_rejects_invalid_url(self):
        with self.assertRaises(ValueError):
            NewsItem("Title", "javascript:alert(1)", "Example")

if __name__ == "__main__":
    unittest.main()
