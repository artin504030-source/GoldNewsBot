import unittest
from market_relationships import analyze_relationships, format_relationships


class MarketRelationshipTests(unittest.TestCase):
    def test_yield_increase_maps_markets(self):
        notes = analyze_relationships("US treasury yields rise")
        self.assertEqual(notes[0]["event"], "افزایش بازده اوراق آمریکا")
        self.assertIn("XAUUSD", notes[0]["assets"])
    def test_risk_off_maps_volatility_and_gold(self):
        notes = analyze_relationships("risk-off sentiment and flight to safety")
        self.assertEqual(notes[0]["event"], "ریسک‌گریزی")
        self.assertIn("VIX", notes[0]["assets"])
    def test_no_match_is_safe(self):
        self.assertEqual(analyze_relationships("company announces new office"), [])
        self.assertIn("جهت‌گیری ساخته نشد", format_relationships("unknown event"))
    def test_multiple_matches(self):
        notes = analyze_relationships("dollar strengthens and oil prices rise")
        self.assertEqual(len(notes), 2)
        self.assertEqual({n["event"] for n in notes}, {"دلار قوی", "افزایش قیمت نفت"})

if __name__ == "__main__":
    unittest.main()
