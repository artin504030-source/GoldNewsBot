from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone

from .models import IndicatorId, MarketObservation
from .providers import FredProvider, YahooChartProvider, ProviderError
from .validation import validate_observation

ALL_INDICATORS: tuple[IndicatorId, ...] = ("XAUUSD", "DXY", "US10Y", "US02Y", "USOIL", "SPX", "VIX")


@dataclass(frozen=True)
class CollectionResult:
    indicator: IndicatorId
    observation: MarketObservation | None
    error: str | None = None


class MarketDataCollector:
    def __init__(self, fred: FredProvider, yahoo: YahooChartProvider):
        self.fred = fred
        self.yahoo = yahoo

    def collect_one(self, indicator: IndicatorId) -> CollectionResult:
        try:
            item = self.yahoo.fetch(indicator) if indicator in ("XAUUSD", "DXY") else self.fred.fetch(indicator)
            checked = validate_observation(item, now=datetime.now(timezone.utc))
            return CollectionResult(indicator, checked)
        except (ProviderError, ValueError) as exc:
            return CollectionResult(indicator, None, str(exc))

    def collect_all(self) -> dict[IndicatorId, CollectionResult]:
        return {symbol: self.collect_one(symbol) for symbol in ALL_INDICATORS}

    # Backward-compatible names used by the Stage C diagnostic entry point.
    collect_on = collect_one
    collect_all_results = collect_all
