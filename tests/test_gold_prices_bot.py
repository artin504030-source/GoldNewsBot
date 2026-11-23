import unittest
from datetime import datetime, timezone
from zoneinfo import ZoneInfo

from apps.gold_prices.bot import (
    event_due, quote_from_xaus, quote_from_backup, quote_from_biquote,
    pct_change, gap_lines, process, prices_message, SYMBOLS
)

UTC = timezone.utc


class GoldPricesTests(unittest.TestCase):
    def test_xaus_rejects_stale_or_unavailable(self):
        now = datetime(2026, 11, 23, 5, 0, tzinfo=UTC)
        stale = {"spot_usd_oz": 4000, "updated_at": "2026-11-23T04:00:00Z",
                 "data_state": {"status": "stale"}}
        self.assertIsNone(quote_from_xaus(stale, now))

    def test_xaus_accepts_fresh_price(self):
        now = datetime(2026, 11, 23, 5, 0, tzinfo=UTC)
        data = {"spot_usd_oz": 4000, "updated_at": "2026-11-23T04:59:30Z",
                "data_state": {"status": "fresh"}}
        self.assertEqual(quote_from_xaus(data, now)["price"], 4000)

    def test_backup_timestamp_validation(self):
        now = datetime(2026, 11, 23, 5, 0, tzinfo=UTC)
        data = {"price": 4010, "updatedAt": "2026-11-23T04:59:00Z"}
        self.assertEqual(quote_from_backup(data, now)["source"], "Gold-API (backup)")

    def test_biquote_accepts_fresh_live_quote(self):
        now = datetime(2026, 11, 23, 5, 0, tzinfo=UTC)
        data = {"symbol": "EURUSD", "mid": 1.1, "timestamp": "2026-11-23T04:59:59Z",
                "stale": False, "marketState": "open", "quoteAgeSeconds": 1, "source": "test"}
        self.assertEqual(quote_from_biquote("EURUSD", data, now)["price"], 1.1)

    def test_biquote_rejects_stale_or_closed_quote(self):
        now = datetime(2026, 11, 23, 5, 0, tzinfo=UTC)
        stale = {"symbol": "US30", "mid": 49000, "timestamp": "2026-11-23T04:59:59Z",
                 "stale": True, "marketState": "open", "quoteAgeSeconds": 1}
        closed = dict(stale, stale=False, marketState="closed")
        self.assertIsNone(quote_from_biquote("US30", stale, now))
        self.assertIsNone(quote_from_biquote("US30", closed, now))

    def test_symbol_catalog_contains_all_requested_groups(self):
        self.assertEqual(len(SYMBOLS), 16)
        self.assertIn("USTEC", SYMBOLS)
        self.assertIn("USOIL", SYMBOLS)
        self.assertIn("XNGUSD", SYMBOLS)

    def test_prices_message_marks_missing_symbols(self):
        now = datetime(2026, 11, 23, 5, 0, tzinfo=UTC)
        quote = {"price": 4000, "timestamp": now, "source": "test", "age": 0}
        message = prices_message({"XAUUSD": quote}, {"samples": []}, now)
        self.assertIn("طلا", message)
        self.assertIn("قیمت تازه/باز در دسترس نیست", message)
        self.assertIn("NAS100", message)

    def test_percent_and_gap(self):
        self.assertAlmostEqual(pct_change(110, 100), 10)
        self.assertIn("$10.00", " ".join(gap_lines(110, 100)))

    def test_new_york_close_window(self):
        # 17:15 New York on Nov 23, 2026 is within the close window.
        now = datetime(2026, 11, 23, 22, 15, tzinfo=UTC)
        self.assertEqual(event_due(now, ZoneInfo("America/New_York"), 17), "2026-11-23")

    def test_event_outside_window(self):
        now = datetime(2026, 11, 23, 23, 0, tzinfo=UTC)
        self.assertIsNone(event_due(now, ZoneInfo("America/New_York"), 17))

    def test_process_sends_price_only_once_per_slot(self):
        now = datetime(2026, 11, 23, 12, 7, tzinfo=UTC)
        quote = {"price": 4000.0, "timestamp": now, "source": "test", "age": 0}
        messages = []
        state = {"samples": [], "daily_open": {}, "last_daily_close": None,
                 "last_weekly_close": None, "sent": {}, "last_price_slot": ""}
        multi = lambda _: {"XAUUSD": quote}
        process(now, state, sender=messages.append, quote_fetcher=lambda _: quote,
                multi_quote_fetcher=multi)
        first_count = len(messages)
        process(now, state, sender=messages.append, quote_fetcher=lambda _: quote,
                multi_quote_fetcher=multi)
        self.assertEqual(first_count, 1)
        self.assertEqual(len(messages), 1)


if __name__ == "__main__":
    unittest.main()
