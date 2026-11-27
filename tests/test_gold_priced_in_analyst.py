import unittest
import tempfile
from pathlib import Path
from unittest.mock import patch
from apps.gold_priced_in_analyst.__main__ import is_target_post, extract_fields, is_target_chat, discard_pending_updates, process_update, verify_channel_admin
from apps.gold_priced_in_analyst.analysis import numeric, parse_event_time, classify_pre, classify_post, _change, _cross_market_lines
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

    def test_verify_channel_admin_warns_but_allows_delivery_without_pin_permission(self):
        import apps.gold_priced_in_analyst.__main__ as module
        with patch.object(module, "telegram", side_effect=[
            {"id": 123},
            {"status": "administrator", "can_pin_messages": False},
        ]), patch("builtins.print") as log:
            verify_channel_admin()
            self.assertTrue(any("lacks can_pin_messages" in str(call) for call in log.call_args_list))

    def test_pin_failure_does_not_interrupt_delivery(self):
        import apps.gold_priced_in_analyst.__main__ as module
        with (
            patch.object(module, "telegram", side_effect=RuntimeError("not enough rights")),
            patch("builtins.print") as log,
        ):
            self.assertFalse(module.pin_channel_message(321))
            self.assertTrue(any("Could not silently pin" in str(call) for call in log.call_args_list))

    def test_process_update_pins_analysis_and_chart(self):
        import apps.gold_priced_in_analyst.__main__ as module
        import tempfile
        from pathlib import Path
        from unittest.mock import Mock
        old_chat = module.CHAT_ID
        try:
            module.CHAT_ID = "-100123"
            with tempfile.TemporaryDirectory() as tmp:
                chart = Path(tmp) / "chart.png"
                chart.write_bytes(b"chart")
                photo_response = Mock()
                photo_response.status_code = 200
                photo_response.json.return_value = {
                    "ok": True, "result": {"message_id": 22}
                }
                with patch.object(module, "analyze_report", return_value=("analysis", "GC=F", None)), \
                     patch.object(module, "make_chart", return_value=(str(chart), "chart caption")), \
                     patch.object(module, "telegram", side_effect=[
                         {"message_id": 21}, True, True
                     ]) as api, \
                     patch.object(module.requests, "post", return_value=photo_response):
                    update = {"channel_post": {
                        "chat": {"id": -100123},
                        "message_id": 99,
                        "text": "پیش‌تحلیل رویداد اقتصادی",
                    }}
                    self.assertTrue(process_update(update))
                    self.assertEqual(api.call_args_list[1].args[0], "pinChatMessage")
                    self.assertEqual(api.call_args_list[1].args[1]["message_id"], 21)
                    self.assertEqual(api.call_args_list[2].args[0], "pinChatMessage")
                    self.assertEqual(api.call_args_list[2].args[1]["message_id"], 22)
        finally:
            module.CHAT_ID = old_chat

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


    def test_cross_market_change_uses_common_time_window(self):
        from datetime import datetime, timezone, timedelta
        end = datetime.now(timezone.utc)
        rows = [(end - timedelta(hours=12), 100.0), (end, 101.0)]
        self.assertAlmostEqual(_change(rows, end - timedelta(hours=12), end), 1.0)
        self.assertIn("شاخص دلار", _cross_market_lines({"DXY": rows}, end - timedelta(hours=12), end)[0])

    def test_pre_analysis_does_not_claim_cross_market_confirmation_when_missing(self):
        from datetime import datetime, timezone, timedelta
        now = datetime.now(timezone.utc)
        gold = [(now - timedelta(hours=13-i), 2000 + i * 3) for i in range(13)]
        status, evidence = classify_pre(gold, None, "3.2%", "3.0%", "US CPI", {})
        self.assertIn("تا حدی پیش‌خور", status)
        self.assertIn("داده کافی نیست", evidence)

    def test_post_requires_event_time_and_bars(self):
        message = classify_post([], None, "3.2%", "3.1%")
        self.assertIn("زمان دقیق", message)


if __name__ == "__main__":
    unittest.main()
