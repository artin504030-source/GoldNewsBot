from __future__ import annotations

from datetime import datetime, timezone
from decimal import Decimal
import requests

from .models import MarketObservation


FRED_SERIES = {
    "US10Y": ("DGS10", "percent"),
    "US02Y": ("DGS2", "percent"),
    "SPX": ("SP500", "index"),
    "VIX": ("VIXCLS", "index"),
}


class ProviderError(RuntimeError):
    pass


class FredProvider:
    URL = "https://api.stlouisfed.org/fred/series/observations"

    def __init__(self, api_key, session=None, timeout=15):
        self.api_key = (api_key or "").strip()
        self.session = session or requests.Session()
        self.timeout = timeout

    def fetch(self, indicator):
        if indicator not in FRED_SERIES:
            raise ProviderError(f"No FRED series for {indicator}")
        if not self.api_key:
            raise ProviderError("FRED_API_KEY is not configured")
        series_id, unit = FRED_SERIES[indicator]
        try:
            response = self.session.get(
                self.URL,
                params={
                    "series_id": series_id,
                    "api_key": self.api_key,
                    "file_type": "json",
                    "sort_order": "desc",
                    "limit": 10,
                },
                timeout=self.timeout,
            )
            response.raise_for_status()
            for row in response.json().get("observations", []):
                if row.get("value") in (None, "", "."):
                    continue
                observed_at = datetime.strptime(
                    row["date"], "%Y-%m-%d"
                ).replace(tzinfo=timezone.utc)
                return MarketObservation(
                    indicator,
                    Decimal(str(row["value"])),
                    observed_at,
                    f"FRED:{series_id}",
                    unit,
                    "DAILY",
                    "آخرین مشاهده روزانه؛ قیمت لحظه‌ای نیست.",
                )
        except (requests.RequestException, ValueError, KeyError) as exc:
            raise ProviderError(f"FRED {indicator}: {exc}") from exc
        raise ProviderError(f"No usable FRED observation for {indicator}")


class XausSpotProvider:
    """Keyless XAU/USD spot feed. Quotes are indicative, not executable."""

    URL = "https://xaus.com/api/v1/spot"

    def __init__(self, session=None, timeout=15):
        self.session = session or requests.Session()
        self.timeout = timeout

    def fetch(self, indicator="XAUUSD"):
        if indicator != "XAUUSD":
            raise ProviderError(f"XAUS does not provide {indicator}")
        try:
            response = self.session.get(
                self.URL,
                params={"compact": "1"},
                headers={"User-Agent": "GoldMarketBot/1.0"},
                timeout=self.timeout,
            )
            response.raise_for_status()
            payload = response.json()
            state = payload.get("data_state") or {}
            state_status = state.get("status")
            if state_status not in ("fresh", "stale"):
                raise ProviderError("XAUS returned no usable spot quote")

            xau = payload.get("xau") or {}
            price = xau.get("price") or payload.get("spot_usd_oz")
            timestamp = state.get("as_of") or payload.get("updated_at")
            if price is None or not timestamp:
                raise ProviderError("XAUS response is missing price or timestamp")

            observed_at = datetime.fromisoformat(
                str(timestamp).replace("Z", "+00:00")
            )
            if observed_at.tzinfo is None:
                raise ProviderError("XAUS timestamp is not timezone-aware")

            status = "LIVE" if state_status == "fresh" else "STALE"
            source = state.get("source") or "XAUS"
            note = (
                "قیمت اسپاتِ شاخصی و غیرقابل‌معامله؛ زمان مشاهده جداگانه ثبت شده است."
                if status == "LIVE"
                else "آخرین قیمت ذخیره‌شده؛ منبع آن را تازه اعلام نکرده است."
            )
            return MarketObservation(
                "XAUUSD",
                Decimal(str(price)),
                observed_at,
                f"XAUS:{source}",
                "USD/oz",
                status,
                note,
            )
        except ProviderError:
            raise
        except (requests.RequestException, ValueError, KeyError, TypeError) as exc:
            raise ProviderError(f"XAUS XAUUSD: {exc}") from exc


class YahooChartProvider:
    URL = "https://query1.finance.yahoo.com/v8/finance/chart"
    SYMBOLS = {
        # Kept for backwards-compatible direct provider tests; production
        # Gold Market collection uses the dedicated XAUS spot provider.
        "XAUUSD": "XAUUSD=X",
        "DXY": "DX-Y.NYB",
        # Continuous front-month WTI futures, not the EIA/FRED spot series.
        "USOIL": "CL=F",
    }

    def __init__(self, session=None, timeout=15):
        self.session = session or requests.Session()
        self.timeout = timeout

    def fetch(self, indicator):
        if indicator not in self.SYMBOLS:
            raise ProviderError(f"No Yahoo symbol for {indicator}")
        symbol = self.SYMBOLS[indicator]
        try:
            response = self.session.get(
                f"{self.URL}/{symbol}",
                params={"range": "5d", "interval": "1h"},
                headers={"User-Agent": "Mozilla/5.0"},
                timeout=self.timeout,
            )
            response.raise_for_status()
            result = response.json()["chart"]["result"][0]
            timestamps = result.get("timestamp") or []
            closes = result["indicators"]["quote"][0].get("close") or []
            points = [
                (timestamp, close)
                for timestamp, close in zip(timestamps, closes)
                if close is not None
            ]
            if not points:
                raise ProviderError(f"No Yahoo close for {indicator}")

            timestamp, value = points[-1]
            unit = {
                "XAUUSD": "USD/oz",
                "DXY": "index",
                "USOIL": "USD/barrel",
            }[indicator]
            note = (
                "قرارداد آتی پیوسته WTI؛ قیمت اسپات نفت نیست. خوراک با تأخیر."
                if indicator == "USOIL"
                else "خوراک غیررسمی؛ تأخیر دقیق تضمین نشده است."
            )
            return MarketObservation(
                indicator,
                Decimal(str(value)),
                datetime.fromtimestamp(int(timestamp), tz=timezone.utc),
                f"Yahoo Finance:{symbol}",
                unit,
                "DELAYED",
                note,
            )
        except ProviderError:
            raise
        except (
            requests.RequestException,
            ValueError,
            KeyError,
            IndexError,
            TypeError,
        ) as exc:
            raise ProviderError(f"Yahoo {indicator}: {exc}") from exc
