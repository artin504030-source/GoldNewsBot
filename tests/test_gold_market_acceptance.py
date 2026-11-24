"""Offline end-to-end acceptance tests for the Gold Market pipeline."""
import unittest
from datetime import datetime, timedelta, timezone
from decimal import Decimal

from apps.gold_market.analysis import GoldBar
from apps.gold_market.collector import ALL_INDICATORS, MarketDataCollector
from apps.gold_market.models import MarketObservation
from apps.gold_market.providers import ProviderError
from apps.gold_market.telegram import render_telegram_report


def make_observation(symbol, value, now, status, source, unit="index", note=""):
    age = timedelta(days=1) if status == "DAILY" else timedelta(minutes=5)
    return MarketObservation(
        symbol, Decimal(str(value)), now - age, source, unit, status, note
    )


def make_bars(now, count=25):
    bars = []
    for index in range(count):
        close = Decimal("2600") + Decimal(index * 2)
        bars.append(
            GoldBar(
                now - timedelta(hours=count - index),
                close - Decimal("1"),
                close + Decimal("3"),
                close - Decimal("3"),
                close,
            )
        )
    return tuple(bars)


class StubProvider:
    def __init__(self, observations=None, failures=None):
        self.observations = observations or {}
        self.failures = failures or {}
        self.calls = []

    def fetch(self, indicator):
        self.calls.append(indicator)
        if indicator in self.failures:
            raise ProviderError(self.failures[indicator])
        return self.observations[indicator]


class StubHistory:
    def __init__(self, bars=None, error=None):
        self.bars = tuple(bars or ())
        self.error = error
        self.calls = 0

    def fetch_bars(self, now=None):
        self.calls += 1
        if self.error:
            raise RuntimeError(self.error)
        return self.bars


class GoldMarketAcceptanceTests(unittest.TestCase):
    def setUp(self):
        self.now = datetime.now(timezone.utc).replace(microsecond=0)
        self.current = {
            "XAUUSD": make_observation(
                "XAUUSD", "2650.25", self.now, "LIVE",
                "XAUS:spot<&>", "USD/oz", "Indicative <not executable>",
            ),
            "DXY": make_observation(
                "DXY", "100", self.now, "DELAYED", "Yahoo Finance:DX-Y.NYB"
            ),
            "US10Y": make_observation(
                "US10Y", "4.1", self.now, "DAILY", "FRED:DGS10", "percent"
            ),
            "US02Y": make_observation(
                "US02Y", "4.0", self.now, "DAILY", "FRED:DGS2", "percent"
            ),
            "USOIL": make_observation(
                "USOIL", "80", self.now, "DELAYED", "Yahoo Finance:CL=F",
                "USD/barrel", "Continuous WTI futures, not spot",
            ),
            "SPX": make_observation(
                "SPX", "6000", self.now, "DAILY", "FRED:SP500"
            ),
            "VIX": make_observation(
                "VIX", "18", self.now, "DAILY", "FRED:VIXCLS"
            ),
        }
        self.previous = {
            "DXY": make_observation(
                "DXY", "101", self.now - timedelta(days=1), "DAILY", "FRED:prior"
            ),
            "US10Y": make_observation(
                "US10Y", "4.2", self.now - timedelta(days=1), "DAILY", "FRED:prior"
            ),
            "US02Y": make_observation(
                "US02Y", "4.1", self.now - timedelta(days=1), "DAILY", "FRED:prior"
            ),
            "USOIL": make_observation(
                "USOIL", "79", self.now - timedelta(days=1), "DELAYED", "Yahoo:prior"
            ),
            "SPX": make_observation(
                "SPX", "5900", self.now - timedelta(days=1), "DAILY", "FRED:prior"
            ),
            "VIX": make_observation(
                "VIX", "17", self.now - timedelta(days=1), "DAILY", "FRED:prior"
            ),
        }

    def build_collector(self, fail_gold=False, fail_history=False):
        yahoo_symbols = ("DXY", "USOIL")
        fred_symbols = ("US10Y", "US02Y", "SPX", "VIX")
        yahoo = StubProvider({key: self.current[key] for key in yahoo_symbols})
        fred = StubProvider({key: self.current[key] for key in fred_symbols})
        xau = StubProvider(
            {"XAUUSD": self.current["XAUUSD"]},
            {"XAUUSD": "spot feed unavailable"} if fail_gold else {},
        )
        history = StubHistory(
            make_bars(self.now), "history feed unavailable" if fail_history else None
        )
        return MarketDataCollector(fred, yahoo, xau, history), fred, yahoo, xau, history

    def test_full_pipeline_collection_analysis_persian_report_and_telegram(self):
        collector, fred, yahoo, xau, history = self.build_collector()
        assessment, observations, results = collector.collect_report_snapshot(
            previous_observations=self.previous,
            upcoming_events=("US CPI at 13:30 UTC",),
            now=self.now,
        )
        messages = render_telegram_report(
            assessment, observations, generated_at=self.now
        )
        joined = "\n".join(messages)

        self.assertEqual(tuple(results), ALL_INDICATORS)
        self.assertEqual(set(observations), set(ALL_INDICATORS))
        self.assertEqual(len(observations), 7)
        self.assertEqual(assessment.trend, "BULLISH")
        self.assertEqual(assessment.confidence, "HIGH")
        self.assertEqual(assessment.drivers["DXY"], "SUPPORTIVE_FOR_GOLD")
        self.assertEqual(assessment.event_risk, ("US CPI at 13:30 UTC",))
        self.assertEqual(history.calls, 1)
        self.assertCountEqual(xau.calls, ["XAUUSD"])
        self.assertCountEqual(yahoo.calls, ["DXY", "USOIL"])
        self.assertCountEqual(fred.calls, ["US10Y", "US02Y", "SPX", "VIX"])

        self.assertIn("<b>🟡 گزارش وضعیت بازار طلا</b>", joined)
        self.assertIn("جهت روند: صعودی", joined)
        self.assertIn("قیمت اسپات", joined)
        self.assertIn("وضعیت: زنده", joined)
        self.assertIn("وضعیت: با تأخیر", joined)
        self.assertIn("وضعیت: روزانه", joined)
        self.assertIn("XAUS:spot&lt;&amp;&gt;", joined)
        self.assertIn("Indicative &lt;not executable&gt;", joined)
        self.assertIn("قرارداد آتی پیوسته WTI", joined)
        self.assertIn("US CPI at 13:30 UTC", joined)
        self.assertIn("سیگنال قطعی خرید یا فروش", joined)
        self.assertNotIn("XAUS:spot<&>", joined)
        self.assertTrue(all(len(message) <= 3900 for message in messages))

    def test_partial_provider_and_history_failures_remain_explicit(self):
        collector, _, _, _, history = self.build_collector(
            fail_gold=True, fail_history=True
        )
        assessment, observations, results = collector.collect_report_snapshot(
            previous_observations=self.previous, now=self.now
        )
        messages = render_telegram_report(
            assessment, observations, generated_at=self.now
        )
        joined = "\n".join(messages)

        self.assertIsNone(results["XAUUSD"].observation)
        self.assertNotIn("XAUUSD", observations)
        self.assertEqual(assessment.trend, "UNAVAILABLE")
        self.assertEqual(history.calls, 1)
        self.assertTrue(any("spot feed unavailable" in w for w in assessment.data_warnings))
        self.assertTrue(any("history unavailable" in w for w in assessment.data_warnings))
        self.assertIn("قابل ارزیابی نیست", joined)
        self.assertIn("در دسترس نیست", joined)
        self.assertIn("spot feed unavailable", joined)
        self.assertIn("history unavailable", joined)
        self.assertIn("سیگنال قطعی خرید یا فروش", joined)

    def test_single_snapshot_is_reused_for_report_without_second_collection(self):
        collector, fred, yahoo, xau, history = self.build_collector()
        assessment, observations, results = collector.collect_report_snapshot(
            previous_observations=self.previous, now=self.now
        )
        first_messages = render_telegram_report(assessment, observations, self.now)
        second_messages = render_telegram_report(assessment, observations, self.now)

        self.assertEqual(first_messages, second_messages)
        self.assertEqual(len(xau.calls), 1)
        self.assertEqual(len(yahoo.calls), 2)
        self.assertEqual(len(fred.calls), 4)
        self.assertEqual(history.calls, 1)


if __name__ == "__main__":
    unittest.main()
