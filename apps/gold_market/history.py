"""XAUS daily XAU/USD history adapter (no API key required)."""
from datetime import date, datetime, time, timedelta, timezone
from decimal import Decimal
import requests

from .analysis import GoldBar


class HistoryProviderError(RuntimeError):
    pass


class XausDailyHistoryProvider:
    URL = "https://xaus.com/api/v1/history"

    def __init__(self, session=None, timeout=20, metadata_max_age_hours=36):
        self.session = session or requests.Session()
        self.timeout = timeout
        self.metadata_max_age = timedelta(hours=metadata_max_age_hours)

    def fetch_bars(self, limit=90, now=None):
        now = now or datetime.now(timezone.utc)
        if now.tzinfo is None or now.utcoffset() is None:
            raise ValueError("now must be timezone-aware")
        try:
            response = self.session.get(self.URL, headers={"User-Agent":"GoldMarketBot/1.0"}, timeout=self.timeout)
            response.raise_for_status()
            payload = response.json()
            state = payload.get("data_state") or {}
            if state.get("status") != "fresh":
                raise HistoryProviderError("XAUS history is not marked fresh")
            stamp = state.get("as_of") or payload.get("updated_at")
            if not stamp:
                raise HistoryProviderError("XAUS history has no freshness timestamp")
            updated = datetime.fromisoformat(str(stamp).replace("Z", "+00:00"))
            if updated.tzinfo is None:
                raise HistoryProviderError("XAUS history timestamp is not timezone-aware")
            age = now - updated
            if age < timedelta(minutes=-5) or age > self.metadata_max_age:
                raise HistoryProviderError("XAUS history metadata is future-dated or stale")
            bars, seen = [], set()
            today = now.astimezone(timezone.utc).date()
            for point in payload.get("points") or []:
                day = date.fromisoformat(str(point["d"]))
                if day in seen:
                    raise HistoryProviderError(f"Duplicate daily candle: {day}")
                seen.add(day)
                if day >= today:
                    continue
                high, low, close = (Decimal(str(point[k])) for k in ("h", "l", "c"))
                op = Decimal(str(point["o"])) if point.get("o") is not None else None
                if any(not x.is_finite() or x <= 0 for x in (high, low, close)):
                    raise HistoryProviderError(f"Invalid candle values: {day}")
                if high < max(low, close, op or close) or low > min(high, close, op or close):
                    raise HistoryProviderError(f"Inconsistent candle range: {day}")
                bars.append(GoldBar(datetime.combine(day, time(23,59), tzinfo=timezone.utc), op, high, low, close))
            bars.sort(key=lambda x: x.observed_at)
            bars = bars[-max(20, min(int(limit), 365)):]
            if len(bars) < 20:
                raise HistoryProviderError(f"Only {len(bars)} completed daily bars returned; 20 required")
            if now - bars[-1].observed_at > timedelta(hours=96):
                raise HistoryProviderError("Latest completed daily candle is older than 96 hours")
            return bars
        except HistoryProviderError:
            raise
        except (requests.RequestException, ValueError, KeyError, TypeError, ArithmeticError) as exc:
            raise HistoryProviderError(f"XAUS daily history: {exc}") from exc
