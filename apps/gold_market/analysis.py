from __future__ import annotations
from dataclasses import dataclass
from datetime import datetime,timedelta,timezone
from decimal import Decimal
from statistics import mean
from typing import Mapping,Sequence
from .models import MarketObservation

USABLE_STATUSES={"LIVE","DELAYED","DAILY"}
DRIVER_SYMBOLS=("DXY","US10Y","US02Y","USOIL","SPX","VIX")

@dataclass(frozen=True)
class GoldBar:
    """Completed XAU/USD OHLC bar; open is optional when the source omits it."""
    observed_at:datetime
    open:Decimal|None
    high:Decimal
    low:Decimal
    close:Decimal
    def __post_init__(self):
        if self.observed_at.tzinfo is None or self.observed_at.utcoffset() is None:
            raise ValueError("GoldBar observed_at must be timezone-aware")
        vals=(self.high,self.low,self.close)
        if any(not x.is_finite() or x<=0 for x in vals): raise ValueError("GoldBar prices must be finite and positive")
        if self.open is not None and (not self.open.is_finite() or self.open<=0): raise ValueError("GoldBar open must be finite and positive")
        if self.high<max(self.low,self.close,self.open or self.close) or self.low>min(self.high,self.close,self.open or self.close):
            raise ValueError("GoldBar range is inconsistent")

@dataclass(frozen=True)
class MarketAssessment:
    as_of:datetime|None
    regime:str
    trend:str
    volatility:str
    support:Decimal|None
    resistance:Decimal|None
    atr_percent:Decimal|None
    drivers:Mapping[str,str]
    main_scenario:str
    alternative_scenario:str
    confidence:str
    event_risk:tuple[str,...]
    data_warnings:tuple[str,...]

def _usable(item): return item is not None and item.status in USABLE_STATUSES
def _sma(values): return sum(values,Decimal("0"))/Decimal(len(values))
def _true_ranges(bars):
    out=[]; prev=None
    for b in bars:
        out.append(b.high-b.low if prev is None else max(b.high-b.low,abs(b.high-prev),abs(b.low-prev)))
        prev=b.close
    return out

def _driver_context(current,previous):
    out={}
    for s in DRIVER_SYMBOLS:
        cur,old=current.get(s),previous.get(s)
        if not _usable(cur) or not _usable(old) or old.value==0:
            out[s]="UNKNOWN"; continue
        change=cur.value-old.value; pct=abs(change/old.value)*Decimal("100")
        threshold=Decimal("0.03") if s in ("US10Y","US02Y") else Decimal("0.05")
        d="FLAT" if pct<threshold else ("UP" if change>0 else "DOWN")
        if s in ("DXY","US10Y","US02Y"): out[s]={"UP":"HEADWIND_FOR_GOLD","DOWN":"SUPPORTIVE_FOR_GOLD","FLAT":"NEUTRAL"}[d]
        elif s=="USOIL": out[s]="INFLATION_CONTEXT_"+d
        elif s=="SPX": out[s]="RISK_APPETITE_"+d
        else: out[s]="RISK_AVERSION_"+("HIGHER" if d=="UP" else "LOWER" if d=="DOWN" else "STABLE")
    return out

def analyze_market(observations:Mapping[str,MarketObservation],gold_bars:Sequence[GoldBar]=(),
                   previous_observations:Mapping[str,MarketObservation]|None=None,
                   upcoming_events:Sequence[str]=(),now:datetime|None=None)->MarketAssessment:
    now=now or datetime.now(timezone.utc)
    if now.tzinfo is None or now.utcoffset() is None: raise ValueError("now must be timezone-aware")
    valid={k:v for k,v in observations.items() if _usable(v)}
    warnings=[f"{k}: missing, stale, or unavailable" for k,v in observations.items() if not _usable(v)]
    if "XAUUSD" not in valid: warnings.append("XAUUSD spot observation is not currently usable")
    bars=sorted(gold_bars,key=lambda x:x.observed_at)
    if len(bars)<20:
        warnings.append("At least 20 completed XAU/USD bars are required")
        regime=trend=volatility="UNAVAILABLE"; support=resistance=atr_percent=None
    elif bars[-1].observed_at>now+timedelta(minutes=5):
        warnings.append("Latest XAU/USD candle is future-dated")
        regime=trend=volatility="UNAVAILABLE"; support=resistance=atr_percent=None
    elif now-bars[-1].observed_at>timedelta(hours=96):
        warnings.append("Latest completed XAU/USD candle is older than 96 hours")
        regime=trend=volatility="UNAVAILABLE"; support=resistance=atr_percent=None
    else:
        closes=[b.close for b in bars]; fast,slow=_sma(closes[-5:]),_sma(closes[-20:])
        slope=closes[-1]-closes[-6]
        trend="BULLISH" if fast>slow and closes[-1]>slow and slope>0 else ("BEARISH" if fast<slow and closes[-1]<slow and slope<0 else "RANGE")
        recent=bars[-20:]; support=min(b.low for b in recent); resistance=max(b.high for b in recent)
        atr=Decimal(str(mean(_true_ranges(bars)[-14:]))); atr_percent=atr/closes[-1]*Decimal("100")
        volatility="HIGH" if atr_percent>=Decimal("0.80") else ("LOW" if atr_percent<=Decimal("0.30") else "NORMAL")
        regime="EVENT_VOLATILITY" if volatility=="HIGH" else trend
    drivers=_driver_context(valid,previous_observations or {})
    comparable=sum(v!="UNKNOWN" for v in drivers.values())
    confidence="HIGH" if trend!="UNAVAILABLE" and len(valid)>=5 and comparable>=4 else ("MEDIUM" if trend!="UNAVAILABLE" and len(valid)>=3 else "LOW")
    scenarios={
      "BULLISH":("Continuation is the working scenario while price holds above recent structure.","A daily close below recent support invalidates the bullish structure."),
      "BEARISH":("Downside continuation is the working scenario while price remains below recent structure.","A daily close above recent resistance invalidates the bearish structure."),
      "RANGE":("Range conditions remain the working scenario until a confirmed close breaks the range.","A sustained close outside the recent range signals a possible regime change.")}
    main,alt=scenarios.get(trend,("No directional scenario: validated XAU/USD history is insufficient or stale.","Reassess when at least 20 fresh completed XAU/USD bars are available."))
    stamps=[v.observed_at for v in valid.values()]
    return MarketAssessment(max(stamps) if stamps else None,regime,trend,volatility,support,resistance,atr_percent,drivers,main,alt,confidence,tuple(upcoming_events),tuple(warnings))
