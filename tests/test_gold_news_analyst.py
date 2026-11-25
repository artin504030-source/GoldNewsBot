import unittest
from datetime import datetime, timezone, timedelta
from apps.gold_news_analyst.engine import analyse, eligible, fingerprint
from apps.gold_news_analyst.report import render

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
        old = self.item("Fed news", published_utc=(datetime.now(timezone.utc)-timedelta(days=2)).isoformat())
        weak = self.item("Fed news", relevance_score=10)
        now = datetime.now(timezone.utc)
        self.assertFalse(eligible(old, now)); self.assertFalse(eligible(weak, now))

    def test_source_count_not_claimed_as_independent_confirmation(self):
        text = render(self.item("A geopolitical event", source_count=8))
        self.assertIn("لزوماً تأیید ناشران مستقل نیست", text)

    def test_fingerprint_stable(self):
        item = self.item("Headline")
        self.assertEqual(fingerprint(item), fingerprint(item.copy()))

if __name__ == "__main__": unittest.main()
