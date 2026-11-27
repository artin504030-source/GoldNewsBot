import unittest
from unittest.mock import patch
from apps.gold_news_analyst.report import render

class PressConferenceAnalystTests(unittest.TestCase):
    @patch("apps.gold_news_analyst.report.translate_title_to_persian", return_value="نشست خبری فدرال رزرو")
    def test_report_identifies_press_conference_analysis(self, _translate):
        item = {
            "title": "Federal Reserve press conference transcript",
            "source": "Economic Press Conference",
            "content_type": "economic_press_conference_transcript",
            "published_utc": "2026-11-27T08:00:00+00:00",
            "relevance_score": 80,
            "link": "https://www.federalreserve.gov/example",
        }
        report = render(item, {"body": "The Federal Reserve discussed monetary policy. " * 20})
        self.assertIn("تحلیل متن نشست خبری اقتصادی", report)
        self.assertIn("متن منتشرشده نشست", report)

if __name__ == "__main__":
    unittest.main()
