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

    def test_week_calendar_fetches_both_months_when_week_crosses_month(self):
        november = event("2026-11-28", "November Saturday")
        december = event("2026-12-04", "December Friday")
        with patch("gold_reports.get_calendar", side_effect=[[november], [december]]) as fetch:
            events = gold_reports.get_week_calendar_events(datetime(2026, 11, 29).date())
        self.assertEqual(fetch.call_count, 2)
        self.assertEqual({item["title"] for item in events}, {"November Saturday", "December Friday"})

    def test_sunday_report_includes_upcoming_saturday_to_friday_only(self):
        now = datetime(2026, 11, 29, 9, 0, tzinfo=gold_reports.KABUL)
        events = [
            event("2026-11-28", "Current week Saturday"),
            event("2026-12-04", "Current week Friday"),
            event("2026-12-05", "Upcoming Saturday event"),
            event("2026-12-11", "Upcoming Friday event"),
            event("2026-12-12", "Following Saturday event"),
        ]
        state = {}
        with patch("gold_reports.send_long_telegram") as send:
            gold_reports.publish_scheduled_report(events, state, now, {})
        message = send.call_args.args[0]
        self.assertNotIn("Current week Saturday", message)
        self.assertNotIn("Current week Friday", message)
        self.assertIn("Upcoming Saturday event", message)
        self.assertIn("Upcoming Friday event", message)
        self.assertNotIn("Following Saturday event", message)
        self.assertIn("2026-12-05 تا 2026-12-11", message)

    def test_long_report_splitting_keeps_event_cards_together(self):
        separator = "━━━━━━━━━━━━━━━━━━━━"
        message = (
            "header\n"
            "CARD_ONE\nDETAIL_ONE\n"
            + separator
            + "\nCARD_TWO\nDETAIL_TWO\n"
            + separator
            + "\nfooter"
        )
        with patch("gold_reports.send_telegram") as send:
            gold_reports.send_long_telegram(message, limit=50)
        chunks = [call.args[0] for call in send.call_args_list]
        self.assertTrue(any("CARD_ONE" in chunk and "DETAIL_ONE" in chunk for chunk in chunks))
        self.assertTrue(any("CARD_TWO" in chunk and "DETAIL_TWO" in chunk for chunk in chunks))

    def test_report_events_are_visually_separated_and_labeled(self):
        now = datetime(2026, 11, 28, 10, 0, tzinfo=gold_reports.KABUL)
        message = gold_reports.report_message(
            [event("2026-11-27", "Core CPI", actual="2.8%"),
             event("2026-11-30", "Employment report")],
            "تقویم و گزارش ماه جاری", "November 2026", now, {}, []
        )
        self.assertIn("━━━━━━━━━━━━━━━━━━━━", message)
        self.assertIn("📅 <b>تاریخ و ساعت:</b>", message)
        self.assertIn("🌍 <b>ارز:</b>", message)
        self.assertIn("📰 <b>رویداد:</b>", message)
        self.assertIn("📢 <b>نتیجه واقعی:</b>", message)

    def test_month_report_marks_released_event_and_actual_result(self):
        now = datetime(2026, 11, 28, 10, 0, tzinfo=gold_reports.KABUL)
        message = gold_reports.report_message(
            [event("2026-11-27", actual="2.8%", title="Core CPI")],
            "تقویم و گزارش ماه جاری", "November 2026", now, {}, []
        )
        self.assertIn("منتشر شده", message)
        self.assertIn("📢 <b>نتیجه واقعی:</b> <b>2.8%</b>", message)

    def test_month_report_marks_future_event_as_pending(self):
        now = datetime(2026, 11, 28, 10, 0, tzinfo=gold_reports.KABUL)
        message = gold_reports.report_message(
            [event("2026-11-30", title="Employment report")],
            "تقویم و گزارش ماه جاری", "November 2026", now, {}, []
        )
        self.assertIn("در انتظار انتشار", message)

    def test_silent_pin_is_persistent_and_never_unpinned(self):
        with patch.object(gold_reports, "TOKEN", "token"):
            with patch.object(gold_reports, "CHAT_ID", "channel"):
                with patch("gold_reports.telegram_post", side_effect=[
                    {"result": {"message_id": 123}},
                    {"result": {"message_id": 123}},
                ]) as post:
                    gold_reports.send_telegram("test")
        self.assertEqual(post.call_count, 2)
        self.assertTrue(post.call_args_list[1].args[0].endswith("/pinChatMessage"))
        self.assertTrue(post.call_args_list[1].args[1]["disable_notification"])


if __name__ == "__main__":
    unittest.main()
