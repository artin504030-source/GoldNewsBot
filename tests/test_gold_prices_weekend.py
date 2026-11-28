import unittest
from datetime import datetime
from zoneinfo import ZoneInfo

from apps.gold_prices.weekend import process_weekend_notice

NY = ZoneInfo("America/New_York")


class GoldPricesWeekendTests(unittest.TestCase):
    def test_sends_one_notice_per_new_york_day(self):
        state = {"sent": {}}
        messages = []
        saturday = datetime(2026, 11, 28, 9, 0, tzinfo=NY)
        self.assertTrue(process_weekend_notice(saturday, state, messages.append))
        self.assertFalse(process_weekend_notice(saturday, state, messages.append))
        self.assertEqual(len(messages), 1)
        self.assertIn("Gold Prices", messages[0])
        self.assertEqual(state["sent"]["weekend_closed"], "2026-11-28")

    def test_sunday_gets_a_separate_notice_before_reopen(self):
        state = {"sent": {"weekend_closed": "2026-11-28"}}
        messages = []
        sunday = datetime(2026, 11, 29, 12, 0, tzinfo=NY)
        self.assertTrue(process_weekend_notice(sunday, state, messages.append))
        self.assertEqual(len(messages), 1)
        self.assertIn("امروز ساعت 17:00", messages[0])

    def test_no_closure_notice_after_sunday_reopen(self):
        state = {"sent": {}}
        messages = []
        sunday_open = datetime(2026, 11, 29, 17, 0, tzinfo=NY)
        self.assertFalse(process_weekend_notice(sunday_open, state, messages.append))
        self.assertEqual(messages, [])


if __name__ == "__main__":
    unittest.main()
