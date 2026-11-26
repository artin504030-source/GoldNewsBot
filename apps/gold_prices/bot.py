"""Gold Prices Telegram bot: free spot providers, session snapshots and gap reporting."""
from __future__ import annotations

import json
import os
import sys
import urllib.parse
import urllib.request
import urllib.error
from datetime import datetime, timedelta, timezone
from pathlib import Path
from zoneinfo import ZoneInfo

UTC = timezone.utc
NY = ZoneInfo("America/New_York")
SYDNEY = ZoneInfo("Australia/Sydney")
XAUS_SPOT = "https://xaus.com/api/v1/spot?compact=1"
XAUS_INTRADAY = "https://xaus.com/api/v1/intraday?symbol=xau&hours=2"
BACKUP_SPOT = "https://api.gold-api.com/price/XAU"
BIQUOTE_LATEST = "https://biquote.io/api/latest"
MAX_AGE_SECONDS = 300
SYMBOLS = {
    "XAUUSD": ("فلزات", "طلا"), "XAGUSD": ("فلزات", "نقره"),
    "XPTUSD": ("فلزات", "پلاتین"), "XPDUSD": ("فلزات", "پالادیوم"),
    "EURUSD": ("جفت‌ارزها", "EUR/USD"), "GBPUSD": ("جفت‌ارزها", "GBP/USD"),
    "USDJPY": ("جفت‌ارزها", "USD/JPY"), "AUDUSD": ("جفت‌ارزها", "AUD/USD"),
    "USDCAD": ("جفت‌ارزها", "USD/CAD"),
    "US30": ("شاخص‌ها", "داوجونز | US30"), "USTEC": ("شاخص‌ها", "نزدک ۱۰۰ | NAS100"),
    "US500": ("شاخص‌ها", "اس‌اندپی ۵۰۰ | SPX500"), "DE30": ("شاخص‌ها", "دکس ۴۰ | DAX40"),
    "USOIL": ("انرژی", "نفت WTI"), "UKOIL": ("انرژی", "نفت برنت"),
    "XNGUSD": ("انرژی", "گاز طبیعی"),
}
FOREX_SYMBOLS = {"EURUSD", "GBPUSD", "USDJPY", "AUDUSD", "USDCAD"}

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


def quote_from_biquote(symbol: str, payload: dict, now: datetime) -> dict | None:
    if not payload or payload.get("symbol") != symbol:
        return None
    if payload.get("stale") is True or payload.get("marketState") != "open":
        return None
    price = payload.get("mid")
    updated = payload.get("timestamp") or payload.get("lastQuoteAt")
    if price is None or not updated:
        return None
    stamp = parse_time(updated)
    age = (now.astimezone(UTC) - stamp).total_seconds()
    reported_age = payload.get("quoteAgeSeconds")
    if age < -60 or age > MAX_AGE_SECONDS:
        return None
    if reported_age is not None and float(reported_age) > MAX_AGE_SECONDS:
        return None
    return {"price": float(price), "timestamp": stamp,
            "source": f"BiQuote / {payload.get('source', 'live feed')}",
            "age": max(0, int(age)), "bid": payload.get("bid"),
            "ask": payload.get("ask"), "spread": payload.get("spread")}


def fetch_multi_quotes(now: datetime) -> dict:
    query = urllib.parse.urlencode([("symbols", symbol) for symbol in SYMBOLS])
    try:
        payload = http_json(f"{BIQUOTE_LATEST}?{query}")
    except Exception as exc:
        print(f"BiQuote provider error: {exc}")
        return {}
    quotes = {}
    for symbol in SYMBOLS:
        quote = quote_from_biquote(symbol, payload.get(symbol), now)
        if quote:
            quotes[symbol] = quote
        else:
            print(f"No fresh/open BiQuote quote for {symbol}")
    return quotes


def display_price(symbol: str, price: float) -> str:
    if symbol in FOREX_SYMBOLS:
        return f"{price:,.{3 if symbol == 'USDJPY' else 5}f}"
    if symbol == "XNGUSD":
        return f"{price:,.4f}"
    return f"{price:,.2f}"


def prices_message(quotes: dict, state: dict, now: datetime) -> str:
    target = now.astimezone(UTC) - timedelta(minutes=30)
    lines = ["📊 <b>قیمت بازارها | به‌روزرسانی ۳۰ دقیقه‌ای</b>"]
    samples = state.get("samples", [])
    for group in ("فلزات", "جفت‌ارزها", "شاخص‌ها", "انرژی"):
        group_lines = []
        for symbol, meta in SYMBOLS.items():
            if meta[0] != group or symbol not in quotes:
                continue
            quote = quotes[symbol]
            line = f"• <b>{meta[1]}</b>: <code>{display_price(symbol, quote['price'])}</code>"
            candidates = []
            for sample in samples:
                if sample.get("symbol", "XAUUSD") != symbol:
                    continue
                try:
                    stamp = parse_time(sample["timestamp"])
                    delta = abs((stamp - target).total_seconds())
                    if delta <= 12 * 60:
                        candidates.append((delta, float(sample["price"])))
                except (KeyError, ValueError, TypeError):
                    continue
            if candidates:
                _, previous = min(candidates, key=lambda item: item[0])
                change = quote["price"] - previous
                pct = pct_change(quote["price"], previous)
                line += f" | ۳۰دقیقه: {'+' if change > 0 else ''}{display_price(symbol, change)} ({pct:+.3f}٪)"
            else:
                line += " | تغییر ۳۰دقیقه: داده مقایسه‌ای موجود نیست"
            group_lines.append(line)
        if group_lines:
            lines.append(f"\n<b>{group}</b>")
            lines.extend(group_lines)
    missing = [meta[1] for symbol, meta in SYMBOLS.items() if symbol not in quotes]
    if missing:
        lines.append("\n⚠️ <b>قیمت تازه/باز در دسترس نیست:</b> " + "، ".join(missing))
    sources = sorted({q["source"] for q in quotes.values()})
    if sources:
        lines.append("\n🔎 منبع: " + "؛ ".join(sources))
    lines.append(f"\n🕒 زمان بررسی: {fmt_time(now, NY)} نیویورک")
    lines.append("ℹ️ قیمت‌ها نرخ مرجع فید هستند و ممکن است با قیمت بروکر شما تفاوت داشته باشند.")
    return "\n".join(lines)


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
    signature = "<b>Gold Admin</b>\\n<b>Prices Admin</b>"
    if text.endswith(signature):
        text = text[:-len(signature)].rstrip()
    lines = text.splitlines()
    title = lines[0].strip() if lines else "گزارش قیمت بازار"
    body = "\\n".join(lines[1:]).strip()
    text = (
        "<b>Gold Channel | XAU</b>\\n\\n"
        f"<b>عنوان:</b>\\n{title}\\n\\n"
        f"<b>متن:</b>\\n{body}\\n\\n"
        f"{signature}"
    )
    token = os.getenv("GOLD_PRICES_BOT_TOKEN"); chat_id = os.getenv("GOLD_PRICES_CHANNEL_ID")
    if not token or not chat_id:
        raise RuntimeError("Missing GOLD_PRICES_BOT_TOKEN or GOLD_PRICES_CHANNEL_ID GitHub secret")
    url = f"https://api.telegram.org/bot{token}/sendMessage"
    body = urllib.parse.urlencode({"chat_id": chat_id, "text": text, "parse_mode": "HTML",
                                   "disable_web_page_preview": "true"}).encode()
    request = urllib.request.Request(url, data=body, method="POST")
    try:
        with urllib.request.urlopen(request, timeout=20) as response:
            result = json.loads(response.read().decode())
    except urllib.error.HTTPError as exc:
        detail = exc.read().decode("utf-8", errors="replace")
        raise RuntimeError(f"Telegram API HTTP {exc.code}: {detail}") from exc
    if not result.get("ok"):
        raise RuntimeError(f"Telegram API rejected message: {result}")


def _symbol_label(symbol: str) -> str:
    return SYMBOLS[symbol][1]


def _latest_symbol_price(symbol: str, quotes: dict, state: dict, now: datetime,
                         max_age_minutes: int = 45) -> dict | None:
    live = quotes.get(symbol)
    if live:
        return live
    cutoff = now.astimezone(UTC) - timedelta(minutes=max_age_minutes)
    candidates = []
    for sample in state.get("samples", []):
        if sample.get("symbol", "XAUUSD") != symbol:
            continue
        try:
            stamp = parse_time(sample["timestamp"])
            if cutoff <= stamp <= now.astimezone(UTC):
                candidates.append((stamp, float(sample["price"])))
        except (KeyError, ValueError, TypeError):
            continue
    if not candidates:
        return None
    stamp, price = max(candidates, key=lambda item: item[0])
    return {"price": price, "timestamp": stamp, "source": "آخرین قیمت معتبر ذخیره‌شده",
            "age": int((now.astimezone(UTC) - stamp).total_seconds())}


def _price_snapshot(quotes: dict, state: dict, now: datetime) -> dict:
    snapshot = {}
    for symbol in SYMBOLS:
        item = _latest_symbol_price(symbol, quotes, state, now)
        if item:
            snapshot[symbol] = {"price": float(item["price"]),
                                "timestamp": item["timestamp"].isoformat(),
                                "source": item.get("source", "unknown")}
    return snapshot


def session_report(title: str, quotes: dict, state: dict, now: datetime,
                   reference: dict | None = None, opening: bool = False) -> tuple[str, dict]:
    snapshot = _price_snapshot(quotes, state, now)
    lines = [title, f"🕒 زمان گزارش: {fmt_time(now, SYDNEY if opening else NY)}"]
    for group in ("فلزات", "جفت‌ارزها", "شاخص‌ها", "انرژی"):
        lines.append(f"\n<b>{group}</b>")
        for symbol, (category, label) in SYMBOLS.items():
            if category != group:
                continue
            current = snapshot.get(symbol)
            previous = (reference or {}).get(symbol)
            if not current:
                lines.append(f"• <b>{label}</b>: قیمت تازه/قابل اتکا در دسترس نیست")
                continue
            price = float(current["price"])
            line = f"• <b>{label}</b>: <code>{display_price(symbol, price)}</code>"
            if previous is not None:
                old = float(previous.get("price", previous) if isinstance(previous, dict) else previous)
                change = price - old
                pct = pct_change(price, old)
                if opening:
                    line += f" | گپ: {display_price(symbol, change)} ({pct:+.3f}٪)"
                else:
                    line += f" | تغییر: {display_price(symbol, change)} ({pct:+.3f}٪)"
            else:
                line += " | مبنای مقایسه ثبت نشده"
            stamp = parse_time(current["timestamp"])
            age = max(0, int((now.astimezone(UTC) - stamp).total_seconds()))
            if age > 0:
                line += f" | قیمت ثبت‌شده {age // 60} دقیقه قبل"
            lines.append(line)
    lines.append("\nℹ️ نرخ‌ها قیمت مرجع فید هستند و ممکن است با قیمت بروکر تفاوت داشته باشند.")
    return "\n".join(lines), snapshot


def process(now: datetime, state: dict, sender=telegram_send, quote_fetcher=fetch_quote,
            multi_quote_fetcher=None) -> list[str]:
    now = now.astimezone(UTC)
    quotes = multi_quote_fetcher(now) if multi_quote_fetcher else fetch_multi_quotes(now)
    quote = quotes.get("XAUUSD") or quote_fetcher(now)
    if quote:
        quotes["XAUUSD"] = quote
    state.setdefault("samples", [])
    state.setdefault("daily_open", {})
    state.setdefault("sent", {})
    for symbol, item in quotes.items():
        state["samples"].append({"symbol": symbol, "timestamp": item["timestamp"].isoformat(),
                                 "price": item["price"]})
    cutoff = now - timedelta(days=8)
    state["samples"] = [s for s in state["samples"] if parse_time(s["timestamp"]) >= cutoff]
    sent = []
    slot = now.replace(minute=0 if now.minute < 30 else 30, second=0, microsecond=0).isoformat()
    if quotes and state.get("last_price_slot") != slot:
        sender(prices_message(quotes, state, now))
        state["last_price_slot"] = slot
        sent.append("30m_price")

    sydney_day = now.astimezone(SYDNEY)
    open_key = event_due(now, SYDNEY, 8)
    if open_key and sydney_day.weekday() < 5:
        if sydney_day.weekday() == 0 and state["sent"].get("weekly_open") != open_key:
            previous = state.get("last_weekly_close") or {}
            reference = previous.get("prices", {})
            if not reference and previous.get("price") is not None:
                reference = {"XAUUSD": previous["price"]}
            msg, snapshot = session_report("🌏 <b>گزارش بازگشایی هفتگی بازارها | سشن سیدنی</b>",
                                           quotes, state, now, reference, opening=True)
            sender(msg)
            state["sent"]["weekly_open"] = open_key
            state["weekly_open"] = {"date": open_key, "prices": snapshot}
            sent.append("weekly_open")
        elif sydney_day.weekday() in (1, 2, 3, 4) and state["sent"].get("daily_open") != open_key:
            previous = state.get("last_daily_close") or {}
            reference = previous.get("prices", {})
            if not reference and previous.get("price") is not None:
                reference = {"XAUUSD": previous["price"]}
            msg, snapshot = session_report("🌅 <b>گزارش بازگشایی روزانه بازارها | سشن سیدنی</b>",
                                           quotes, state, now, reference, opening=True)
            sender(msg)
            state["daily_open"][open_key] = snapshot
            state["sent"]["daily_open"] = open_key
            sent.append("daily_open")

    close_key = event_due(now, NY, 17)
    ny_day = now.astimezone(NY)
    if close_key and ny_day.weekday() < 5 and state["sent"].get("daily_close") != close_key:
        open_record = state.get("daily_open", {}).get(sydney_day.date().isoformat(), {})
        if isinstance(open_record, dict) and "prices" in open_record:
            open_prices = open_record.get("prices", {})
        else:
            open_prices = open_record if isinstance(open_record, dict) else {}
        msg, snapshot = session_report("🔔 <b>گزارش بسته‌شدن روزانه تمام بازارها | ساعت ۱۷ نیویورک</b>",
                                       quotes, state, now, open_prices, opening=False)
        sender(msg)
        state["last_daily_close"] = {"price": snapshot.get("XAUUSD", {}).get("price"),
                                     "prices": snapshot, "timestamp": now.isoformat(), "date": close_key}
        state["sent"]["daily_close"] = close_key
        if ny_day.weekday() == 4:
            state["last_weekly_close"] = state["last_daily_close"].copy()
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
