"""Tests for the isolated Gold Market foundation."""
import os
import unittest
from datetime import datetime, timezone
from decimal import Decimal
from unittest.mock import patch

from apps.gold_market.config import Settings
from apps.gold_market.indicators import INDICATOR_IDS
from apps.gold_market.models import MarketObservation


class GoldMarketFoundationTests(unittest.TestCase):
    def test_registry_contains_seven_expected_indicators(self):
        self.assertEqual(
            INDICATOR_IDS,
            ("XAUUSD", "DXY", "US10Y", "US02Y", "USOIL", "SPX", "VIX"),
        )

    def test_default_interval_is_sixty_minutes(self):
        with patch.dict(os.environ, {}, clear=True):
            self.assertEqual(Settings.from_env().report_interval_minutes, 60)

    def test_interval_rejects_non_hourly_value(self):
        with patch.dict(os.environ, {"GOLD_MARKET_INTERVAL_MINUTES": "30"}, clear=True):
            with self.assertRaises(ValueError):
                Settings.from_env()

    def test_observation_requires_timezone_aware_timestamp(self):
        with self.assertRaises(ValueError):
            MarketObservation("XAUUSD", Decimal("2000"), datetime(2026, 1, 1), "test")

    def test_observation_rejects_non_finite_value(self):
        with self.assertRaises(ValueError):
            MarketObservation("XAUUSD", Decimal("NaN"), datetime.now(timezone.utc), "test")

    def test_observation_accepts_valid_market_data(self):
        item = MarketObservation("XAUUSD", Decimal("2000.25"), datetime.now(timezone.utc), "unit-test")
        self.assertEqual(item.value, Decimal("2000.25"))
        self.assertGreaterEqual(item.age_seconds, 0)


if __name__ == "__main__":
    unittest.main()
