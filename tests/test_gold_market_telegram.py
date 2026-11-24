import unittest
from datetime import datetime, timezone
from decimal import Decimal

from apps.gold_market.analysis import MarketAssessment
from apps.gold_market.models import MarketObservation
from apps.gold_market.telegram import render_telegram_report, split_telegram_html

NOW = datetime(2026, 11, 24, 15, 30, tzinfo=timezone.utc)


def sample_assessment(**overrides):
    values = dict(
        as_of=NOW, regime="TREND", trend="BULLISH", volatility="NORMAL",
        support=Decimal("2600"), resistance=Decimal("2700"),
        atr_percent=Decimal("0.45"),
        drivers={"DXY": "HEADWIND_FOR_GOLD", "US10Y": "SUPPORTIVE_FOR_GOLD",
                 "US02Y": "UNKNOWN", "USOIL": "INFLATION_CONTEXT_UP",
                 "SPX": "RISK_APPETITE_UP", "VIX": "RISK_AVERSION_HIGHER"},
        main_scenario="سناریوی اصلی <آزمایشی>",
        alternative_scenario="سناریوی جایگزین",
        confidence="MEDIUM", event_risk=("رویداد <مهم>",), data_warnings=(),
    )
    values.update(overrides)
    return MarketAssessment(**values)


class GoldMarketTelegramFormatterTests(unittest.TestCase):
    def test_report_is_html_formatted_and_dynamic_text_is_escaped(self):
        obs = MarketObservation(
            "XAUUSD", Decimal("2650.25"), NOW, "XAUS:<spot>",
            "USD/oz", "LIVE", "quote <indicative>",
        )
        messages = render_telegram_report(sample_assessment(), {"XAUUSD": obs}, NOW)
        joined = "\n".join(messages)
        self.assertIn("<b>🟡 گزارش وضعیت بازار طلا</b>", joined)
        self.assertIn("XAUS:&lt;spot&gt;", joined)
        self.assertIn("quote &lt;indicative&gt;", joined)
        self.assertIn("سناریوی اصلی &lt;آزمایشی&gt;", joined)
        self.assertNotIn("سناریوی اصلی <آزمایشی>", joined)

    def test_long_report_is_split_under_configured_limit(self):
        assessment = sample_assessment(
            event_risk=tuple(f"رویداد شماره {i}: " + ("جزئیات " * 30) for i in range(80)),
            data_warnings=("هشدار " * 200,),
        )
        messages = render_telegram_report(assessment, generated_at=NOW, max_length=1000)
        self.assertGreater(len(messages), 1)
        self.assertTrue(all(len(message) <= 1000 for message in messages))

    def test_split_does_not_break_html_entities(self):
        messages = split_telegram_html(["الف &amp; " + ("متن " * 100)], max_length=100)
        self.assertGreater(len(messages), 1)
        self.assertTrue(all(len(message) <= 100 for message in messages))
        self.assertEqual("".join(messages).count("&amp;"), 1)

    def test_missing_data_and_disclaimer_are_preserved(self):
        messages = render_telegram_report(
            sample_assessment(data_warnings=("DXY stale",)), {}, NOW
        )
        joined = "\n".join(messages)
        self.assertIn("جزئیات قیمت و منبع", joined)
        self.assertIn("سیگنال قطعی خرید یا فروش", joined)
        self.assertIn("DXY stale", joined)

    def test_invalid_message_limit_is_rejected(self):
        with self.assertRaises(ValueError):
            split_telegram_html(["متن"], max_length=20)


if __name__ == "__main__":
    unittest.main()
