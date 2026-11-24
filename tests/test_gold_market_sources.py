import unittest
from datetime import datetime, timezone
from unittest.mock import Mock

from apps.gold_market.providers import (
    ProviderError,
    XausSpotProvider,
    YahooChartProvider,
)


class FakeResponse:
    def __init__(self, payload):
        self.payload = payload

    def raise_for_status(self):
        return None

    def json(self):
        return self.payload


class GoldMarketSourceTests(unittest.TestCase):
    def test_xaus_fresh_spot_quote_is_live(self):
        session = Mock()
        session.get.return_value = FakeResponse({
            "xau": {"price": 2651.25},
            "updated_at": "2026-11-24T15:00:00Z",
            "data_state": {
                "status": "fresh",
                "as_of": "2026-11-24T15:00:00Z",
                "source": "upstream",
            },
        })

        item = XausSpotProvider(session=session).fetch("XAUUSD")

        self.assertEqual(str(item.value), "2651.25")
        self.assertEqual(item.status, "LIVE")
        self.assertEqual(item.unit, "USD/oz")
        self.assertEqual(item.observed_at.tzinfo, timezone.utc)
        session.get.assert_called_once()

    def test_xaus_stale_quote_remains_stale(self):
        session = Mock()
        session.get.return_value = FakeResponse({
            "xau": {"price": 2651.25},
            "updated_at": "2026-11-24T14:00:00Z",
            "data_state": {
                "status": "stale",
                "as_of": "2026-11-24T14:00:00Z",
                "source": "cache",
            },
        })

        item = XausSpotProvider(session=session).fetch("XAUUSD")

        self.assertEqual(item.status, "STALE")

    def test_xaus_unavailable_response_is_rejected(self):
        session = Mock()
        session.get.return_value = FakeResponse({
            "data_state": {"status": "unavailable"}
        })

        with self.assertRaises(ProviderError):
            XausSpotProvider(session=session).fetch("XAUUSD")

    def test_yahoo_oil_uses_front_month_wti_futures(self):
        session = Mock()
        session.get.return_value = FakeResponse({
            "chart": {
                "result": [{
                    "timestamp": [1795532400],
                    "indicators": {"quote": [{"close": [80.25]}]},
                }]
            }
        })

        item = YahooChartProvider(session=session).fetch("USOIL")

        self.assertEqual(str(item.value), "80.25")
        self.assertEqual(item.status, "DELAYED")
        self.assertEqual(item.unit, "USD/barrel")
        self.assertEqual(item.source, "Yahoo Finance:CL=F")
        self.assertIn("آتی", item.note)
        self.assertEqual(
            session.get.call_args.args[0],
            "https://query1.finance.yahoo.com/v8/finance/chart/CL=F",
        )


if __name__ == "__main__":
    unittest.main()
