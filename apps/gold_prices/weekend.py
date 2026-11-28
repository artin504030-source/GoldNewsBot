"""Send one Gold Prices weekend-closure notice per New York calendar day."""
from __future__ import annotations

from datetime import datetime, timezone
from zoneinfo import ZoneInfo

from market_hours import market_is_closed, weekend_closure_message
from .bot import load_state, save_state, telegram_send

NEW_YORK = ZoneInfo("America/New_York")


def process_weekend_notice(now: datetime, state: dict, sender=telegram_send) -> bool:
    if not market_is_closed(now):
        return False
    state.setdefault("sent", {})
    day_key = now.astimezone(NEW_YORK).date().isoformat()
    if state["sent"].get("weekend_closed") == day_key:
        return False
    sender(weekend_closure_message(now, "Gold Prices"))
    state["sent"]["weekend_closed"] = day_key
    return True


def main() -> int:
    now = datetime.now(timezone.utc)
    state = load_state()
    sent = process_weekend_notice(now, state)
    save_state(state)
    print("Weekend closure notice sent." if sent else "No weekend notice due.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
