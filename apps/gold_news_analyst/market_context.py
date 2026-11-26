"""Best-effort, explicitly timestamped public market context for news analysis."""
from __future__ import annotations
from datetime import datetime, timezone
import requests

YAHOO = {
    "XAUUSD": "XAUUSD=X",
    "DXY": "DX-Y.NYB",
    "US10Y": "^TNX",
    "USOIL": "CL=F",
}

def _fetch_yahoo(symbol, session, timeout):
    response = session.get(
        f"https://query1.finance.yahoo.com/v8/finance/chart/{symbol}",
        params={"range": "5d", "interval": "1h"},
        headers={"User-Agent": "Mozilla/5.0"},
        timeout=timeout,
    )
    response.raise_for_status()
    result = response.json()["chart"]["result"][0]
    timestamps = result.get("timestamp") or []
    closes = result["indicators"]["quote"][0].get("close") or []
    points = [(int(ts), float(value)) for ts, value in zip(timestamps, closes) if value is not None]
    if not points:
        raise ValueError("No usable market observations")
    ts, value = points[-1]
    # Compare to the nearest available hourly observation at least 20h earlier.
    prior = next(((t, v) for t, v in reversed(points[:-1]) if ts - t >= 20 * 3600), None)
    change = ((value / prior[1]) - 1) * 100 if prior and prior[1] else None
    observed = datetime.fromtimestamp(ts, tz=timezone.utc)
    age = max(0, int((datetime.now(timezone.utc) - observed).total_seconds() / 60))
    if symbol == "^TNX":
        value /= 10.0
    return {
        "value": round(value, 4),
        "change_pct": round(change, 4) if change is not None else None,
        "age_minutes": age,
        "observed_utc": observed.isoformat(),
        "status": "DELAYED" if age <= 360 else "STALE",
        "source": f"Yahoo Finance ({symbol})",
        "unit": "USD/oz" if symbol == "XAUUSD=X" else "index" if symbol == "DX-Y.NYB" else "yield_percent" if symbol == "^TNX" else "USD/barrel",
    }

def fetch_market_snapshot(session=None, timeout=12):
    session = session or requests.Session()
    snapshot = {}
    for key, symbol in YAHOO.items():
        try:
            snapshot[key] = _fetch_yahoo(symbol, session, timeout)
        except (requests.RequestException, ValueError, KeyError, TypeError, IndexError) as exc:
            snapshot[key] = {"status": "UNAVAILABLE", "source": f"Yahoo Finance ({symbol})", "error": str(exc)[:180]}
    return snapshot
