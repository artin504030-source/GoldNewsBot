"""Canonical indicator registry; data-source mapping is defined in Stage B."""
from dataclasses import dataclass


@dataclass(frozen=True)
class IndicatorSpec:
    symbol: str
    display_name: str
    description: str


INDICATORS: tuple[IndicatorSpec, ...] = (
    IndicatorSpec("XAUUSD", "Gold Spot", "Primary market being evaluated"),
    IndicatorSpec("DXY", "US Dollar Index", "Broad US dollar strength"),
    IndicatorSpec("US10Y", "US 10-Year Yield", "Longer-term Treasury yield"),
    IndicatorSpec("US02Y", "US 2-Year Yield", "Shorter-term Treasury yield"),
    IndicatorSpec("USOIL", "WTI Crude Oil", "Oil price and possible inflation context"),
    IndicatorSpec("SPX", "S&P 500", "US equity-market risk appetite"),
    IndicatorSpec("VIX", "CBOE Volatility Index", "US equity implied volatility"),
)

INDICATOR_IDS = tuple(item.symbol for item in INDICATORS)
