import unittest
from market_analysis import analyze_market_news

class MarketAnalysisTests(unittest.TestCase):
    def test_gold_news(self):
        self.assertIn("XAUUSD", analyze_market_news("Gold bullion demand increases", "")["symbols"])
    def test_euro_news(self):
        self.assertIn("EURUSD", analyze_market_news("ECB decision in eurozone", "")["symbols"])
    def test_oil_news(self):
        self.assertIn("USOIL", analyze_market_news("WTI crude oil supply update", "")["symbols"])
    def test_unknown_symbol(self):
        self.assertEqual(analyze_market_news("Local community festival", "")["symbols"], ["ارتباط نماد مشخص نشد"])
    def test_ambiguous_direction_is_not_positive(self):
        self.assertEqual(analyze_market_news("Fed policy announcement", "")["potential_effect"], "خنثی یا اثر نامشخص")

if __name__ == "__main__":
    unittest.main()
