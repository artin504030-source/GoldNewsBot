import sys
import types
import unittest
from datetime import datetime

# The session helpers do not need BeautifulSoup; keep the root test environment
# lightweight even when the standalone Gold Reports dependency set is not installed.
try:
    import bs4  # noqa: F401
except ImportError:
    stub = types.ModuleType("bs4")
    stub.BeautifulSoup = lambda *args, **kwargs: None
    sys.modules["bs4"] = stub

from gold_reports import KABUL, session_status_text


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


if __name__ == "__main__":
    unittest.main()
