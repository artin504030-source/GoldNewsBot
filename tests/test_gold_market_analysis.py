import unittest
from datetime import datetime, timedelta, timezone
from decimal import Decimal

from apps.gold_market.analysis import GoldBar, analyze_market
from apps.gold_market.models import MarketObservation


NOW = datetime(2026, 11, 24, 15, 0, tzinfo=timezone.utc)


def observation(symbol, value, status="LIVE", age_hours=0):
    return MarketObservation(
        symbol, Decimal(str(value)), NOW - timedelta(hours=age_hours),
        "test-source", "unit", status, ""
    )


def rising_bars(count=25, last_age_hours=1):
    bars = []
    for index in range(count):
        close = Decimal("2600") + Decimal(index * 2)
        bars.append(GoldBar(
            NOW - timedelta(hours=count-index-1 + last_age_hours),
            close - Decimal("1"), close + Decimal("2"),
            close - Decimal("2"), close
        ))
    return bars


class GoldMarketAnalysisTests(unittest.TestCase):
    def test_bullish_structure_and_levels(self):
        report = analyze_market(
            {"XAUUSD": observation("XAUUSD", 2650)},
            rising_bars()
        )
        self.assertEqual(report.trend, "BULLISH")
        self.assertEqual(report.regime, "BULLISH")
        self.assertIsNotNone(report.support)
        self.assertIsNotNone(report.resistance)

    def test_insufficient_bars_never_invents_trend_or_levels(self):
        report = analyze_market(
            {"XAUUSD": observation("XAUUSD", 2650)},
            rising_bars(10)
        )
        self.assertEqual(report.trend, "UNAVAILABLE")
        self.assertIsNone(report.support)
        self.assertIsNone(report.resistance)
        self.assertEqual(report.confidence, "LOW")

    def test_stale_gold_is_not_treated_as_usable(self):
        report = analyze_market(
            {"XAUUSD": observation("XAUUSD", 2650, "STALE")},
            rising_bars()
        )
        self.assertIn("XAUUSD", " ".join(report.data_warnings))
        self.assertEqual(report.confidence, "LOW")

    def test_old_candle_history_is_not_classified(self):
        report = analyze_market(
            {"XAUUSD": observation("XAUUSD", 2650)},
            rising_bars(last_age_hours=8)
        )
        self.assertEqual(report.trend, "UNAVAILABLE")
        self.assertIsNone(report.support)

    def test_future_candle_history_is_not_classified(self):
        report = analyze_market(
            {"XAUUSD": observation("XAUUSD", 2650)},
            rising_bars(last_age_hours=-2)
        )
        self.assertEqual(report.trend, "UNAVAILABLE")

    def test_dollar_and_yields_context_are_not_causal_claims(self):
        current = {
            "XAUUSD": observation("XAUUSD", 2650),
            "DXY": observation("DXY", 100),
            "US10Y": observation("US10Y", 4.0),
        }
        previous = {
            "DXY": observation("DXY", 101),
            "US10Y": observation("US10Y", 4.1),
        }
        report = analyze_market(current, rising_bars(), previous)
        self.assertEqual(report.drivers["DXY"], "SUPPORTIVE_FOR_GOLD")
        self.assertEqual(report.drivers["US10Y"], "SUPPORTIVE_FOR_GOLD")

    def test_unknown_previous_driver_stays_unknown(self):
        report = analyze_market(
            {"XAUUSD": observation("XAUUSD", 2650), "VIX": observation("VIX", 20)},
            rising_bars()
        )
        self.assertEqual(report.drivers["VIX"], "UNKNOWN")

    def test_events_are_preserved_as_context(self):
        report = analyze_market(
            {"XAUUSD": observation("XAUUSD", 2650)},
            rising_bars(),
            upcoming_events=("US CPI release",)
        )
        self.assertEqual(report.event_risk, ("US CPI release",))

    def test_empty_observations_have_no_as_of_timestamp(self):
        report = analyze_market({}, rising_bars())
        self.assertIsNone(report.as_of)
        self.assertEqual(report.confidence, "LOW")

    def test_naive_timestamp_is_rejected(self):
        with self.assertRaises(ValueError):
            GoldBar(NOW.replace(tzinfo=None), *(Decimal("1"),) * 4)

    def test_inconsistent_bar_is_rejected(self):
        with self.assertRaises(ValueError):
            GoldBar(NOW, Decimal("10"), Decimal("9"), Decimal("8"), Decimal("10"))


if __name__ == "__main__":
    unittest.main()
