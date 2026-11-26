import unittest
from datetime import datetime, timezone, timedelta
from apps.gold_news_analyst.market_context import _fetch_yahoo

class FakeResponse:
    def raise_for_status(self):
        return None
    def json(self):
        now = int(datetime.now(timezone.utc).timestamp())
        return {"chart": {"result": [{
            "timestamp": [now - 25 * 3600, now],
            "indicators": {"quote": [{"close": [4.80, 4.85]}]},
        }]}}

class FakeSession:
    def get(self, *args, **kwargs):
        return FakeResponse()

class MarketContextTests(unittest.TestCase):
    def test_treasury_yield_is_not_divided_by_ten(self):
        item = _fetch_yahoo("^TNX", FakeSession(), 1)
        self.assertAlmostEqual(item["value"], 4.85, places=2)
        self.assertIsNotNone(item["change_pct"])
        self.assertEqual(item["unit"], "yield_percent")

if __name__ == "__main__":
    unittest.main()
