import unittest
from datetime import datetime, timezone, timedelta
from tempfile import TemporaryDirectory
from pathlib import Path
from unittest.mock import patch
from apps.gold_news_analyst.engine import analyse, eligible, fingerprint, SYMBOL_UNIVERSE
from apps.gold_news_analyst.report import render
from apps.gold_news_analyst import __main__ as analyst_main

class AnalystTests(unittest.TestCase):
    def item(self, title, **extra):
        row = {"title": title, "summary": "", "source": "Test Feed", "link": "https://example.com/a", "published_utc": datetime.now(timezone.utc).isoformat(), "relevance_score": 40, "source_count": 3}
        row.update(extra); return row

    def test_geopolitical_headline_does_not_force_a_direction(self):
        result = analyse(self.item("Military strike raises geopolitical risk"))
        self.assertEqual(result["direction"], "خنثی؛ شواهد کافی برای جهت‌دهی وجود ندارد")
        self.assertIn("ژئوپلیتیک و امنیت", result["events"])

    def test_hawkish_inflation_surprise_can_create_bearish_bias(self):
        result = analyse(self.item("Core PCE inflation hotter than expected; Fed signals rate hike"))
        self.assertIn("تمایل فشاری", result["direction"])
        self.assertIn("تورم و شاخص قیمت", result["events"])
        self.assertIn("سیاست پولی و نرخ بهره", result["events"])

    def test_tariffs_are_multi_channel_and_not_automatically_bullish(self):
        result = analyse(self.item("Trump tariffs raise import costs and inflation risks"))
        self.assertIn("تعرفه و تجارت", result["events"])
        self.assertIn("تعرفه‌ها", " ".join(result["drivers"]))
        self.assertIn("خنثی", result["direction"])

    def test_company_appointment_is_not_mistaken_for_gold_market_signal(self):
        result = analyse(self.item("Uta Holzenkamp Appointed New CEO of Heraeus Precious Metals"), "The company announced a new chief executive. " * 10)
        self.assertIn("خنثی", result["direction"])
        self.assertIn("رویداد شرکتی", result["events"])
        self.assertEqual(result["confidence"], "پایین")

    def test_body_mentions_far_below_lead_do_not_create_false_event_labels(self):
        body = "Gold prices slipped below support before a modest rebound. " + ("Market details about bullion trading. " * 60)
        body += "Tariffs war sanctions CPI payroll GDP oil OPEC FOMC bank default " * 20
        result = analyse(self.item("Gold prices slipped below support", summary="Gold market update"), body)
        self.assertIn("طلا و فلزات گران‌بها", result["events"])
        self.assertNotIn("تعرفه و تجارت", result["events"])
        self.assertNotIn("ژئوپلیتیک و امنیت", result["events"])

    def test_article_body_improves_context_and_confidence(self):
        body = ("The Federal Reserve said monetary policy will remain restrictive. " * 8)
        result = analyse(self.item("Fed policy update"), body)
        self.assertTrue(result["article_text_ok"])
        self.assertIn("سیاست پولی و نرخ بهره", result["events"])

    def test_market_snapshot_is_ignored_and_symbol_impacts_are_classified(self):
        snapshot = {
            "DXY": {"value": 105, "change_pct": 0.4, "status": "DELAYED", "age_minutes": 30},
            "US10Y": {"value": 4.3, "change_pct": 0.05, "status": "DELAYED", "age_minutes": 30},
            "XAUUSD": {"value": 2700, "change_pct": -0.3, "status": "DELAYED", "age_minutes": 30},
        }
        result = analyse(self.item("Core CPI above expectations"), "", snapshot)
        impacts = {x["symbol"]: x for x in result["symbol_impacts"]}
        self.assertIn("XAUUSD", impacts)
        self.assertIn("EURUSD", impacts)
        self.assertEqual(result["market_lines"], [])
        self.assertFalse(result["market_warnings"])

    def test_news_only_report_has_no_intermarket_section(self):
        output = render(self.item("Core CPI above expectations"))
        self.assertNotIn("داده‌های بین‌بازاری", output)
        self.assertIn("نمادهای مرتبط و اثر احتمالی", output)

    def test_symbol_universe_matches_all_gold_prices_instruments(self):
        self.assertEqual(len(SYMBOL_UNIVERSE), 16)
        for symbol in ("XAUUSD", "XAGUSD", "XPTUSD", "XPDUSD", "EURUSD", "GBPUSD",
                       "USDJPY", "AUDUSD", "USDCAD", "US30", "USTEC", "US500",
                       "DE30", "USOIL", "UKOIL", "XNGUSD"):
            self.assertIn(symbol, SYMBOL_UNIVERSE)

    def test_energy_news_maps_to_oil_and_gas_symbols(self):
        result = analyse(self.item("Natural gas supply disruption after pipeline attack"),
                         "Natural gas supply disruption and pipeline attack. " * 8)
        impacts = {x["symbol"]: x for x in result["symbol_impacts"]}
        self.assertIn("USOIL", impacts)
        self.assertIn("UKOIL", impacts)
        self.assertIn("XNGUSD", impacts)

    def test_gold_relevance_filter_is_disabled_for_all_news(self):
        item = self.item("Regional manufacturing update", relevance_score=0)
        self.assertTrue(eligible(item, datetime.now(timezone.utc), min_relevance=0))

    def test_unrelated_company_news_does_not_invent_symbol_impact(self):
        result = analyse(self.item("Small local retailer appoints new CEO"))
        self.assertEqual(result["symbol_impacts"], [])

    def test_stale_or_fresh_quotes_do_not_change_news_only_analysis(self):
        fresh = {"DXY": {"value": 105, "change_pct": 0.8, "status": "DELAYED"}}
        stale = {"DXY": {"value": 105, "change_pct": -0.8, "status": "STALE"}}
        headline = self.item("Core CPI above expectations")
        self.assertEqual(analyse(headline, "", fresh)["symbol_impacts"],
                         analyse(headline, "", stale)["symbol_impacts"])

    def test_old_and_low_relevance_news_rejected(self):
        old = self.item("Fed news", published_utc=(datetime.now(timezone.utc)-timedelta(days=2)).isoformat())
        weak = self.item("Fed news", relevance_score=10); now = datetime.now(timezone.utc)
        self.assertFalse(eligible(old, now)); self.assertFalse(eligible(weak, now))

    def test_source_count_not_claimed_as_independent_confirmation(self):
        self.assertIn("تأیید ناشران مستقل نیست", render(self.item("A geopolitical event", source_count=8)))

    def test_report_labels_missing_article_body(self):
        output = render(self.item("Core PCE inflation"), {"body": "", "error": "publisher blocked"})
        self.assertIn("متن کامل دریافت نشد", output)
        self.assertIn("publisher blocked", output)

    def test_fingerprint_stable(self):
        item = self.item("Headline"); self.assertEqual(fingerprint(item), fingerprint(item.copy()))

    def test_state_saved_after_each_successful_send(self):
        now = datetime.now(timezone.utc)
        one = self.item("First", published_utc=(now - timedelta(seconds=1)).isoformat())
        two = self.item("Second", published_utc=(now - timedelta(seconds=2)).isoformat())
        with TemporaryDirectory() as tmp:
            archive = Path(tmp)/"archive.json"; state_path = Path(tmp)/"state.json"
            archive.write_text(__import__("json").dumps([one,two]), encoding="utf-8")
            cfg = analyst_main.Settings("token","channel",str(archive),str(state_path),24,0,5,False,False); calls=[]
            def fake_send(*args):
                calls.append(1)
                if len(calls)==2:
                    saved=__import__("json").loads(state_path.read_text(encoding="utf-8"))["sent"]
                    self.assertEqual(saved,[fingerprint(one)]); raise RuntimeError("second send failed")
            with patch.object(analyst_main.Settings,"from_env",return_value=cfg), patch.object(analyst_main,"send",side_effect=fake_send):
                with self.assertRaises(RuntimeError): analyst_main.main()
            self.assertEqual(__import__("json").loads(state_path.read_text(encoding="utf-8"))["sent"],[fingerprint(one)])

    def test_dry_run_does_not_send_or_persist_state(self):
        item = self.item("Dry run headline")
        with TemporaryDirectory() as tmp:
            archive = Path(tmp)/"archive.json"; state_path = Path(tmp)/"state.json"
            archive.write_text(__import__("json").dumps([item]), encoding="utf-8")
            cfg = analyst_main.Settings("token","channel",str(archive),str(state_path),24,0,5,True,False)
            with patch.object(analyst_main.Settings,"from_env",return_value=cfg), patch.object(analyst_main,"send") as send_mock:
                analyst_main.main()
            send_mock.assert_not_called()
            self.assertFalse(state_path.exists())

if __name__ == "__main__": unittest.main()
