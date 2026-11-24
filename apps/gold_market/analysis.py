"""Deterministic, data-first market-state assessment for Gold Market.

This module deliberately does not create trading entries or causal claims.
It only classifies supplied XAUUSD candles and describes cross-market context.
"""
from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone
from decimal import Decimal
from statistics import mean
from typing import Mapping, Sequence

from .models import MarketObservation

USABLE_STATUSES = {"LIVE", "DELAYED", "DAILY"}
DRIVER_SYMBOLS = ("DXY", "US10Y", "US02Y", "USOIL", "SPX", "VIX")


@dataclass(frozen=True)
class GoldBar:
    """A completed XAUUSD OHLC bar with a timezone-aware close time."""

    observed_at: datetime
    open: Decimal
    high: Decimal
    low: Decimal
    close: Decimal

    def __post_init__(self) -> None:
        if self.observed_at.tzinfo is None or self.observed_at.utcoffset() is None:
            raise ValueError("GoldBar observed_at must be timezone-aware")
        values = (self.open, self.high, self.low, self.close)
        if any(not value.is_finite() or value <= 0 for value in values):
            raise ValueError("GoldBar prices must be finite and positive")
        if self.high < max(self.open, self.close, self.low):
            raise ValueError("GoldBar high is inconsistent")
        if self.low > min(self.open, self.close, self.high):
            raise ValueError("GoldBar low is inconsistent")


@dataclass(frozen=True)
class MarketAssessment:
    as_of: datetime | None
    regime: str
    trend: str
    volatility: str
    support: Decimal | None
    resistance: Decimal | None
    atr_percent: Decimal | None
    drivers: Mapping[str, str]
    main_scenario: str
    alternative_scenario: str
    confidence: str
    event_risk: tuple[str, ...]
    data_warnings: tuple[str, ...]


def _usable(item: MarketObservation | None) -> bool:
    return item is not None and item.status in USABLE_STATUSES


def _sma(values: Sequence[Decimal]) -> Decimal:
    return sum(values, Decimal("0")) / Decimal(len(values))


def _true_ranges(bars: Sequence[GoldBar]) -> list[Decimal]:
    ranges: list[Decimal] = []
    previous_close: Decimal | None = None
    for bar in bars:
        if previous_close is None:
            ranges.append(bar.high - bar.low)
        else:
            ranges.append(max(
                bar.high - bar.low,
                abs(bar.high - previous_close),
                abs(bar.low - previous_close),
            ))
        previous_close = bar.close
    return ranges


def _driver_context(
    current: Mapping[str, MarketObservation],
    previous: Mapping[str, MarketObservation],
) -> dict[str, str]:
    result: dict[str, str] = {}
    for symbol in DRIVER_SYMBOLS:
        now_item = current.get(symbol)
        old_item = previous.get(symbol)
        if not _usable(now_item) or not _usable(old_item):
            result[symbol] = "UNKNOWN"
            continue
        assert now_item is not None and old_item is not None
        if old_item.value == 0:
            result[symbol] = "UNKNOWN"
            continue
        change = now_item.value - old_item.value
        pct = abs(change / old_item.value) * Decimal("100")
        threshold = Decimal("0.03") if symbol in ("US10Y", "US02Y") else Decimal("0.05")
        if pct < threshold:
            direction = "FLAT"
        else:
            direction = "UP" if change > 0 else "DOWN"

        if symbol == "DXY":
            meaning = {"UP": "HEADWIND_FOR_GOLD", "DOWN": "SUPPORTIVE_FOR_GOLD", "FLAT": "NEUTRAL"}[direction]
        elif symbol in ("US10Y", "US02Y"):
            meaning = {"UP": "HEADWIND_FOR_GOLD", "DOWN": "SUPPORTIVE_FOR_GOLD", "FLAT": "NEUTRAL"}[direction]
        elif symbol == "USOIL":
            meaning = "INFLATION_CONTEXT_" + direction
        elif symbol == "SPX":
            meaning = "RISK_APPETITE_" + direction
        else:
            meaning = "RISK_AVERSION_" + ("HIGHER" if direction == "UP" else "LOWER" if direction == "DOWN" else "STABLE")
        result[symbol] = meaning
    return result


def analyze_market(
    observations: Mapping[str, MarketObservation],
    gold_bars: Sequence[GoldBar] = (),
    previous_observations: Mapping[str, MarketObservation] | None = None,
    upcoming_events: Sequence[str] = (),
    now: datetime | None = None,
) -> MarketAssessment:
    """Build a reproducible market-state assessment from validated inputs.

    At least 20 completed gold bars are required before trend/levels are
    classified. Missing history produces UNAVAILABLE rather than a guess.
    """
    now = now or datetime.now(timezone.utc)
    if now.tzinfo is None or now.utcoffset() is None:
        raise ValueError("now must be timezone-aware")

    valid = {
        key: item for key, item in observations.items()
        if _usable(item)
    }
    warnings: list[str] = []
    for key, item in observations.items():
        if not _usable(item):
            warnings.append(f"{key}: missing, stale, or unavailable")
    if "XAUUSD" not in valid:
        warnings.append("XAUUSD spot observation is not currently usable")

    bars = sorted(gold_bars, key=lambda item: item.observed_at)
    if len(bars) < 20:
        warnings.append("At least 20 completed XAUUSD bars are required for structure analysis")
        regime = trend = volatility = "UNAVAILABLE"
        support = resistance = atr_percent = None
    else:
        closes = [bar.close for bar in bars]
        fast = _sma(closes[-5:])
        slow = _sma(closes[-20:])
        slope = closes[-1] - closes[-6]
        if fast > slow and closes[-1] > slow and slope > 0:
            trend = "BULLISH"
        elif fast < slow and closes[-1] < slow and slope < 0:
            trend = "BEARISH"
        else:
            trend = "RANGE"

        recent = bars[-20:]
        support = min(bar.low for bar in recent)
        resistance = max(bar.high for bar in recent)
        atr = Decimal(str(mean(_true_ranges(bars)[-14:])))
        atr_percent = (atr / closes[-1]) * Decimal("100")
        if atr_percent >= Decimal("0.80"):
            volatility = "HIGH"
        elif atr_percent <= Decimal("0.30"):
            volatility = "LOW"
        else:
            volatility = "NORMAL"
        regime = "EVENT_VOLATILITY" if volatility == "HIGH" else trend

    drivers = _driver_context(valid, previous_observations or {})
    comparable = sum(value != "UNKNOWN" for value in drivers.values())
    if len(bars) >= 20 and len(valid) >= 5 and comparable >= 4:
        confidence = "HIGH"
    elif len(bars) >= 20 and len(valid) >= 3:
        confidence = "MEDIUM"
    else:
        confidence = "LOW"

    if trend == "BULLISH":
        main = "Continuation remains the working scenario while price holds above the recent structure."
        alternative = "A close below the recent support invalidates the bullish structure."
    elif trend == "BEARISH":
        main = "Downside continuation remains the working scenario while price stays below the recent structure."
        alternative = "A close above the recent resistance invalidates the bearish structure."
    elif trend == "RANGE":
        main = "Range conditions remain the working scenario until a confirmed close breaks the recent range."
        alternative = "A sustained close outside the recent range signals a possible regime change."
    else:
        main = "No primary directional scenario: validated XAUUSD candle history is insufficient."
        alternative = "Reassess after at least 20 completed XAUUSD bars are available."

    timestamps = [item.observed_at for item in valid.values()]
    as_of = min(timestamps) if not timestamps else max(timestamps)
    return MarketAssessment(
        as_of=as_of,
        regime=regime,
        trend=trend,
        volatility=volatility,
        support=support,
        resistance=resistance,
        atr_percent=atr_percent,
        drivers=drivers,
        main_scenario=main,
        alternative_scenario=alternative,
        confidence=confidence,
        event_risk=tuple(upcoming_events),
        data_warnings=tuple(warnings),
    )
