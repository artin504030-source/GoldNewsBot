import unittest
from market_digest import categorize_news, build_multi_market_digest

class MultiMarketDigestTests(unittest.TestCase):
    def test_categories_cover_multiple_markets(self):
        r=categorize_news({"title":"US inflation CPI, gold rises, oil and Bitcoin rally", "summary":"Nasdaq stocks and Treasury yields react"})
        for market in ("gold","fx","indices","energy","crypto","rates"):
            self.assertIn(market,r["categories"])
        self.assertIn("XAUUSD",r["impact"]["symbols"])
    def test_counts_and_calendar_fields(self):
        news=[{"title":"Fed rate decision and dollar moves", "relevance_score":80,"importance":"زیاد","source":"Reuters","link":"https://example.test/a"},{"title":"Bitcoin crypto gains", "relevance_score":45,"importance":"متوسط"}]
        events=[{"title":"US CPI","country":"US","currency":"USD","date":"2026-11-21","time":"08:30","impact_level":"زیاد","forecast":"3.2","previous":"3.1","related_symbols":["XAUUSD","DXY"]}]
        r=build_multi_market_digest(news,events,"2026-11-20 10:00 (کابل)")
        self.assertEqual(r["market_counts"]["rates"],1)
        self.assertEqual(r["market_counts"]["crypto"],1)
        self.assertEqual(len(r["news"]),2)
        self.assertIn("US CPI",r["message"])
        self.assertIn("Multi-Market Digest",r["message"])
        self.assertIn("cross_market_impact",r["news"][0])
    def test_empty_digest_safe(self):
        r=build_multi_market_digest([],[],"timestamp")
        self.assertEqual(len(r["news"]),0)
        self.assertIn("خبر آرشیوشده",r["message"])

if __name__ == "__main__": unittest.main()
