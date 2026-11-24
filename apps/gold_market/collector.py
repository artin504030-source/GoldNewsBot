from __future__ import annotations
from dataclasses import dataclass,replace
from datetime import datetime,timezone
from .analysis import analyze_market
from .history import HistoryProviderError,XausDailyHistoryProvider
from .models import IndicatorId,MarketObservation
from .providers import FredProvider,ProviderError,XausSpotProvider,YahooChartProvider
from .validation import validate_observation

ALL_INDICATORS:tuple[IndicatorId,...]=("XAUUSD","DXY","US10Y","US02Y","USOIL","SPX","VIX")
@dataclass(frozen=True)
class CollectionResult:
    indicator:IndicatorId
    observation:MarketObservation|None
    error:str|None=None

class MarketDataCollector:
    def __init__(self,fred:FredProvider,yahoo:YahooChartProvider,xau:XausSpotProvider|None=None,history:XausDailyHistoryProvider|None=None):
        self.fred,self.yahoo,self.xau=fred,yahoo,xau
        self.history=history or XausDailyHistoryProvider()
    def collect_one(self,indicator:IndicatorId)->CollectionResult:
        try:
            if indicator=="XAUUSD" and self.xau is not None: item=self.xau.fetch(indicator)
            elif indicator in ("XAUUSD","DXY","USOIL"): item=self.yahoo.fetch(indicator)
            else: item=self.fred.fetch(indicator)
            return CollectionResult(indicator,validate_observation(item,now=datetime.now(timezone.utc)))
        except (ProviderError,ValueError) as exc: return CollectionResult(indicator,None,str(exc))
    def collect_all(self): return {s:self.collect_one(s) for s in ALL_INDICATORS}
    def assess_market(self,previous_observations=None,upcoming_events=(),now=None):
        now=now or datetime.now(timezone.utc); results=self.collect_all()
        observations={k:v.observation for k,v in results.items() if v.observation is not None}
        try: bars=self.history.fetch_bars(now=now); error=None
        except (HistoryProviderError,ValueError) as exc: bars, error=(),str(exc)
        report=analyze_market(observations,bars,previous_observations,upcoming_events,now)
        if error: report=replace(report,data_warnings=report.data_warnings+(f"XAUUSD history unavailable: {error}",))
        return report
    collect_on=collect_one
    collect_all_results=collect_all
