"""Fetch comparable prior macro observations for contextual change analysis."""
from datetime import datetime, timezone
from decimal import Decimal
import requests
from .models import MarketObservation
from .providers import FRED_SERIES, YahooChartProvider


def fetch_previous_snapshot(fred_provider, yahoo_provider):
    """Return prior valid observations; a failed optional comparison stays absent."""
    previous = {}
    for indicator, (series_id, unit) in FRED_SERIES.items():
        if not fred_provider.api_key:
            continue
        try:
            response = fred_provider.session.get(
                fred_provider.URL,
                params={"series_id":series_id,"api_key":fred_provider.api_key,
                        "file_type":"json","sort_order":"desc","limit":10},
                timeout=fred_provider.timeout)
            response.raise_for_status()
            rows=[r for r in response.json().get("observations",[]) if r.get("value") not in (None,"",".")]
            if len(rows)<2: continue
            row=rows[1]
            observed=datetime.strptime(row["date"],"%Y-%m-%d").replace(tzinfo=timezone.utc)
            previous[indicator]=MarketObservation(indicator,Decimal(str(row["value"])),observed,
                f"FRED:{series_id}",unit,"DAILY","Previous available FRED observation.")
        except Exception:
            # Prior context is optional; never block the main live snapshot on it.
            continue
    for indicator in ("DXY","USOIL"):
        symbol=YahooChartProvider.SYMBOLS[indicator]
        try:
            response=yahoo_provider.session.get(f"{yahoo_provider.URL}/{symbol}",
                params={"range":"5d","interval":"1h"},headers={"User-Agent":"Mozilla/5.0"},
                timeout=yahoo_provider.timeout)
            response.raise_for_status()
            result=response.json()["chart"]["result"][0]
            ts_list=result.get("timestamp") or []
            closes=result["indicators"]["quote"][0].get("close") or []
            points=[(ts,c) for ts,c in zip(ts_list,closes) if c is not None]
            if len(points)<2: continue
            ts,close=points[-2]
            unit="index" if indicator=="DXY" else "USD/barrel"
            previous[indicator]=MarketObservation(indicator,Decimal(str(close)),
                datetime.fromtimestamp(int(ts),tz=timezone.utc),f"Yahoo Finance:{symbol}",
                unit,"DELAYED","Previous hourly delayed quote; contextual comparison only.")
        except Exception:
            continue
    return previous
