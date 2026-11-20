import unittest
from unittest.mock import patch
import gold_news_features as g
class FakeResponse:
    content = b"<weekly><event><title>US CPI</title><country>USD</country><date>11-20-2026</date><time>8:30am</time><impact>High</impact><forecast>3.1%</forecast><previous>3.0%</previous></event><event><title>Euro CPI</title><country>EUR</country><date>11-21-2026</date><time>10:00am</time><impact>Medium</impact><forecast>2%</forecast><previous>1.9%</previous></event></weekly>"
    def raise_for_status(self): pass
class Tests(unittest.TestCase):
    @patch("requests.get", return_value=FakeResponse())
    def test_us_event_enriched(self, mock_get):
        ev = g.fetch_calendar_events(2)[0]
        self.assertEqual(ev["currency"],"USD")
        self.assertEqual(ev["impact_level"],"زیاد")
        self.assertIn("XAUUSD",ev["related_symbols"])
        self.assertEqual(ev["timezone"],"نامشخص")
    @patch("requests.get", return_value=FakeResponse())
    def test_eur_mapping(self, mock_get):
        ev = g.fetch_calendar_events(2)[1]
        self.assertEqual(ev["currency"],"EUR")
        self.assertIn("EURUSD",ev["related_symbols"])
        self.assertEqual(ev["impact_level"],"متوسط")
    def test_impact_unknown(self):
        self.assertEqual(g.normalize_calendar_impact(""),"نامشخص")
if __name__ == "__main__": unittest.main()
