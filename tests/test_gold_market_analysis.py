import unittest
from datetime import datetime,timedelta,timezone
from decimal import Decimal
from unittest.mock import Mock
from apps.gold_market.analysis import GoldBar,analyze_market
from apps.gold_market.history import XausDailyHistoryProvider,HistoryProviderError
from apps.gold_market.models import MarketObservation
NOW=datetime(2026,11,24,15,0,tzinfo=timezone.utc)
class FakeResponse:
    def __init__(self,p): self.p=p
    def raise_for_status(self): pass
    def json(self): return self.p
def payload(n=30,status="fresh",last="2026-11-23"):
    end=datetime.fromisoformat(last).date(); points=[]
    for i in range(n):
        d=end-timedelta(days=n-i-1); c=2600+i*2; points.append({"d":d.isoformat(),"c":c,"h":c+3,"l":c-3})
    return {"data_state":{"status":status,"as_of":"2026-11-24T14:00:00Z"},"updated_at":"2026-11-24T14:00:00Z","points":points}
class HistoryTests(unittest.TestCase):
    def test_fetch_daily(self):
        s=Mock(); s.get.return_value=FakeResponse(payload()); b=XausDailyHistoryProvider(session=s).fetch_bars(now=NOW)
        self.assertEqual(len(b),30); self.assertIsNone(b[-1].open); self.assertEqual(b[-1].close,Decimal("2658"))
    def test_reject_stale(self):
        s=Mock(); s.get.return_value=FakeResponse(payload(status="stale"))
        with self.assertRaises(HistoryProviderError): XausDailyHistoryProvider(session=s).fetch_bars(now=NOW)
    def test_minimum_twenty(self):
        s=Mock(); s.get.return_value=FakeResponse(payload(n=12))
        with self.assertRaises(HistoryProviderError): XausDailyHistoryProvider(session=s).fetch_bars(now=NOW)
    def test_skip_today(self):
        s=Mock(); s.get.return_value=FakeResponse(payload(n=25,last="2026-11-24"))
        b=XausDailyHistoryProvider(session=s).fetch_bars(now=NOW); self.assertEqual(b[-1].observed_at.date().isoformat(),"2026-11-23")
    def test_invalid_range(self):
        p=payload(); p["points"][-1]["h"]=1; s=Mock(); s.get.return_value=FakeResponse(p)
        with self.assertRaises(HistoryProviderError): XausDailyHistoryProvider(session=s).fetch_bars(now=NOW)

def obs(s,v,status="LIVE",age=0):
    return MarketObservation(s,Decimal(str(v)),NOW-timedelta(hours=age),"test","unit",status,"")
def bars(n=25,age=1):
    out=[]
    for i in range(n):
        c=Decimal(2600+i*2); out.append(GoldBar(NOW-timedelta(hours=n-i-1+age),c-1,c+5,c-5,c))
    return out
class AnalysisTests(unittest.TestCase):
    def test_bullish_levels(self):
        r=analyze_market({"XAUUSD":obs("XAUUSD",2650)},bars(),now=NOW); self.assertEqual(r.trend,"BULLISH"); self.assertIsNotNone(r.support)
    def test_insufficient(self): self.assertEqual(analyze_market({},bars(10),now=NOW).trend,"UNAVAILABLE")
    def test_daily_open_optional(self):
        b=[GoldBar(NOW-timedelta(hours=24*(25-i)),None,Decimal(2700),Decimal(2500),Decimal(2640+i)) for i in range(25)]
        self.assertNotEqual(analyze_market({"XAUUSD":obs("XAUUSD",2650)},b,now=NOW).trend,"UNAVAILABLE")
    def test_old_history(self): self.assertEqual(analyze_market({},bars(age=120),now=NOW).trend,"UNAVAILABLE")
    def test_future_history(self): self.assertEqual(analyze_market({},bars(age=-2),now=NOW).trend,"UNAVAILABLE")
    def test_stale_spot(self):
        r=analyze_market({"XAUUSD":obs("XAUUSD",2650,"STALE")},bars(),now=NOW); self.assertEqual(r.confidence,"LOW")
    def test_driver(self):
        r=analyze_market({"DXY":obs("DXY",100)},bars(),{"DXY":obs("DXY",101)},now=NOW); self.assertEqual(r.drivers["DXY"],"SUPPORTIVE_FOR_GOLD")
    def test_unknown_driver(self): self.assertEqual(analyze_market({},bars(),now=NOW).drivers["VIX"],"UNKNOWN")
    def test_events(self): self.assertEqual(analyze_market({},bars(),upcoming_events=("US CPI",),now=NOW).event_risk,("US CPI",))
    def test_naive_time(self):
        with self.assertRaises(ValueError): GoldBar(NOW.replace(tzinfo=None),Decimal(1),Decimal(2),Decimal(1),Decimal(1))
    def test_bad_range(self):
        with self.assertRaises(ValueError): GoldBar(NOW,Decimal(10),Decimal(9),Decimal(8),Decimal(10))
if __name__=="__main__": unittest.main()
