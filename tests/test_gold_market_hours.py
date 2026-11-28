import unittest
from datetime import datetime
from zoneinfo import ZoneInfo

from market_hours import market_is_closed, next_reopen_text, weekend_closure_message

NY = ZoneInfo("America/New_York")


class GoldMarketHoursTests(unittest.TestCase):
    def test_friday_closes_at_1700_new_york(self):
        self.assertFalse(market_is_closed(datetime(2026, 11, 27, 16, 59, tzinfo=NY)))
        self.assertTrue(market_is_closed(datetime(2026, 11, 27, 17, 0, tzinfo=NY)))

    def test_saturday_is_closed_all_day(self):
        self.assertTrue(market_is_closed(datetime(2026, 11, 28, 12, 0, tzinfo=NY)))

    def test_sunday_reopens_at_1700_new_york(self):
        before = datetime(2026, 11, 29, 16, 59, tzinfo=NY)
        opening = datetime(2026, 11, 29, 17, 0, tzinfo=NY)
        self.assertTrue(market_is_closed(before))
        self.assertFalse(market_is_closed(opening))

    def test_weekday_is_open(self):
        self.assertFalse(market_is_closed(datetime(2026, 11, 30, 9, 0, tzinfo=NY)))

    def test_closure_message_explains_reopening(self):
        saturday = datetime(2026, 11, 28, 12, 0, tzinfo=NY)
        sunday = datetime(2026, 11, 29, 12, 0, tzinfo=NY)
        self.assertIn("بازار جهانی طلا", weekend_closure_message(saturday, "Gold Market"))
        self.assertIn("یکشنبه ساعت 17:00", next_reopen_text(saturday))
        self.assertIn("امروز ساعت 17:00", next_reopen_text(sunday))

    def test_naive_datetime_is_rejected(self):
        with self.assertRaises(ValueError):
            market_is_closed(datetime(2026, 11, 28, 12, 0))


if __name__ == "__main__":
    unittest.main()
