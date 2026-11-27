import unittest
from datetime import datetime, timezone, timedelta
from tempfile import TemporaryDirectory
from pathlib import Path
from unittest.mock import patch
from apps.gold_news_analyst.engine import analyse, eligible, fingerprint, SYMBOL_UNIVERSE
from apps.gold_news_analyst.report import render
from apps.gold_news_analyst import __main__ as analyst_main
from apps.gold_news_analyst.us_macro import analyze_us_macro

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

    def test_report_includes_original_and_persian_headlines(self):
        item = self.item("Federal Reserve keeps interest rates unchanged")
        with patch("apps.gold_news_analyst.report.translate_title_to_persian", return_value="فدرال رزرو نرخ بهره را بدون تغییر حفظ کرد"):
            output = render(item)
        self.assertIn("عنوان اصلی:", output)
        self.assertIn("عنوان فارسی: فدرال رزرو نرخ بهره را بدون تغییر حفظ کرد", output)

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

    def test_unemployment_rate_surprise_is_inverted_for_currency_bias(self):
        result = analyse(self.item("US unemployment above expectations"))
        impacts = {x["symbol"]: x for x in result["symbol_impacts"]}
        self.assertEqual(impacts["EURUSD"]["impact"], "صعودی بالقوه")
        self.assertEqual(impacts["USDJPY"]["impact"], "نزولی بالقوه")

    def test_keyword_matching_does_not_match_oil_inside_boiling(self):
        result = analyse(self.item("Boiling point research update"))
        self.assertNotIn("نفت و انرژی", result["events"])
        self.assertNotIn("USOIL", {x["symbol"] for x in result["symbol_impacts"]})

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
        self.assertFalse(eligible(old, now)); self.assertTrue(eligible(weak, now)); self.assertFalse(eligible(weak, now, min_relevance=25))

    def test_source_count_not_claimed_as_independent_confirmation(self):
        self.assertIn("تأیید ناشران مستقل نیست", render(self.item("A geopolitical event", source_count=8)))

    def test_report_labels_missing_article_body(self):
        output = render(self.item("Core PCE inflation"), {"body": "", "error": "publisher blocked"})
        self.assertIn("متن کامل دریافت نشد", output)
        self.assertIn("publisher blocked", output)

    def test_us_cpi_actual_forecast_previous_and_gold_transmission_are_reported(self):
        item = self.item("US Core CPI Actual: 3.1% Forecast: 3.0% Previous: 3.2%")
        result = analyze_us_macro(item, "The latest CPI report showed the figures.")
        self.assertEqual(result["indicator"], "CPI / Core CPI")
        self.assertEqual(result["surprise"], "قوی‌تر/بالاتر از انتظار")
        self.assertEqual(result["actual"], "3.1%")
        self.assertIn("بازده واقعی", result["mechanism"])
        self.assertIn("فشار نزولی بالقوه", result["gold"])

    def test_jobless_claims_higher_actual_is_classified_as_weaker_labor(self):
        item = self.item("Initial Jobless Claims Actual: 230K Forecast: 220K Previous: 215K")
        result = analyze_us_macro(item)
        self.assertEqual(result["indicator"], "Initial / Continuing Jobless Claims")
        self.assertEqual(result["surprise"], "ضعیف‌تر/پایین‌تر از انتظار")

    def test_preview_does_not_invent_actual_value_or_surprise(self):
        item = self.item("Preview: economists expect US CPI to ease; consensus forecast 2.8%")
        result = analyze_us_macro(item)
        self.assertIsNone(result["actual"])
        self.assertIsNone(result["surprise"])
        self.assertIn("پیش‌نمایش", result["stage"])
        self.assertIn("جهت قطعی", result["gold"])

    def test_nfp_specialist_notes_include_revisions_and_wages(self):
        item = self.item("US Nonfarm Payrolls report released")
        result = analyze_us_macro(item, "Employment report details were published.")
        self.assertIn("بازنگری دو ماه قبل", result["caveat"])
        self.assertTrue(any("DXY" in line for line in result["checks"]))

    def test_us_macro_section_is_included_in_rendered_report(self):
        item = self.item("US Core PCE inflation Actual: 2.9% Forecast: 2.8% Previous: 2.8%")
        with patch("apps.gold_news_analyst.report.translate_title_to_persian", return_value="گزارش تورم"):
            output = render(item)
        self.assertIn("تحلیل تخصصی گزارش اقتصادی آمریکا", output)
        self.assertIn("Actual:", output)
        self.assertIn("مسیر انتقال اثر به بازار", output)

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
            def fake_send(*args, **kwargs):
                calls.append(1)
                if len(calls)==2:
                    saved=__import__("json").loads(state_path.read_text(encoding="utf-8"))["sent"]
                    self.assertEqual(saved,[fingerprint(one)]); raise RuntimeError("second send failed")
            with patch.object(analyst_main.Settings,"from_env",return_value=cfg), patch.object(analyst_main,"send",side_effect=fake_send):
                with self.assertRaises(RuntimeError): analyst_main.main()
            self.assertEqual(__import__("json").loads(state_path.read_text(encoding="utf-8"))["sent"],[fingerprint(one)])


    def test_workflow_run_only_analyzes_news_archived_during_triggered_news_run(self):
        now = datetime.now(timezone.utc)
        cutoff = now - timedelta(minutes=2)
        old = self.item("Older unrelated archive item", published_utc=now.isoformat(), archived_at_utc=(cutoff - timedelta(minutes=1)).isoformat())
        new = self.item("News sent in this run", published_utc=now.isoformat(), archived_at_utc=(cutoff + timedelta(seconds=10)).isoformat())
        with TemporaryDirectory() as tmp:
            archive = Path(tmp)/"archive.json"; state_path = Path(tmp)/"state.json"
            archive.write_text(__import__("json").dumps([old, new]), encoding="utf-8")
            cfg = analyst_main.Settings("token", "channel", str(archive), str(state_path), 24, 0, 5, False, False)
            sent_messages = []
            with patch.object(analyst_main.Settings, "from_env", return_value=cfg), \
                 patch.dict(analyst_main.os.environ, {"GOLD_NEWS_ANALYST_TRIGGERED_AFTER": cutoff.isoformat()}), \
                 patch.object(analyst_main, "fetch_article", return_value={"body": "", "final_url": "https://example.com/a"}), \
                 patch.object(analyst_main, "render", side_effect=lambda item, article: item["title"]), \
                 patch.object(analyst_main, "send", side_effect=lambda token, chat, message, **kwargs: sent_messages.append(message)):
                analyst_main.main()
            self.assertEqual(sent_messages, ["News sent in this run"])
            self.assertEqual(__import__("json").loads(state_path.read_text(encoding="utf-8"))["sent"], [fingerprint(new)])


    def test_send_replies_to_original_news_message_when_message_id_exists(self):
        item = self.item("Core CPI above expectations", telegram_message_id=12345, telegram_chat_id="@goldchannel")
        with patch.object(analyst_main.requests, "post") as post:
            response = post.return_value
            response.json.return_value = {"ok": True, "result": {"message_id": 67890}}
            response.raise_for_status.return_value = None
            analyst_main.send("token", "@goldchannel", "analysis", reply_to_message_id=item["telegram_message_id"])
            self.assertEqual(post.call_args.kwargs["data"]["reply_to_message_id"], 12345)
            self.assertTrue(post.call_args.kwargs["data"]["allow_sending_without_reply"])

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


    def test_eurozone_hicp_actual_forecast_and_gold_path(self):
        from apps.gold_news_analyst.regional_macro import analyze_regional_macro
        item = self.item("Eurozone HICP Actual: 2.8% Forecast: 2.6% Previous: 2.7%", source="Eurostat")
        result = analyze_regional_macro(item, "Euro area inflation report released with headline and core details. " * 8)
        self.assertEqual(result["region"], "🇪🇺 اروپا / منطقه یورو")
        self.assertEqual(result["indicator"], "HICP / Core HICP")
        self.assertEqual(result["surprise"], "قوی‌تر/بالاتر از انتظار")
        self.assertIn("غیرمستقیم", result["gold"])

    def test_uk_boe_rate_policy_is_not_assumed_without_statement(self):
        from apps.gold_news_analyst.regional_macro import analyze_regional_macro
        item = self.item("Bank of England rate decision", source="Bank of England")
        result = analyze_regional_macro(item)
        self.assertEqual(result["currency"], "GBP")
        self.assertIn("قابل تعیین نیست", result["policy"])

    def test_japan_cpi_lower_than_forecast_is_weaker(self):
        from apps.gold_news_analyst.regional_macro import analyze_regional_macro
        item = self.item("Japan CPI Actual: 2.1% Forecast: 2.4% Previous: 2.3%", source="Bank of Japan")
        result = analyze_regional_macro(item)
        self.assertEqual(result["region"], "🇯🇵 ژاپن")
        self.assertEqual(result["surprise"], "ضعیف‌تر/پایین‌تر از انتظار")
        self.assertEqual(result["currency"], "JPY")

    def test_china_pmi_preview_does_not_invent_actual(self):
        from apps.gold_news_analyst.regional_macro import analyze_regional_macro
        item = self.item("China PMI preview: economists expect 50.2", source="Google News — Asia Economic Expectations")
        result = analyze_regional_macro(item)
        self.assertEqual(result["region"], "🇨🇳 چین")
        self.assertIsNone(result["actual"])
        self.assertIsNone(result["surprise"])
        self.assertIn("پیش‌نمایش", result["stage"])

    def test_regional_macro_is_rendered_in_analyst_report(self):
        item = self.item("Eurozone HICP Actual: 2.8% Forecast: 2.6% Previous: 2.7%", source="Eurostat")
        with patch("apps.gold_news_analyst.report.translate_title_to_persian", return_value="تورم اروپا"):
            output = render(item)
        self.assertIn("تحلیل تخصصی گزارش اقتصادی", output)
        self.assertIn("🇪🇺 اروپا", output)
        self.assertIn("EUR", output)


    def test_india_rbi_policy_report_is_classified(self):
        from apps.gold_news_analyst.regional_macro import analyze_regional_macro
        item = self.item("Reserve Bank of India repo rate decision", source="Google News — Asia Official Economic Releases")
        result = analyze_regional_macro(item)
        self.assertEqual(result["region"], "🇮🇳 هند")
        self.assertEqual(result["currency"], "INR")

    def test_south_korea_cpi_is_not_misclassified_as_china_or_japan(self):
        from apps.gold_news_analyst.regional_macro import analyze_regional_macro
        item = self.item("South Korea CPI Actual: 2.4% Forecast: 2.2% Previous: 2.1%", source="Google News — Asia Official Economic Releases")
        result = analyze_regional_macro(item)
        self.assertEqual(result["region"], "🇰🇷 کوریای جنوبی")
        self.assertEqual(result["surprise"], "قوی‌تر/بالاتر از انتظار")

if __name__ == "__main__": unittest.main()
