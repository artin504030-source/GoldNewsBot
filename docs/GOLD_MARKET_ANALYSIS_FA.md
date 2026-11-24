# Gold Market — Stage F: Market State Engine

- Current XAU/USD spot: XAUS /api/v1/spot (indicative mid-market, not executable).
- Historical XAU/USD: XAUS /api/v1/history (daily high/low/close; up to five years).
- Source-omitted open values remain null; no synthetic open is invented.
- Current UTC-day candle is excluded. History metadata <=36h old, latest completed candle <=96h old, at least 20 candles.
- Trend: SMA5/SMA20, latest close vs SMA20, six-session slope.
- Support/resistance: lowest low / highest high over latest 20 sessions.
- Volatility: ATR14 / latest close; HIGH >=0.80%, LOW <=0.30%, else NORMAL.
- Prior macro snapshot is fetched from previous available FRED daily observations and prior Yahoo hourly bars. If a comparison is unavailable, that driver remains UNKNOWN.
- DXY and yields are directional context only, not causal predictions. Oil, SPX and VIX remain contextual.
- Runtime: python -m apps.gold_market prints a JSON assessment; missing/stale history returns UNAVAILABLE and a warning.
- No orders, Telegram delivery, or schedules are enabled.
- Tests: python -m unittest discover -s tests -p "test_gold_market_*.py" -v
