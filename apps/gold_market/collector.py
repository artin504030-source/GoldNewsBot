from __future__ import annotations
from dataclasses import dataclass
from .models import IndicatorId,MarketObservation
from .providers import FredProvider,YahooChartProvider,ProviderError
ALL_INDICATORS:tuple[IndicatorId,...]=("XAUUSD","DXY","US10Y","US02Y","USOIL","SPX","VIX")
@dataclass(frozen=True)
class CollectionResult:
    indicator:IndicatorId
    observation:MarketObservation|None
    error:str|None=None
class MarketDataCollector:
    def __init__(self,fred:FredProvider,yahoo:YahooChartProvider): self.fred=fred; self.yahoo=yahoo
    def collect_one(self,indicator:IndicatorId)->CollectionResult:
        try:
            item=self.yahoo.fetch(indicator) if indicator in ("XAUUSD","DXY") else self.fred.fetch(indicator)
            return CollectionResult(indicator,item)
        except ProviderError as e: return CollectionResult(indicator,None,str(e))
    def collect_all(self)->dict[IndicatorId,CollectionResult]:
        return {s:self.collect_one(s) for s in ALL_INDICATORS}
