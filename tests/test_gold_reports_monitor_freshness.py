import unittest
from datetime import datetime, timedelta, timezone
from unittest.mock import patch
from zoneinfo import ZoneInfo

from gold_reports import monitor_events, POST_EVENT_GRACE


class GoldReportsMonitorFreshnessTests(unittest.TestCase):
    def setUp(self):
        self.now = datetime(2026, 11, 27, 16, 0, tzinfo=ZoneInfo("Asia/Kabul"))
        self.state = {"pre_sent": {}, "post_sent": {}}

    def event(self, when, actual="3.1%"):
        return {
            "date": when.date().isoformat(),
            "datetime_utc": when.astimezone(timezone.utc).isoformat(),
            "currency": "USD",
            "title": "CPI m/m",
            "impact": "high",
            "actual": actual,
            "forecast": "3.0%",
            "previous": "2.9%",
        }

    def test_historical_actual_event_older_than_grace_is_not_published(self):
        event_time = self.now.astimezone(timezone.utc) - POST_EVENT_GRACE - timedelta(minutes=1)
        with patch("gold_reports.send_telegram") as send:
            monitor_events([self.event(event_time)], self.state, self.now)
        send.assert_not_called()
        self.assertEqual(self.state["post_sent"], {})

    def test_recent_actual_event_is_published_once(self):
        event_time = self.now.astimezone(timezone.utc) - timedelta(minutes=30)
        event = self.event(event_time)
        with patch("gold_reports.event_message", return_value="post report"), patch(
            "gold_reports.send_telegram"
        ) as send:
            monitor_events([event], self.state, self.now)
            monitor_events([event], self.state, self.now)
        send.assert_called_once_with("post report")
        self.assertIn("2026-11-27|USD|CPI m/m", self.state["post_sent"])

    def test_pre_release_alert_still_works_inside_one_hour_window(self):
        event_time = self.now.astimezone(timezone.utc) + timedelta(minutes=30)
        event = self.event(event_time, actual="")
        with patch("gold_reports.event_message", return_value="pre report"), patch(
            "gold_reports.send_telegram"
        ) as send:
            monitor_events([event], self.state, self.now)
        send.assert_called_once_with("pre report")
        self.assertIn("2026-11-27|USD|CPI m/m", self.state["pre_sent"])


if __name__ == "__main__":
    unittest.main()
