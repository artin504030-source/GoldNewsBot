import sys
import types
import unittest

# gold_reports imports BeautifulSoup for calendar scraping; these unit tests exercise
# pure analysis helpers and do not need the optional parser dependency.
sys.modules.setdefault("bs4", types.SimpleNamespace(BeautifulSoup=object))
from gold_reports import analyst_bias, compare_actual_forecast, analyst_expectation_comparison


class GoldReportsAccuracyTests(unittest.TestCase):
    def test_repeated_feed_copies_from_same_domain_count_once(self):
        articles = [
            {"title": "Inflation hotter than expected", "description": "", "source": "Publisher",
             "link": "https://www.publisher.example/story-a"},
            {"title": "Inflation hotter than expected", "description": "", "source": "Publisher RSS",
             "link": "https://publisher.example/story-b"},
        ]
        bias, label = analyst_bias({"title": "CPI", "currency": "USD"}, articles)
        self.assertEqual(label, "نامشخص")
        self.assertIn("فقط 1 ناشر مستقل", bias)

    def test_two_distinct_publishers_can_form_a_limited_direction(self):
        articles = [
            {"title": "CPI hotter than expected", "description": "", "link": "https://a.example/a"},
            {"title": "Inflation remains high", "description": "", "link": "https://b.example/b"},
        ]
        _, label = analyst_bias({"title": "CPI", "currency": "USD"}, articles)
        self.assertEqual(label, "بالاتر/قوی‌تر")

    def test_google_news_rss_items_use_publisher_labels_not_shared_host(self):
        articles = [
            {"title": "CPI hotter than expected", "description": "", "source": "Reuters",
             "link": "https://news.google.com/rss/articles/one"},
            {"title": "Inflation remains high", "description": "", "source": "Bloomberg",
             "link": "https://news.google.com/rss/articles/two"},
        ]
        _, label = analyst_bias({"title": "CPI", "currency": "USD"}, articles)
        self.assertEqual(label, "بالاتر/قوی‌تر")

    def test_unemployment_lower_than_forecast_is_described_as_better(self):
        result = compare_actual_forecast("3.8%", "4.0%", "Unemployment Rate")
        self.assertIn("پایین‌تر", result)
        self.assertIn("قوی‌تر/بهتر", result)

    def test_jobless_claims_higher_than_forecast_are_described_as_worse(self):
        result = compare_actual_forecast("230K", "220K", "Initial Jobless Claims")
        self.assertIn("بالاتر", result)
        self.assertIn("ضعیف‌تر/بدتر", result)

    def test_expectation_comparison_uses_raw_higher_lower_surprise(self):
        result = analyst_expectation_comparison("پایین‌تر/ضعیف‌تر", "3.8%", "4.0%", "Unemployment Rate")
        self.assertIn("پایین‌تر/ضعیف‌تر", result)


if __name__ == "__main__":
    unittest.main()
