# Gold Market — Stage F completed: Market State Engine

- Spot: XAUS /api/v1/spot (indicative mid-market, not executable).
- History: XAUS /api/v1/history (daily XAU/USD high/low/close; up to five years).
- Open is optional when source omits it; no synthetic open is invented.
- Current UTC-day candle is excluded until complete.
- History metadata freshness <=36 hours; latest completed candle <=96 hours.
- At least 20 completed daily candles are required.
- Trend: SMA5/SMA20, latest close vs SMA20, and six-session slope.
- Support/resistance: 20-session low/high.
- Volatility: ATR14 / latest close; HIGH >=0.80%, LOW <=0.30%, else NORMAL.
- DXY/yields are context only, not causal predictions. Oil, SPX and VIX remain context labels.
- Runtime: python -m apps.gold_market prints a JSON assessment; missing/stale history returns UNAVAILABLE and a warning.
- No orders, Telegram delivery, or schedules are enabled.
- Tests: python -m unittest discover -s tests -p "test_gold_market_*.py" -v
