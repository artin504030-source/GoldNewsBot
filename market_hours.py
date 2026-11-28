"""Shared XAUUSD weekend trading-hours detection (New York time)."""
from __future__ import annotations

from datetime import datetime, time
from zoneinfo import ZoneInfo

NEW_YORK = ZoneInfo("America/New_York")
WEEKEND_REOPEN = time(17, 0)


def market_is_closed(now: datetime) -> bool:
    """Gold spot is normally closed Fri 17:00 NY through Sun 17:00 NY."""
    if now.tzinfo is None:
        raise ValueError("now must be timezone-aware")
    local = now.astimezone(NEW_YORK)
    if local.weekday() == 4:
        return local.time().replace(tzinfo=None) >= WEEKEND_REOPEN
    if local.weekday() == 5:
        return True
    if local.weekday() == 6:
        return local.time().replace(tzinfo=None) < WEEKEND_REOPEN
    return False


def next_reopen_text(now: datetime) -> str:
    if now.tzinfo is None:
        raise ValueError("now must be timezone-aware")
    local = now.astimezone(NEW_YORK)
    if local.weekday() == 6:
        return "امروز ساعت 17:00 به وقت نیویورک"
    return "یکشنبه ساعت 17:00 به وقت نیویورک"


def weekend_closure_message(now: datetime, bot_label: str) -> str:
    local = now.astimezone(NEW_YORK)
    return (
        f"🔒 <b>وضعیت بازار طلا | {bot_label}</b>\n"
        "⛔ بازار جهانی طلا (XAU/USD) در تعطیلی آخر هفته قرار دارد.\n"
        f"🕒 زمان بررسی: {local:%Y-%m-%d %H:%M} نیویورک\n"
        f"🔔 زمان بازگشایی معمول: {next_reopen_text(now)}\n"
        "ℹ️ در زمان تعطیلی، قیمت تازه و قابل معامله منتشر نمی‌شود. "
        "پس از بازگشایی، گزارش‌های عادی از سر گرفته می‌شوند."
    )
