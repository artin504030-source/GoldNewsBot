import unittest
from datetime import datetime, timedelta, timezone
from decimal import Decimal

from apps.gold_market.models import MarketObservation
from apps.gold_market.validation import validate_observation


class MarketObservationValidationTests(unittest.TestCase):
    def setUp(self):
        self.now = datetime(2026, 11, 24, 15, 0, tzinfo=timezone.utc)

    def observation(self, *, indicator="XAUUSD", value="2650", age_hours=1, status="DELAYED"):
        return MarketObservation(
            indicator=indicator,
            value=Decimal(value),
            observed_at=self.now - timedelta(hours=age_hours),
            source="test",
            unit="USD" if indicator in ("XAUUSD", "USOIL") else "index",
            status=status,
        )

    def test_recent_delayed_quote_remains_delayed(self):
        result = validate_observation(self.observation(), self.now)
        self.assertEqual(result.status, "DELAYED")

    def test_old_delayed_quote_becomes_stale(self):
        result = validate_observation(self.observation(age_hours=7), self.now)
        self.assertEqual(result.status, "STALE")
        self.assertIn("freshness", result.note)

    def test_recent_daily_observation_remains_daily(self):
        item = self.observation(indicator="SPX", value="5900", age_hours=96, status="DAILY")
        self.assertEqual(validate_observation(item, self.now).status, "DAILY")

    def test_old_daily_observation_becomes_stale(self):
        item = self.observation(indicator="SPX", value="5900", age_hours=144, status="DAILY")
        self.assertEqual(validate_observation(item, self.now).status, "STALE")

    def test_impossible_price_is_rejected(self):
        with self.assertRaises(ValueError):
            validate_observation(self.observation(value="999999"), self.now)

    def test_timestamp_too_far_in_future_is_rejected(self):
        item = self.observation()
        future = self.now + timedelta(minutes=6)
        item = MarketObservation(item.indicator, item.value, future, item.source, item.unit, item.status, item.note)
        with self.assertRaises(ValueError):
            validate_observation(item, self.now)

    def test_naive_now_is_rejected(self):
        with self.assertRaises(ValueError):
            validate_observation(self.observation(), datetime(2026, 11, 24, 15, 0))


if __name__ == "__main__":
    unittest.main()
