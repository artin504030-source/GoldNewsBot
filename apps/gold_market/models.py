"""Shared, provider-neutral data models for market observations."""
from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone
from decimal import Decimal
from typing import Literal


IndicatorId = Literal["XAUUSD", "DXY", "US10Y", "US02Y", "USOIL", "SPX", "VIX"]


@dataclass(frozen=True)
class MarketObservation:
    indicator: IndicatorId
    value: Decimal
    observed_at: datetime
    source: str
    unit: str = ""

    def __post_init__(self) -> None:
        if self.value.is_nan() or self.value.is_infinite():
            raise ValueError("Market value must be finite")
        if self.observed_at.tzinfo is None:
            raise ValueError("observed_at must be timezone-aware")
        if not self.source.strip():
            raise ValueError("source must not be empty")

    @property
    def age_seconds(self) -> float:
        now = datetime.now(timezone.utc)
        observed = self.observed_at.astimezone(timezone.utc)
        return max(0.0, (now - observed).total_seconds())
