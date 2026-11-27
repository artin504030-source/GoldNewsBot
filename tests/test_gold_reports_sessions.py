import sys
import types
import unittest
from datetime import datetime
from unittest.mock import patch

# The session helpers do not need BeautifulSoup; keep the root test environment
# lightweight even when the standalone Gold Reports dependency set is not installed.
try:
    import bs4  # noqa: F401
except ImportError:
    stub = types.ModuleType("bs4")
    stub.BeautifulSoup = lambda *args, **kwargs: None
    sys.modules["bs4"] = stub

from gold_reports import KABUL, session_status_text, monitor_session_boundaries, SESSION_BOUNDARY_GRACE


class GoldReportsSessionTests(unittest.TestCase):
    def test_daily_schedule_lists_all_sessions_and_kabul_hours(self):
        now = datetime(2026, 11, 27, 9, 0, tzinfo=KABUL)
        message = session_status_text(now, {}, [])
        for name in ("سیدنی", "توکیو", "لندن", "نیویورک"):
            self.assertIn(f"سشن {name}", message)
        self.assertIn("کابل", message)
        self.assertIn("اکنون باز است", message)

    def test_new_york_next_session_is_not_shown_as_yesterday(self):
        now = datetime(2026, 11, 27, 9, 0, tzinfo=KABUL)
        message = session_status_text(now, {}, [])
        new_york = next(line for line in message.splitlines() if "سشن نیویورک" in line)
        self.assertIn("17:30", new_york)
        self.assertIn("02:30", new_york)

    def test_session_open_notice_recovers_if_runner_is_delayed(self):
        # Tokyo opens at 04:30 Kabul in November; this check runs 90 minutes later.
        now = datetime(2026, 11, 27, 6, 0, tzinfo=KABUL)
        state = {}
        with patch("gold_reports.send_telegram") as send:
            monitor_session_boundaries(state, now, {}, [])
        self.assertEqual(send.call_count, 1)
        self.assertIn("سشن <b>توکیو</b> باز شد", send.call_args.args[0])
        self.assertIn("JP:2026-11-27:open", state["session_notices"])
        self.assertEqual(SESSION_BOUNDARY_GRACE.total_seconds(), 7200)


if __name__ == "__main__":
    unittest.main()
