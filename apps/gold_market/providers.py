from __future__ import annotations
from datetime import datetime, timezone
from decimal import Decimal
import requests
from .models import MarketObservation

FRED_SERIES = {"US10Y":("DGS10","percent"),"US02Y":("DGS2","percent"),"USOIL":("DCOILWTICO","USD/barrel"),"SPX":("SP500","index"),"VIX":("VIXCLS","index")}
class ProviderError(RuntimeError): pass

class FredProvider:
    URL="https://api.stlouisfed.org/fred/series/observations"
    def __init__(self,api_key,session=None,timeout=15):
        self.api_key=api_key; self.session=session or requests.Session(); self.timeout=timeout
    def fetch(self,indicator):
        if indicator not in FRED_SERIES: raise ProviderError(f"No FRED series for {indicator}")
        if not self.api_key: raise ProviderError("FRED_API_KEY is not configured")
        sid,unit=FRED_SERIES[indicator]
        try:
            r=self.session.get(self.URL,params={"series_id":sid,"api_key":self.api_key,"file_type":"json","sort_order":"desc","limit":10},timeout=self.timeout); r.raise_for_status()
            for row in r.json().get("observations",[]):
                if row.get("value") in (None,"","."): continue
                return MarketObservation(indicator,Decimal(str(row["value"])),datetime.strptime(row["date"],"%Y-%m-%d").replace(tzinfo=timezone.utc),f"FRED:{sid}",unit,"DAILY","آخرین مشاهده روزانه؛ قیمت لحظه‌ای نیست.")
        except (requests.RequestException,ValueError,KeyError) as e: raise ProviderError(f"FRED {indicator}: {e}") from e
        raise ProviderError(f"No usable FRED observation for {indicator}")

class YahooChartProvider:
    URL="https://query1.finance.yahoo.com/v8/finance/chart"
    SYMBOLS={"XAUUSD":"XAUUSD=X","DXY":"DX-Y.NYB"}
    def __init__(self,session=None,timeout=15): self.session=session or requests.Session(); self.timeout=timeout
    def fetch(self,indicator):
        if indicator not in self.SYMBOLS: raise ProviderError(f"No Yahoo symbol for {indicator}")
        symbol=self.SYMBOLS[indicator]
        try:
            r=self.session.get(f"{self.URL}/{symbol}",params={"range":"5d","interval":"1h"},headers={"User-Agent":"Mozilla/5.0"},timeout=self.timeout); r.raise_for_status()
            result=r.json()["chart"]["result"][0]; ts=result.get("timestamp") or []; closes=result["indicators"]["quote"][0].get("close") or []
            points=[(t,c) for t,c in zip(ts,closes) if c is not None]
            if not points: raise ProviderError(f"No Yahoo close for {indicator}")
            t,v=points[-1]
            return MarketObservation(indicator,Decimal(str(v)),datetime.fromtimestamp(int(t),tz=timezone.utc),f"Yahoo Finance:{symbol}","USD/oz" if indicator=="XAUUSD" else "index","DELAYED","خوراک غیررسمی؛ تأخیر دقیق تضمین نشده است.")
        except ProviderError: raise
        except (requests.RequestException,ValueError,KeyError,IndexError,TypeError) as e: raise ProviderError(f"Yahoo {indicator}: {e}") from e
