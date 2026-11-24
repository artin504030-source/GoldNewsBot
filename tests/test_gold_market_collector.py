import unittest
from datetime import datetime,timezone
from decimal import Decimal
from unittest.mock import Mock
from apps.gold_market.providers import FredProvider,YahooChartProvider,ProviderError
from apps.gold_market.collector import MarketDataCollector,ALL_INDICATORS
from apps.gold_market.models import MarketObservation
class Response:
    def __init__(self,p): self.p=p
    def raise_for_status(self): pass
    def json(self): return self.p
class Tests(unittest.TestCase):
    def test_fred_latest_valid_daily(self):
        s=Mock(); s.get.return_value=Response({"observations":[{"date":"2026-11-24","value":"."},{"date":"2026-11-23","value":"4.12"}]})
        x=FredProvider("key",s).fetch("US10Y"); self.assertEqual(x.value,Decimal("4.12")); self.assertEqual(x.status,"DAILY")
    def test_fred_requires_key(self):
        with self.assertRaises(ProviderError): FredProvider(None).fetch("US10Y")
    def test_fred_does_not_claim_dxy(self):
        with self.assertRaises(ProviderError): FredProvider("key").fetch("DXY")
    def test_yahoo_delayed_spot_symbol(self):
        s=Mock(); s.get.return_value=Response({"chart":{"result":[{"timestamp":[1795500000],"indicators":{"quote":[{"close":[2650.5}]}}]}})
        x=YahooChartProvider(s).fetch("XAUUSD"); self.assertEqual(x.status,"DELAYED"); self.assertEqual(x.source,"Yahoo Finance:XAUUSD=X")
        self.assertNotEqual(YahooChartProvider.SYMBOLS["XAUUSD"],"GC=F")
    def test_all_symbols_and_independent_failures(self):
        y,f=Mock(),Mock(); y.fetch.return_value=MarketObservation("XAUUSD",Decimal("2650"),datetime.now(timezone.utc),"test",status="DELAYED")
        f.fetch.side_effect=ProviderError("offline")
        result=MarketDataCollector(f,y).collect_all()
        self.assertEqual(tuple(result),ALL_INDICATORS); self.assertEqual(len(result),7); self.assertIsNone(result["US10Y"].observation)
if __name__=="__main__": unittest.main()
