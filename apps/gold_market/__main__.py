import json
from .config import Settings
from .providers import FredProvider,YahooChartProvider
from .collector import MarketDataCollector
def main():
    s=Settings.from_env(); results=MarketDataCollector(FredProvider(s.fred_api_key),YahooChartProvider()).collect_all()
    out={}
    for k,r in results.items():
        if r.observation is None: out[k]={"status":"UNAVAILABLE","error":r.error}
        else:
            x=r.observation; out[k]={"value":str(x.value),"unit":x.unit,"status":x.status,"observed_at":x.observed_at.isoformat(),"source":x.source,"note":x.note}
    print(json.dumps(out,ensure_ascii=False,indent=2))
    return 0 if all(r.observation is not None for r in results.values()) else 1
if __name__=="__main__": raise SystemExit(main())
