import unittest
from unittest.mock import Mock
from apps.gold_market.previous import fetch_previous_snapshot

class FakeResponse:
    def __init__(self,p): self.p=p
    def raise_for_status(self): pass
    def json(self): return self.p

class PreviousSnapshotTests(unittest.TestCase):
    def test_collects_previous_fred_and_yahoo_observations(self):
        fred=Mock(); fred.api_key="test"; fred.URL="https://fred.test"; fred.timeout=5
        fred.session.get.return_value=FakeResponse({"observations":[
            {"date":"2026-11-24","value":"4.1"},{"date":"2026-11-23","value":"4.0"}]})
        yahoo=Mock(); yahoo.URL="https://yahoo.test"; yahoo.timeout=5
        yahoo.SYMBOLS={"DXY":"DX-Y.NYB","USOIL":"CL=F"}
        yahoo.session.get.return_value=FakeResponse({"chart":{"result":[{
            "timestamp":[1795446000,1795450000],
            "indicators":{"quote":[{"close":[100.0,101.0]}]}}]}})
        result=fetch_previous_snapshot(fred,yahoo)
        self.assertEqual(str(result["US10Y"].value),"4.0")
        self.assertEqual(str(result["DXY"].value),"100.0")
        self.assertEqual(str(result["USOIL"].value),"100.0")
        self.assertEqual(result["US10Y"].status,"DAILY")

    def test_missing_fred_key_leaves_comparisons_absent(self):
        fred=Mock(); fred.api_key=""; fred.URL="https://fred.test"; fred.timeout=5
        yahoo=Mock(); yahoo.URL="https://yahoo.test"; yahoo.timeout=5
        yahoo.SYMBOLS={"DXY":"DX-Y.NYB","USOIL":"CL=F"}
        yahoo.session.get.side_effect=RuntimeError("network down")
        self.assertEqual(fetch_previous_snapshot(fred,yahoo),{})

if __name__=="__main__": unittest.main()
