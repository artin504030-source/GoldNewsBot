"""Best-effort, explicitly timestamped public market context for news analysis."""
from __future__ import annotations
from datetime import datetime, timezone
import os
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
    change_points = (value - prior[1]) if prior and symbol == "^TNX" else None
    observed = datetime.fromtimestamp(ts, tz=timezone.utc)
    age = max(0, int((datetime.now(timezone.utc) - observed).total_seconds() / 60))
    return {
        "value": round(value, 4),
        "change_pct": round(change, 4) if change is not None else None,
        "change_points": round(change_points, 4) if change_points is not None else None,
        "age_minutes": age,
        "observed_utc": observed.isoformat(),
        "status": "DELAYED" if age <= 360 else "STALE",
        "source": f"Yahoo Finance ({symbol})",
        "unit": "USD/oz" if symbol == "XAUUSD=X" else "index" if symbol == "DX-Y.NYB" else "yield_percent" if symbol == "^TNX" else "USD/barrel",
    }

def fetch_market_snapshot(session=None, timeout=12, fred_api_key=None):
    session = session or requests.Session()
    snapshot = {}
    # Reuse the free spot provider already integrated in Gold Market.
    try:
        response = session.get(
            "https://xaus.com/api/v1/spot",
            params={"compact": "1"},
            headers={"User-Agent": "GoldNewsBot/2.0"},
            timeout=timeout,
        )
        response.raise_for_status()
        payload = response.json()
        state = payload.get("data_state") or {}
        xau = payload.get("xau") or {}
        stamp = state.get("as_of") or payload.get("updated_at")
        price = xau.get("price") or payload.get("spot_usd_oz")
        if price is None or not stamp or state.get("status") not in ("fresh", "stale"):
            raise ValueError("XAUS spot quote unavailable")
        observed = datetime.fromisoformat(str(stamp).replace("Z", "+00:00"))
        age = max(0, int((datetime.now(timezone.utc) - observed.astimezone(timezone.utc)).total_seconds() / 60))
        snapshot["XAUUSD"] = {
            "value": round(float(price), 4), "change_pct": None, "age_minutes": age,
            "observed_utc": observed.isoformat(), "status": "LIVE" if state.get("status") == "fresh" and age <= 30 else "STALE",
            "source": "XAUS spot", "unit": "USD/oz",
        }
    except (requests.RequestException, ValueError, KeyError, TypeError) as exc:
        snapshot["XAUUSD"] = {"status": "UNAVAILABLE", "source": "XAUS spot", "error": str(exc)[:180]}
    for key, symbol in YAHOO.items():
        if key == "XAUUSD":
            continue
        try:
            snapshot[key] = _fetch_yahoo(symbol, session, timeout)
        except (requests.RequestException, ValueError, KeyError, TypeError, IndexError) as exc:
            snapshot[key] = {"status": "UNAVAILABLE", "source": f"Yahoo Finance ({symbol})", "error": str(exc)[:180]}
    # FRED DFII10 is a daily 10-year TIPS real-yield series. It is optional.
    key = (fred_api_key or os.getenv("FRED_API_KEY", "")).strip()
    if key:
        try:
            response = session.get(
                "https://api.stlouisfed.org/fred/series/observations",
                params={"series_id": "DFII10", "api_key": key, "file_type": "json", "sort_order": "desc", "limit": 2},
                timeout=timeout,
            )
            response.raise_for_status()
            rows = [row for row in response.json().get("observations", []) if row.get("value") not in (None, "", ".")]
            if not rows:
                raise ValueError("FRED returned no real-yield observations")
            value = float(rows[0]["value"])
            prior = float(rows[1]["value"]) if len(rows) > 1 else None
            change_points = (value - prior) if prior is not None else None
            observed = datetime.strptime(rows[0]["date"], "%Y-%m-%d").replace(tzinfo=timezone.utc)
            age = max(0, int((datetime.now(timezone.utc) - observed).total_seconds() / 60))
            snapshot["US10Y_REAL"] = {
                "value": round(value, 4), "change_points": round(change_points, 4) if change_points is not None else None,
                "age_minutes": age, "observed_utc": observed.isoformat(),
                "status": "DAILY" if age <= 5 * 24 * 60 else "STALE",
                "source": "FRED:DFII10", "unit": "real_yield_percent",
            }
        except (requests.RequestException, ValueError, KeyError, TypeError, IndexError) as exc:
            snapshot["US10Y_REAL"] = {"status": "UNAVAILABLE", "source": "FRED:DFII10", "error": str(exc)[:180]}
    else:
        snapshot["US10Y_REAL"] = {"status": "UNAVAILABLE", "source": "FRED:DFII10", "error": "FRED_API_KEY not configured"}
    return snapshot
