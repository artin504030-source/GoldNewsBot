import unittest
from datetime import datetime
from unittest.mock import patch

import gold_reports


def event(day, title="CPI", actual="", forecast="2.5%", impact="high"):
    return {
        "date": day,
        "datetime_utc": f"{day}T12:00:00+00:00",
        "datetime_kabul": f"{day}T16:30:00+04:30",
        "title": title,
        "currency": "USD",
        "impact": impact,
        "actual": actual,
        "forecast": forecast,
        "previous": "2.4%",
    }


class GoldReportsScheduleTests(unittest.TestCase):
    def test_current_week_is_saturday_through_friday(self):
        start, end = gold_reports.current_week_range(datetime(2026, 11, 29).date())
        self.assertEqual(str(start), "2026-11-28")
        self.assertEqual(str(end), "2026-12-04")

    def test_sunday_report_includes_saturday_to_friday_only(self):
        now = datetime(2026, 11, 29, 9, 0, tzinfo=gold_reports.KABUL)
        events = [
            event("2026-11-28", "Saturday event"),
            event("2026-12-04", "Friday event"),
            event("2026-12-05", "Next Saturday event"),
        ]
        state = {}
        with patch("gold_reports.send_long_telegram") as send:
            gold_reports.publish_scheduled_report(events, state, now, {})
        message = send.call_args.args[0]
        self.assertIn("Saturday event", message)
        self.assertIn("Friday event", message)
        self.assertNotIn("Next Saturday event", message)
        self.assertIn("2026-11-28 تا 2026-12-04", message)

    def test_month_report_marks_released_event_and_actual_result(self):
        now = datetime(2026, 11, 28, 10, 0, tzinfo=gold_reports.KABUL)
        message = gold_reports.report_message(
            [event("2026-11-27", actual="2.8%", title="Core CPI")],
            "تقویم و گزارش ماه جاری", "November 2026", now, {}, []
        )
        self.assertIn("منتشر شده", message)
        self.assertIn("نتیجه واقعی: <b>2.8%</b>", message)

    def test_month_report_marks_future_event_as_pending(self):
        now = datetime(2026, 11, 28, 10, 0, tzinfo=gold_reports.KABUL)
        message = gold_reports.report_message(
            [event("2026-11-30", title="Employment report")],
            "تقویم و گزارش ماه جاری", "November 2026", now, {}, []
        )
        self.assertIn("در انتظار انتشار", message)

    def test_silent_pin_is_persistent_and_never_unpinned(self):
        with patch.object(gold_reports, "TOKEN", "token"), \\
             patch.object(gold_reports, "CHAT_ID", "channel"), \\
             patch("gold_reports.telegram_post", side_effect=[
                 {"result": {"message_id": 123}},
                 {"result": {"message_id": 123}},
             ]) as post:
            gold_reports.send_telegram("test")
        self.assertEqual(post.call_count, 2)
        self.assertTrue(post.call_args_list[1].args[0].endswith("/pinChatMessage"))
        self.assertTrue(post.call_args_list[1].args[1]["disable_notification"])


if __name__ == "__main__":
    unittest.main()
