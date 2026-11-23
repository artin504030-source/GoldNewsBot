"""Gold Prices Telegram bot: free spot providers, session snapshots and gap reporting."""
from __future__ import annotations

import json
import os
import sys
import urllib.parse
import urllib.request
from datetime import datetime, timedelta, timezone
from pathlib import Path
from zoneinfo import ZoneInfo

UTC = timezone.utc
NY = ZoneInfo("America/New_York")
SYDNEY = ZoneInfo("Australia/Sydney")
XAUS_SPOT = "https://xaus.com/api/v1/spot?compact=1"
XAUS_INTRADAY = "https://xaus.com/api/v1/intraday?symbol=xau&hours=2"
BACKUP_SPOT = "https://api.gold-api.com/price/XAU"
MAX_AGE_SECONDS = 300
STATE_PATH = Path(os.getenv("GOLD_PRICES_STATE", "apps/gold_prices/state.json"))


def parse_time(value: str) -> datetime:
    dt = datetime.fromisoformat(value.replace("Z", "+00:00"))
    if dt.tzinfo is None:
        raise ValueError("Provider timestamp must include timezone")
    return dt.astimezone(UTC)


def http_json(url: str, timeout: int = 15) -> dict:
    request = urllib.request.Request(url, headers={"User-Agent": "GoldPricesBot/1.0"})
    with urllib.request.urlopen(request, timeout=timeout) as response:
        if response.status != 200:
            raise RuntimeError(f"HTTP {response.status}")
        return json.loads(response.read().decode("utf-8"))


def quote_from_xaus(payload: dict, now: datetime) -> dict | None:
    state = payload.get("data_state") or {}
    updated = payload.get("updated_at") or state.get("as_of")
    price = payload.get("spot_usd_oz")
    if price is None:
        price = (payload.get("xau") or {}).get("price")
    if state.get("status") != "fresh" or not updated or price is None:
        return None
    stamp = parse_time(updated)
    age = (now.astimezone(UTC) - stamp).total_seconds()
    if age < -60 or age > MAX_AGE_SECONDS:
        return None
    return {"price": float(price), "timestamp": stamp, "source": "XAUS", "age": max(0, int(age))}


def quote_from_backup(payload: dict, now: datetime) -> dict | None:
    updated = payload.get("updatedAt")
    price = payload.get("price")
    if not updated or price is None:
        return None
    stamp = parse_time(updated)
    age = (now.astimezone(UTC) - stamp).total_seconds()
    if age < -60 or age > MAX_AGE_SECONDS:
        return None
    return {"price": float(price), "timestamp": stamp, "source": "Gold-API (backup)", "age": max(0, int(age))}


def fetch_quote(now: datetime) -> dict | None:
    try:
        quote = quote_from_xaus(http_json(XAUS_SPOT), now)
        if quote:
            return quote
    except Exception as exc:
        print(f"XAUS provider error: {exc}")
    try:
        quote = quote_from_backup(http_json(BACKUP_SPOT), now)
        if quote:
            return quote
    except Exception as exc:
        print(f"Backup provider error: {exc}")
    return None


def historical_30m_price(now: datetime, state: dict) -> tuple[float, str] | None:
    target = now.astimezone(UTC) - timedelta(minutes=30)
    try:
        payload = http_json(XAUS_INTRADAY)
        points = payload.get("points") or []
        eligible = []
        for point in points:
            stamp = datetime.fromtimestamp(int(point["t"]), UTC)
            delta = abs((stamp - target).total_seconds())
            if delta <= 8 * 60:
                eligible.append((delta, float(point["p"]), stamp))
        if eligible:
            _, price, stamp = min(eligible, key=lambda item: item[0])
            return price, f"XAUS intraday ({stamp:%H:%M} UTC)"
    except Exception as exc:
        print(f"XAUS intraday history error: {exc}")
    samples = state.get("samples", [])
    eligible = []
    for sample in samples:
        try:
            stamp = parse_time(sample["timestamp"])
            delta = abs((stamp - target).total_seconds())
            if delta <= 8 * 60:
                eligible.append((delta, float(sample["price"]), stamp))
        except (KeyError, ValueError, TypeError):
            continue
    if eligible:
        _, price, stamp = min(eligible, key=lambda item: item[0])
        return price, f"ذخیره ربات ({stamp:%H:%M} UTC)"
    return None


def pct_change(current: float, previous: float) -> float | None:
    return ((current - previous) / previous * 100) if previous else None


def money(value: float) -> str:
    return f"\u0024{value:,.2f}"


def direction(change: float) -> str:
    return "🟢 افزایش" if change > 0 else ("🔴 کاهش" if change < 0 else "⚪ بدون تغییر")


def fmt_time(dt: datetime, zone: ZoneInfo) -> str:
    return dt.astimezone(zone).strftime("%Y-%m-%d %H:%M %Z")


def price_message(quote: dict, comparison: tuple[float, str] | None, now: datetime) -> str:
    price = quote["price"]
    lines = ["🟡 <b>قیمت لحظه‌ای طلا | XAU/USD</b>", f"💰 قیمت هر اونس: <b>{money(price)}</b>"]
    if comparison:
        old, provenance = comparison
        change = price - old
        pct = pct_change(price, old)
        lines.extend([f"🕧 قیمت ۳۰ دقیقه قبل: {money(old)}",
                      f"📊 تغییر ۳۰ دقیقه: <b>{money(change)} ({pct:+.3f}٪)</b>",
                      direction(change), f"🧾 مبنای مقایسه: {provenance}"])
    else:
        lines.append("📊 تغییر ۳۰ دقیقه: داده تاریخی معتبر در دسترس نیست.")
    lines.extend([f"🕒 زمان قیمت: {fmt_time(quote['timestamp'], NY)} نیویورک",
                  f"🔎 منبع: {quote['source']} | عمر داده: {quote['age']} ثانیه",
                  "ℹ️ قیمت مرجع اسپات است و ممکن است با نرخ بروکر متفاوت باشد."])
    return "\n".join(lines)


def gap_lines(current: float, previous: float | None) -> list[str]:
    if previous is None or previous <= 0:
        return ["📏 اندازه گپ: قابل محاسبه نیست؛ قیمت بسته‌شدن قبلی ثبت نشده است."]
    gap = current - previous
    pct = pct_change(current, previous)
    label = "گپ مثبت" if gap > 0 else ("گپ منفی" if gap < 0 else "بدون گپ")
    return [f"📏 {label}: <b>{money(gap)} ({pct:+.3f}٪)</b>", f"📌 قیمت مرجع قبلی: {money(previous)}"]


def event_due(now: datetime, zone: ZoneInfo, hour: int, minute: int = 0, window: int = 45) -> str | None:
    local = now.astimezone(zone)
    scheduled = local.replace(hour=hour, minute=minute, second=0, microsecond=0)
    if timedelta(0) <= local - scheduled <= timedelta(minutes=window):
        return local.date().isoformat()
    return None


def load_state(path: Path = STATE_PATH) -> dict:
    if not path.exists():
        return {"samples": [], "daily_open": {}, "last_daily_close": None, "last_weekly_close": None,
                "sent": {"daily_open": "", "weekly_open": "", "daily_close": ""}, "last_price_slot": ""}
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
        data.setdefault("samples", []); data.setdefault("daily_open", {}); data.setdefault("sent", {})
        return data
    except (OSError, json.JSONDecodeError):
        raise RuntimeError("State file is unreadable; refusing to reset session history.")


def save_state(state: dict, path: Path = STATE_PATH) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_suffix(".tmp")
    tmp.write_text(json.dumps(state, ensure_ascii=False, indent=2), encoding="utf-8")
    tmp.replace(path)


def telegram_send(text: str) -> None:
    token = os.getenv("GOLD_PRICES_BOT_TOKEN"); chat_id = os.getenv("GOLD_PRICES_CHANNEL_ID")
    if not token or not chat_id:
        raise RuntimeError("Missing GOLD_PRICES_BOT_TOKEN or GOLD_PRICES_CHANNEL_ID GitHub secret")
    url = f"https://api.telegram.org/bot{token}/sendMessage"
    body = urllib.parse.urlencode({"chat_id": chat_id, "text": text, "parse_mode": "HTML",
                                   "disable_web_page_preview": "true"}).encode()
    request = urllib.request.Request(url, data=body, method="POST")
    with urllib.request.urlopen(request, timeout=20) as response:
        result = json.loads(response.read().decode())
    if not result.get("ok"):
        raise RuntimeError(f"Telegram API rejected message: {result}")


def process(now: datetime, state: dict, sender=telegram_send, quote_fetcher=fetch_quote) -> list[str]:
    now = now.astimezone(UTC); quote = quote_fetcher(now)
    if not quote:
        print("No fresh price from primary or backup provider; no price message sent."); return []
    price = quote["price"]
    state["samples"].append({"timestamp": quote["timestamp"].isoformat(), "price": price})
    cutoff = now - timedelta(days=3)
    state["samples"] = [s for s in state["samples"] if parse_time(s["timestamp"]) >= cutoff]
    sent = []
    slot = now.replace(minute=0 if now.minute < 30 else 30, second=0, microsecond=0).isoformat()
    if state.get("last_price_slot") != slot:
        comparison = historical_30m_price(now, state)
        sender(price_message(quote, comparison, now)); state["last_price_slot"] = slot; sent.append("30m_price")

    sydney_day = now.astimezone(SYDNEY); open_key = event_due(now, SYDNEY, 8)
    if open_key and sydney_day.weekday() < 5:
        if sydney_day.weekday() == 0 and state["sent"].get("weekly_open") != open_key:
            previous = state.get("last_weekly_close")
            msg = ["🌏 <b>بازگشایی هفتگی طلا | سشن سیدنی</b>",
                   f"💰 قیمت بازگشایی: <b>{money(price)}</b>", f"🕒 زمان: {fmt_time(now, SYDNEY)}",
                   *gap_lines(price, previous.get("price") if previous else None), f"🔎 منبع: {quote['source']}"]
            sender("\n".join(msg)); state["sent"]["weekly_open"] = open_key; sent.append("weekly_open")
        elif sydney_day.weekday() in (1, 2, 3, 4) and state["sent"].get("daily_open") != open_key:
            previous = state.get("last_daily_close")
            msg = ["🌅 <b>بازگشایی روزانه طلا | سشن سیدنی</b>",
                   f"💰 قیمت بازگشایی: <b>{money(price)}</b>", f"🕒 زمان: {fmt_time(now, SYDNEY)}",
                   *gap_lines(price, previous.get("price") if previous else None), f"🔎 منبع: {quote['source']}"]
            sender("\n".join(msg)); state["daily_open"][open_key] = price
            state["sent"]["daily_open"] = open_key; sent.append("daily_open")

    close_key = event_due(now, NY, 17); ny_day = now.astimezone(NY)
    if close_key and ny_day.weekday() < 5 and state["sent"].get("daily_close") != close_key:
        previous_open = state.get("daily_open", {}).get(now.astimezone(SYDNEY).date().isoformat())
        change = price - previous_open if previous_open is not None else None
        pct = pct_change(price, previous_open) if previous_open is not None else None
        change_text = f"{money(change)} ({pct:+.3f}٪)" if change is not None else "قابل محاسبه نیست"
        msg = ["🔔 <b>گزارش بسته‌شدن روزانه طلا</b>",
               f"🌅 قیمت بازگشایی روز: {money(previous_open) if previous_open is not None else 'ثبت نشده'}",
               f"🌇 قیمت بسته‌شدن: <b>{money(price)}</b>", f"📊 تغییر روز: {change_text}",
               f"🕒 زمان بسته‌شدن: {fmt_time(now, NY)}", f"🔎 منبع: {quote['source']}"]
        sender("\n".join(msg)); state["last_daily_close"] = {"price": price, "timestamp": quote["timestamp"].isoformat(), "date": close_key}
        state["sent"]["daily_close"] = close_key
        if ny_day.weekday() == 4: state["last_weekly_close"] = state["last_daily_close"].copy()
        sent.append("daily_close")
    return sent


def main() -> int:
    if not os.getenv("GOLD_PRICES_BOT_TOKEN") or not os.getenv("GOLD_PRICES_CHANNEL_ID"):
        print("Gold Prices Telegram secrets are not configured; skipping delivery."); return 0
    now = datetime.now(UTC); state = load_state()
    try: sent = process(now, state)
    finally: save_state(state)
    print("Sent:", ", ".join(sent) if sent else "no event"); return 0


if __name__ == "__main__":
    sys.exit(main())
