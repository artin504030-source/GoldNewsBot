import unittest
import tempfile
from pathlib import Path
from unittest.mock import patch
from apps.gold_priced_in_analyst.__main__ import is_target_post, extract_fields, is_target_chat, discard_pending_updates
from apps.gold_priced_in_analyst.analysis import numeric, parse_event_time, classify_pre, classify_post
from datetime import datetime, timezone, timedelta


class TargetFilterTests(unittest.TestCase):
    def test_only_exact_report_headings(self):
        self.assertEqual(is_target_post({"text": "🗓 پیش‌تحلیل رویداد اقتصادی"}), "pre")
        self.assertEqual(is_target_post({"text": "📊 نتیجه رویداد اقتصادی"}), "post")
        self.assertIsNone(is_target_post({"text": "📚 تقویم و گزارش ماه جاری"}))
        self.assertIsNone(is_target_post({"text": "🔔 اعلان سشن معاملاتی"}))
        self.assertIsNone(is_target_post({"text": "📰 خبر جدید"}))

    def test_target_chat_accepts_numeric_id(self):
        import apps.gold_priced_in_analyst.__main__ as module
        old = module.CHAT_ID
        try:
            module.CHAT_ID = "-100123"
            self.assertTrue(is_target_chat({"id": -100123}))
            self.assertFalse(is_target_chat({"id": -100456}))
        finally:
            module.CHAT_ID = old

    def test_target_chat_accepts_username(self):
        import apps.gold_priced_in_analyst.__main__ as module
        old = module.CHAT_ID
        try:
            module.CHAT_ID = "@gold_channel"
            self.assertTrue(is_target_chat({"id": -100123, "username": "gold_channel"}))
        finally:
            module.CHAT_ID = old

    def test_discard_pending_updates_advances_offset_without_processing(self):
        import apps.gold_priced_in_analyst.__main__ as module
        old_path = module.STATE_PATH
        with tempfile.TemporaryDirectory() as tmp:
            try:
                module.STATE_PATH = Path(tmp) / "state.json"
                state = {"offset": 100, "processed": []}
                with patch.object(module, "telegram", return_value=[{"update_id": 101}, {"update_id": 102}]) as api:
                    self.assertEqual(discard_pending_updates(state), 2)
                    api.assert_called_once()
                self.assertEqual(state["offset"], 103)
                self.assertTrue(module.STATE_PATH.exists())
            finally:
                module.STATE_PATH = old_path

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
