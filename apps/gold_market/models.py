"""Normalized market observation with explicit source and freshness label."""
from dataclasses import dataclass
from datetime import datetime,timezone
from decimal import Decimal
from typing import Literal
IndicatorId=Literal["XAUUSD","DXY","US10Y","US02Y","USOIL","SPX","VIX"]
DataStatus=Literal["LIVE","DELAYED","DAILY","STALE","UNAVAILABLE"]
@dataclass(frozen=True)
class MarketObservation:
    indicator:IndicatorId
    value:Decimal
    observed_at:datetime
    source:str
    unit:str=""
    status:DataStatus="UNAVAILABLE"
    note:str=""
    def __post_init__(self):
        if not self.value.is_finite(): raise ValueError("Market value must be finite")
        if self.observed_at.tzinfo is None: raise ValueError("observed_at must be timezone-aware")
        if not self.source.strip(): raise ValueError("source must not be empty")
    @property
    def age_seconds(self):
        return max(0.0,(datetime.now(timezone.utc)-self.observed_at.astimezone(timezone.utc)).total_seconds())
