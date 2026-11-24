import json

from .config import Settings
from .providers import FredProvider, XausSpotProvider, YahooChartProvider
from .collector import MarketDataCollector


def main():
    settings = Settings.from_env()
    results = MarketDataCollector(
        FredProvider(settings.fred_api_key),
        YahooChartProvider(),
        XausSpotProvider(),
    ).collect_all()

    output = {}
    for indicator, result in results.items():
        if result.observation is None:
            output[indicator] = {
                "status": "UNAVAILABLE",
                "error": result.error,
            }
        else:
            item = result.observation
            output[indicator] = {
                "value": str(item.value),
                "unit": item.unit,
                "status": item.status,
                "observed_at": item.observed_at.isoformat(),
                "source": item.source,
                "note": item.note,
            }

    print(json.dumps(output, ensure_ascii=False, indent=2))
    return 0 if all(
        result.observation is not None
        for result in results.values()
    ) else 1


if __name__ == "__main__":
    raise SystemExit(main())
