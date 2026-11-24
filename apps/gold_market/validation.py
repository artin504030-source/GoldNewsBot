"""Freshness and plausibility checks for normalized market observations."""
from dataclasses import replace
from datetime import datetime, timedelta, timezone

# Conservative guardrails catch malformed feeds, not normal market volatility.
VALUE_BOUNDS = {
    "XAUUSD": (100, 20000),
    "DXY": (1, 300),
    "US10Y": (-5, 30),
    "US02Y": (-5, 30),
    "USOIL": (0, 1000),
    "SPX": (100, 100000),
    "VIX": (0, 200),
}
MAX_AGE = {
    "DELAYED": timedelta(hours=6),
    # Daily series can have weekend and market-holiday gaps.
    "DAILY": timedelta(days=5),
    "LIVE": timedelta(minutes=30),
}
FUTURE_TOLERANCE = timedelta(minutes=5)


def validate_observation(observation, now=None):
    """Return a checked observation; reject impossible values/timestamps.

    Old but otherwise valid observations are retained and explicitly marked STALE.
    """
    now = now or datetime.now(timezone.utc)
    if now.tzinfo is None or now.utcoffset() is None:
        raise ValueError("now must be timezone-aware")
    observed_at = observation.observed_at
    if observed_at.tzinfo is None or observed_at.utcoffset() is None:
        raise ValueError("observation timestamp must be timezone-aware")
    now_utc = now.astimezone(timezone.utc)
    observed_utc = observed_at.astimezone(timezone.utc)
    if observed_utc > now_utc + FUTURE_TOLERANCE:
        raise ValueError("observation timestamp is too far in the future")

    bounds = VALUE_BOUNDS.get(observation.indicator)
    if bounds is None:
        raise ValueError(f"unknown indicator: {observation.indicator}")
    if not bounds[0] <= observation.value <= bounds[1]:
        raise ValueError(
            f"{observation.indicator} value {observation.value} outside {bounds}"
        )

    max_age = MAX_AGE.get(observation.status)
    if max_age is not None and now_utc - observed_utc > max_age:
        note = (observation.note + "; " if observation.note else "") + "Data is older than the freshness limit"
        return replace(observation, status="STALE", note=note)
    return observation
