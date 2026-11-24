# Gold Market data sources

The Gold Market collector uses a hybrid source policy. Each observation carries
its own source, observation timestamp, and freshness label.

| Indicator | Provider | Instrument / series | Label |
|---|---|---|---|
| XAUUSD | XAUS Gold Data API | XAU/USD spot, indicative mid-market | LIVE or STALE according to provider metadata |
| DXY | Yahoo Finance | DX-Y.NYB | DELAYED |
| US10Y | FRED | DGS10 | DAILY |
| US02Y | FRED | DGS2 | DAILY |
| USOIL | Yahoo Finance | CL=F continuous front-month WTI futures | DELAYED |
| SPX | FRED | SP500 | DAILY |
| VIX | FRED | VIXCLS | DAILY |

XAUS spot endpoint: https://xaus.com/api/v1/spot?compact=1
It is keyless and intended for reasonable use; the provider requests a minimum
60-second cache interval. Gold Market runs hourly. XAUS quotes are indicative
mid-market prices and are not broker-executable prices. Its `data_state` and
observation timestamp are checked; stale provider data remains labelled STALE.

Yahoo's `CL=F` is a continuous front-month WTI futures quote, not the EIA/FRED
daily WTI spot series. It is explicitly labelled DELAYED and the report note
identifies it as futures data.

FRED values are daily observations, not live quotes. The collector preserves
their observation dates and applies the freshness validator. A missing or old
FRED observation is never relabelled as live.

FRED attribution notice:
“This product uses the FRED® API but is not endorsed or certified by the
Federal Reserve Bank of St. Louis.”

XAUS source documentation: https://xaus.com/api/
Yahoo Finance symbols: https://finance.yahoo.com/quote/CL%3DF/
