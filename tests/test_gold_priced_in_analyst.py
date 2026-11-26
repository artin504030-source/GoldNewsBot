import unittest
from apps.gold_priced_in_analyst.__main__ import is_target_post, extract_fields
from apps.gold_priced_in_analyst.analysis import numeric, parse_event_time, classify_pre, classify_post
from datetime import datetime, timezone, timedelta


class TargetFilterTests(unittest.TestCase):
    def test_only_exact_report_headings(self):
        self.assertEqual(is_target_post({"text": "🗓 پیش‌تحلیل رویداد اقتصادی"}), "pre")
        self.assertEqual(is_target_post({"text": "📊 نتیجه رویداد اقتصادی"}), "post")
        self.assertIsNone(is_target_post({"text": "📚 تقویم و گزارش ماه جاری"}))
        self.assertIsNone(is_target_post({"text": "🔔 اعلان سشن معاملاتی"}))
        self.assertIsNone(is_target_post({"text": "📰 خبر جدید"}))

    def test_extract_fields(self):
        fields = extract_fields("🌍 USD | US CPI\n🕘 زمان کابل: 2026-11-26 20:00\nپیش‌بینی عددی Forex Factory: 3.1%\nعدد واقعی: 3.2%")
        self.assertEqual(fields["forecast"], "3.1%")
        self.assertEqual(fields["actual"], "3.2%")

    def test_numeric(self):
        self.assertEqual(numeric("3.25%"), 3.25)
        self.assertIsNone(numeric("N/A"))

    def test_parse_kabul_time(self):
        parsed = parse_event_time("2026-11-26 20:00")
        self.assertIsNotNone(parsed)
        self.assertEqual(parsed.tzinfo, timezone.utc)

    def test_pre_requires_market_evidence(self):
        status, _ = classify_pre([], None, "3.1%", "3.0%", "CPI")
        self.assertEqual(status, "اطلاعات کافی برای تشخیص وجود ندارد")

    def test_post_requires_event_time_and_bars(self):
        message = classify_post([], None, "3.2%", "3.1%")
        self.assertIn("زمان دقیق", message)


if __name__ == "__main__":
    unittest.main()
