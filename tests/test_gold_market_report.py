import unittest
from datetime import datetime,timezone
from decimal import Decimal
from apps.gold_market.analysis import MarketAssessment
from apps.gold_market.models import MarketObservation
from apps.gold_market.report import render_market_report

NOW=datetime(2026,11,24,15,30,tzinfo=timezone.utc)

def assessment(**overrides):
    values=dict(as_of=NOW,regime="TREND",trend="BULLISH",volatility="NORMAL",
        support=Decimal("2600"),resistance=Decimal("2700"),atr_percent=Decimal("0.45"),
        drivers={"DXY":"HEADWIND_FOR_GOLD","US10Y":"SUPPORTIVE_FOR_GOLD","US02Y":"UNKNOWN",
                 "USOIL":"INFLATION_CONTEXT_UP","SPX":"RISK_APPETITE_UP","VIX":"RISK_AVERSION_HIGHER"},
        main_scenario="سناریوی اصلی آزمایشی",alternative_scenario="سناریوی جایگزین آزمایشی",
        confidence="MEDIUM",event_risk=("US CPI",),data_warnings=())
    values.update(overrides)
    return MarketAssessment(**values)

class GoldMarketReportTests(unittest.TestCase):
    def test_report_contains_persian_sections_and_disclaimer(self):
        report=render_market_report(assessment(),generated_at=NOW)
        for text in ("گزارش وضعیت بازار طلا","وضعیت بازار","زمینه بین‌بازاری","سناریوها",
                     "ریسک رویدادها","هشدارهای کیفیت داده","سیگنال قطعی خرید یا فروش"):
            self.assertIn(text,report)

    def test_report_formats_observations_and_source_status(self):
        obs=MarketObservation("XAUUSD",Decimal("2650.25"),NOW,"XAUS:spot","USD/oz","LIVE","Indicative quote")
        report=render_market_report(assessment(),{"XAUUSD":obs},NOW)
        self.assertIn("2,650.25 USD/oz",report)
        self.assertIn("وضعیت: زنده",report)
        self.assertIn("XAUS:spot",report)
        self.assertIn("Indicative quote",report)

    def test_missing_data_is_explicit(self):
        report=render_market_report(assessment(data_warnings=("DXY stale",)),{},NOW)
        self.assertIn("جزئیات قیمت و منبع",report)
        self.assertIn("DXY stale",report)
        self.assertIn("نامشخص",report)

    def test_unknown_driver_is_not_invented(self):
        a=assessment(drivers={"DXY":"UNKNOWN"})
        report=render_market_report(a,generated_at=NOW)
        self.assertIn("شاخص دلار: نامشخص",report)

if __name__=="__main__":
    unittest.main()
