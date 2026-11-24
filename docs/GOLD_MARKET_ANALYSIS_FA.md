# Gold Market — Stage F: Market State Engine

## Scope
This stage adds a deterministic analysis layer. It does not send Telegram
messages, schedule hourly jobs, issue entries, or execute trades.

## Input contract
- Validated `MarketObservation` snapshots from the collector.
- Completed XAUUSD OHLC bars supplied by a history-capable provider.
- An optional previous snapshot for cross-market change comparisons.
- Optional upcoming-event labels from a future calendar integration.

## Analysis rules
- Requires at least 20 completed XAUUSD bars before classifying trend,
  support, resistance, or volatility. Otherwise these fields are UNAVAILABLE.
- Trend is classified from the 5-bar and 20-bar simple moving averages,
  the latest close relative to the 20-bar average, and the six-bar slope.
- Volatility uses a 14-bar average true range as a percentage of the latest
  close: HIGH at 0.80% or above, LOW at 0.30% or below, NORMAL otherwise.
- Recent support and resistance are the lowest low and highest high of the
  latest 20 completed bars.
- Cross-market drivers require both current and previous usable observations.
  DXY and Treasury yields are contextual headwinds/supports only; oil, SPX,
  and VIX are context labels, not causal predictors.
- Stale or unavailable observations are never silently promoted to usable data.
- Confidence is reduced when candle history, current observations, or
  comparable previous snapshots are missing.

## Important current limitation
Stage E verifies current XAUUSD spot and daily/delayed macro snapshots, but it
does not yet provide a historical XAUUSD OHLC candle series. Therefore the
engine safely returns UNAVAILABLE for price structure until a history provider
and its freshness tests are added. No trend or support/resistance is fabricated.

## Acceptance tests
Run:
```bash
python -m unittest discover -s tests -p "test_gold_market_*.py" -v
```
The engine must cover bullish structure, insufficient history, stale data,
driver context, missing comparisons, event context, and invalid candle data.
