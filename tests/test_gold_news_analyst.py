import unittest
from datetime import datetime, timezone, timedelta
from tempfile import TemporaryDirectory
from pathlib import Path
from unittest.mock import patch
from apps.gold_news_analyst.engine import analyse, eligible, fingerprint
from apps.gold_news_analyst.report import render
from apps.gold_news_analyst import __main__ as analyst_main

class AnalystTests(unittest.TestCase):
    def item(self, title, **extra):
        row = {"title": title, "summary": "", "source": "Test Feed", "link": "https://example.com/a", "published_utc": datetime.now(timezone.utc).isoformat(), "relevance_score": 40, "source_count": 3}
        row.update(extra); return row
    def test_geopolitical_event_is_cautiously_supportive(self):
        self.assertEqual(analyse(self.item("Military strike raises geopolitical risk"))["direction"], "تمایل حمایتی برای طلا")
    def test_dollar_strength_is_potential_headwind(self):
        self.assertEqual(analyse(self.item("Dollar strengthens as Treasury yields rise"))["direction"], "تمایل فشاری برای طلا")
    def test_ambiguous_inflation_is_not_forced_direction(self):
        self.assertEqual(analyse(self.item("US CPI inflation report released"))["direction"], "خنثی؛ جهت قطعی مشخص نیست")
    def test_old_and_low_relevance_news_rejected(self):
        old = self.item("Fed news", published_utc=(datetime.now(timezone.utc)-timedelta(days=2)).isoformat()); weak = self.item("Fed news", relevance_score=10); now = datetime.now(timezone.utc)
        self.assertFalse(eligible(old, now)); self.assertFalse(eligible(weak, now))
    def test_source_count_not_claimed_as_independent_confirmation(self):
        self.assertIn("لزوماً تأیید ناشران مستقل نیست", render(self.item("A geopolitical event", source_count=8)))
    def test_fingerprint_stable(self):
        item = self.item("Headline"); self.assertEqual(fingerprint(item), fingerprint(item.copy()))
    def test_state_saved_after_each_successful_send(self):
        now = datetime.now(timezone.utc)
        one = self.item("First", published_utc=(now - timedelta(seconds=1)).isoformat())
        two = self.item("Second", published_utc=(now - timedelta(seconds=2)).isoformat())
        with TemporaryDirectory() as tmp:
            archive = Path(tmp)/"archive.json"; state_path = Path(tmp)/"state.json"
            archive.write_text(__import__("json").dumps([one,two]), encoding="utf-8")
            cfg = analyst_main.Settings("token","channel",str(archive),str(state_path),24,0,5,False); calls=[]
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
            cfg = analyst_main.Settings("token","channel",str(archive),str(state_path),24,0,5,True)
            with patch.object(analyst_main.Settings,"from_env",return_value=cfg), patch.object(analyst_main,"send") as send_mock:
                analyst_main.main()
            send_mock.assert_not_called()
            self.assertFalse(state_path.exists())
if __name__ == "__main__": unittest.main()
