import json
from decimal import Decimal
from .config import Settings
from .providers import FredProvider,XausSpotProvider,YahooChartProvider
from .history import XausDailyHistoryProvider
from .collector import MarketDataCollector
from .report import render_market_report


def _json_value(value):
    if isinstance(value,Decimal): return str(value)
    if hasattr(value,"isoformat"): return value.isoformat()
    raise TypeError(f"Unsupported JSON value: {type(value).__name__}")


def main():
    settings=Settings.from_env()
    collector=MarketDataCollector(
        FredProvider(settings.fred_api_key),YahooChartProvider(),
        XausSpotProvider(),XausDailyHistoryProvider()
    )
    assessment,observations,results=collector.collect_report_snapshot()
    report=render_market_report(assessment,observations)
    print(report)
    print("\n--- MACHINE READABLE ASSESSMENT ---")
    keys=("as_of","regime","trend","volatility","support","resistance","atr_percent","drivers",
          "main_scenario","alternative_scenario","confidence","event_risk","data_warnings")
    print(json.dumps({k:getattr(assessment,k) for k in keys},default=_json_value,ensure_ascii=False,indent=2))
    return 0 if assessment.trend!="UNAVAILABLE" else 1


if __name__=="__main__":
    raise SystemExit(main())
