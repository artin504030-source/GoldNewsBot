import json
from decimal import Decimal
from .config import Settings
from .providers import FredProvider,XausSpotProvider,YahooChartProvider
from .history import XausDailyHistoryProvider
from .collector import MarketDataCollector

def _json_value(value):
    if isinstance(value,Decimal): return str(value)
    if hasattr(value,"isoformat"): return value.isoformat()
    raise TypeError(f"Unsupported JSON value: {type(value).__name__}")

def main():
    settings=Settings.from_env()
    collector=MarketDataCollector(FredProvider(settings.fred_api_key),YahooChartProvider(),XausSpotProvider(),XausDailyHistoryProvider())
    report=collector.assess_market()
    keys=("as_of","regime","trend","volatility","support","resistance","atr_percent","drivers","main_scenario","alternative_scenario","confidence","event_risk","data_warnings")
    print(json.dumps({k:getattr(report,k) for k in keys},default=_json_value,ensure_ascii=False,indent=2))
    return 0 if report.trend!="UNAVAILABLE" else 1

if __name__=="__main__": raise SystemExit(main())
