#!/usr/bin/env python3
"""Standalone Gold Reports bot. Does not import or call any other project bot."""
from __future__ import annotations
import calendar
import html
import json
import os
import re
import sys
import time
from datetime import datetime, timedelta, date
from pathlib import Path
from urllib.parse import quote
from zoneinfo import ZoneInfo
import requests
from bs4 import BeautifulSoup
import xml.etree.ElementTree as ET

KABUL = ZoneInfo("Asia/Kabul")
LONDON = ZoneInfo("Europe/London")
ROOT = Path(__file__).resolve().parent
STATE_FILE = ROOT / "gold_reports_state.json"
TOKEN = os.environ.get("GOLD_REPORTS_BOT_TOKEN", "")
CHAT_ID = os.environ.get("GOLD_REPORTS_CHANNEL_ID", "")
UA = {"User-Agent": "Mozilla/5.0 (compatible; GoldReportsBot/1.0)"}
FF_URL = "https://www.forexfactory.com/calendar"
GOOGLE_RSS = "https://news.google.com/rss/search?q={query}&hl=en-US&gl=US&ceid=US:en"

# Do not publish stale calendar results when the monitor resumes after an outage.
POST_EVENT_GRACE = timedelta(hours=2)
# Session notices can be recovered if GitHub delays a scheduled runner.
SESSION_BOUNDARY_GRACE = timedelta(hours=2)


# Standard local market-session hours. ZoneInfo applies seasonal DST changes automatically.
SESSIONS = [
    {"name": "سیدنی", "country": "AU", "zone": "Australia/Sydney", "open": "07:00", "close": "16:00"},
    {"name": "توکیو", "country": "JP", "zone": "Asia/Tokyo", "open": "09:00", "close": "18:00"},
    {"name": "لندن", "country": "GB", "zone": "Europe/London", "open": "08:00", "close": "17:00"},
    {"name": "نیویورک", "country": "US", "zone": "America/New_York", "open": "08:00", "close": "17:00"},
]
COUNTRY_NAMES = {"AU": "استرالیا", "JP": "ژاپن", "GB": "بریتانیا", "US": "آمریکا"}

def fetch_public_holidays(state, now):
    cache = state.setdefault("holiday_cache", {})
    results = {}
    for session in SESSIONS:
        zone = ZoneInfo(session["zone"])
        local_year = now.astimezone(zone).date().year
        key = f"{session['country']}-{local_year}"
        cached = cache.get(key)
        refresh_due = True
        if cached and cached.get("fetched_at"):
            try:
                fetched = datetime.fromisoformat(cached["fetched_at"])
                refresh_due = (now - fetched).total_seconds() > (6 * 3600 if cached.get("unavailable") else 30 * 86400)
            except ValueError:
                pass
        if refresh_due:
            try:
                response = requests.get(
                    f"https://date.nager.at/api/v3/PublicHolidays/{local_year}/{session['country']}",
                    headers=UA, timeout=15
                )
                response.raise_for_status()
                holidays = response.json()
                cache[key] = {"fetched_at": now.isoformat(), "items": [
                    {"date": h.get("date"), "name": h.get("localName") or h.get("name") or "تعطیلی رسمی",
                     "global": bool(h.get("global", False)), "types": h.get("types", [])}
                    for h in holidays
                ]}
            except Exception as exc:
                print(f"Holiday source unavailable for {key}: {exc}", file=sys.stderr)
                if not cached:
                    cache[key] = {"fetched_at": now.isoformat(), "items": [], "unavailable": True}
        results[session["country"]] = cache.get(key, {}).get("items", [])
    return results

def get_session_times(session, now, session_date=None):
    zone = ZoneInfo(session["zone"])
    local_today = session_date or now.astimezone(zone).date()
    open_h, open_m = map(int, session["open"].split(":"))
    close_h, close_m = map(int, session["close"].split(":"))
    open_local = datetime.combine(local_today, datetime.min.time().replace(hour=open_h, minute=open_m), zone)
    close_local = datetime.combine(local_today, datetime.min.time().replace(hour=close_h, minute=close_m), zone)
    return open_local.astimezone(KABUL), close_local.astimezone(KABUL)


def session_status_text(now, holiday_data, ff_events):
    lines = ["🌐 <b>برنامه و وضعیت روزانه سشن‌های معاملاتی</b>"]
    ff_holidays = {}
    for event in ff_events:
        if event.get("all_day") and any(word in event["title"].lower() for word in ("holiday", "bank holiday")):
            country = {"AUD": "AU", "JPY": "JP", "GBP": "GB", "USD": "US"}.get(event["currency"].upper())
            if country:
                ff_holidays.setdefault(country, []).append({"date": event["date"], "title": event["title"]})

    for session in SESSIONS:
        zone = ZoneInfo(session["zone"])
        local_now = now.astimezone(zone)
        local_date = local_now.date()
        today_open, today_close = get_session_times(session, now, local_date)
        opened = today_open <= now < today_close

        # If today's local session has ended, show the next weekday's opening/closing
        # so the daily Kabul schedule never displays yesterday's already-finished hours.
        display_date = local_date
        weekend = local_date.weekday() >= 5
        if weekend or (not opened and now >= today_close):
            display_date = local_date + timedelta(days=1)
            while display_date.weekday() >= 5:
                display_date += timedelta(days=1)
        open_kabul, close_kabul = get_session_times(session, now, display_date)

        public_holiday = next((h for h in holiday_data.get(session["country"], [])
                               if h.get("date") == local_date.isoformat()), None)
        ff_reason = "; ".join(sorted({
            h["title"] for h in ff_holidays.get(session["country"], [])
            if h["date"] == local_date.isoformat()
        }))

        if weekend:
            status, marker = "تعطیل آخر هفته؛ زمان بازگشایی بعدی", "🔴"
        elif ff_reason:
            status, marker = f"تعطیل بانکی — {html.escape(ff_reason)}", "🔴"
        elif opened:
            status, marker = "اکنون باز است", "🟢"
        elif now < today_open:
            status, marker = "هنوز باز نشده", "🟡"
        else:
            status, marker = "اکنون بسته است؛ زمان بازگشایی بعدی", "⚪"

        if public_holiday and not ff_reason and not weekend:
            status += f" | تعطیلی رسمی {COUNTRY_NAMES[session['country']]}: {html.escape(public_holiday.get('name', 'تعطیلی رسمی'))}"
            if not opened:
                marker = "🟠"

        open_label = open_kabul.strftime("%Y-%m-%d %H:%M" if open_kabul.date() != now.date() else "%H:%M")
        close_label = close_kabul.strftime("%Y-%m-%d %H:%M" if close_kabul.date() != now.date() else "%H:%M")
        state_line = f"{marker} <b>سشن {session['name']}: {status}</b>"
        if opened:
            state_line += f" — تا ساعت <code>{close_label}</code> کابل باز است"
        else:
            state_line += f" — نوبت بعدی از <code>{open_label}</code> تا <code>{close_label}</code> کابل"
        lines.append(state_line)
        lines.append(f"بازگشایی: <code>{open_label}</code> کابل | بسته‌شدن: <code>{close_label}</code> کابل")

    lines.append("ساعت‌ها به وقت کابل هستند و با تغییر ساعت تابستانی لندن، نیویورک و سیدنی به‌صورت خودکار تنظیم می‌شوند.")
    return "\n".join(lines)

def monitor_session_boundaries(state, now, holiday_data, ff_events):
    sent = state.setdefault("session_notices", {})
    utc_now = now.astimezone(ZoneInfo("UTC"))
    for session in SESSIONS:
        zone = ZoneInfo(session["zone"])
        local_date = now.astimezone(zone).date()
        candidate_dates = (local_date, local_date - timedelta(days=1))
        currency = {"AU": "AUD", "JP": "JPY", "GB": "GBP", "US": "USD"}.get(session["country"])

        for session_date in candidate_dates:
            if session_date.weekday() >= 5:
                continue
            bank_holiday = any(
                e.get("all_day") and e.get("date") == session_date.isoformat()
                and e.get("currency", "").upper() == currency
                and "holiday" in e.get("title", "").lower()
                for e in ff_events
            )
            if bank_holiday:
                continue

            opening, closing = get_session_times(session, now, session_date)
            for kind, boundary, verb in (("open", opening, "باز شد"), ("close", closing, "بسته شد")):
                delta = (utc_now - boundary.astimezone(ZoneInfo("UTC"))).total_seconds()
                key = f"{session['country']}:{session_date.isoformat()}:{kind}"
                if 0 <= delta <= SESSION_BOUNDARY_GRACE.total_seconds() and not sent.get(key):
                    time_label = boundary.strftime("%Y-%m-%d %H:%M" if boundary.date() != now.date() else "%H:%M")
                    snapshot = session_status_text(now, holiday_data, ff_events).splitlines()[1:]
                    message = (
                        f"🔔 <b>اعلان سشن معاملاتی</b>\n"
                        f"🕒 ساعت کابل: <code>{time_label}</code>\n"
                        f"سشن <b>{session['name']}</b> {verb}.\n\n"
                        f"<b>وضعیت هم‌زمان همه سشن‌ها</b>\n"
                        + "\n".join(snapshot)
                        + "\n\n<b>Gold Admin</b>\n<b>Reports Admin</b>"
                    )
                    send_telegram(message)
                    sent[key] = now.isoformat()
                    print(f"Session boundary notice sent | {session['name']} | {kind} | scheduled={boundary.isoformat()} | delay_seconds={int(delta)}")

def now_kabul():
    return datetime.now(KABUL)

def load_state():
    try:
        return json.loads(STATE_FILE.read_text(encoding="utf-8"))
    except Exception:
        return {"pre_sent": {}, "post_sent": {}, "daily_sent": {}, "session_daily_sent": {}}

def save_state(state):
    STATE_FILE.write_text(json.dumps(state, ensure_ascii=False, indent=2), encoding="utf-8")

def clean(s):
    return re.sub(r"\s+", " ", s or "").strip()

def get_calendar(month_date=None):
    month_date = month_date or now_kabul().date()
    month_name = calendar.month_abbr[month_date.month].lower()
    month_arg = f"{month_name}.{month_date.year}"
    url = f"{FF_URL}?month={month_arg}"
    response = requests.get(url, headers=UA, timeout=25)
    response.raise_for_status()
    soup = BeautifulSoup(response.text, "html.parser")
    tz_text = soup.get_text(" ", strip=True)
    tz_match = re.search(r"Calendar Time Zone:\s*([A-Za-z_]+/[A-Za-z_ ]+)", tz_text)
    tz_name = tz_match.group(1).strip().replace(" ", "_") if tz_match else "UTC"
    try:
        calendar_tz = ZoneInfo(tz_name)
    except Exception:
        calendar_tz = ZoneInfo("UTC")
    events = []
    current_day = None
    for row in soup.select("tr.calendar__row"):
        date_cell = row.select_one("td.calendar__date")
        if date_cell:
            raw_date = clean(date_cell.get_text(" ", strip=True))
            parsed = parse_ff_date(raw_date, month_date.year)
            if parsed:
                current_day = parsed
        if current_day is None or current_day.month != month_date.month:
            continue
        title = clean((row.select_one(".calendar__event-title") or row).get_text(" ", strip=True))
        currency = clean((row.select_one(".calendar__currency") or row).get_text(" ", strip=True))
        impact_el = row.select_one(".calendar__impact span")
        impact = clean(" ".join(impact_el.get("class", [])) if impact_el else "")
        impact = "high" if "red" in impact.lower() else ("medium" if "ora" in impact.lower() else ("low" if "yel" in impact.lower() else "low"))
        time_text = clean((row.select_one(".calendar__time") or row).get_text(" ", strip=True))
        actual = clean((row.select_one(".calendar__actual") or row).get_text(" ", strip=True))
        forecast = clean((row.select_one(".calendar__forecast") or row).get_text(" ", strip=True))
        previous = clean((row.select_one(".calendar__previous") or row).get_text(" ", strip=True))
        if not title or title.lower() == "tentative":
            continue
        all_day = time_text.lower() in ("all day", "day", "")
        event_dt = datetime.combine(current_day, datetime.min.time(), calendar_tz) if all_day else parse_ff_time(current_day, time_text, calendar_tz)
        if not event_dt:
            continue
        events.append({
            "date": current_day.isoformat(), "datetime_utc": event_dt.astimezone(ZoneInfo("UTC")).isoformat(),
            "datetime_kabul": event_dt.astimezone(KABUL).isoformat(), "title": title,
            "currency": currency, "impact": impact, "actual": actual, "forecast": forecast,
            "previous": previous, "all_day": all_day, "source": url
        })
    # Some calendar pages render repeated event rows without date cells; current_day handles that.
    unique = {}
    for e in events:
        unique[(e["datetime_utc"], e["currency"], e["title"])] = e
    return sorted(unique.values(), key=lambda x: x["datetime_utc"])

def parse_ff_date(text, year):
    text = clean(text)
    for fmt in ("%a %b %d", "%b %d", "%A %b %d"):
        try:
            d = datetime.strptime(text, fmt).date()
            return d.replace(year=year)
        except ValueError:
            pass
    return None

def parse_ff_time(day, text, calendar_tz):
    text = clean(text).lower()
    if not text or text in ("all day", "tentative", "day"):
        return None
    try:
        t = datetime.strptime(text, "%I:%M%p").time()
    except ValueError:
        try:
            t = datetime.strptime(text, "%I%p").time()
        except ValueError:
            return None
    return datetime.combine(day, t, calendar_tz)

def analyst_sources(event):
    # Google News RSS is used as a discovery layer; each item retains its publisher and original link.
    q = f'"{event["title"]}" {event["currency"]} economists forecast OR analysts outlook'
    url = GOOGLE_RSS.format(query=quote(q))
    try:
        r = requests.get(url, headers=UA, timeout=18)
        r.raise_for_status()
        root = ET.fromstring(r.content)
    except Exception:
        return []
    items = []
    for item in root.findall(".//item")[:8]:
        title = clean(item.findtext("title"))
        link = clean(item.findtext("link"))
        source = clean(item.findtext("source")) or "News publisher"
        desc = clean(BeautifulSoup(item.findtext("description") or "", "html.parser").get_text(" ", strip=True))
        if title and link:
            items.append({"title": title, "link": link, "source": source, "description": desc})
    return items

def analyst_bias(event, articles):
    """One vote per distinct publisher domain; never treat repeated feed copies as consensus."""
    from urllib.parse import urlparse
    votes = {}
    for article in articles or []:
        host = urlparse(article.get("link", "")).netloc.lower().removeprefix("www.")
        publisher = (article.get("source", "") or "").strip().lower()
        # Google News RSS links share one host; use the publisher label in that case.
        domain = publisher if host.endswith("news.google.com") else (host or publisher)
        domain = domain.removeprefix("www.")
        if not domain or domain in votes:
            continue
        text = (article.get("title", "") + " " + article.get("description", "")).lower()
        higher = ("hotter than expected", "higher than expected", "sticky inflation",
                  "inflation remains high", "hawkish", "stronger than expected",
                  "rate hike", "upside surprise", "above forecast")
        lower = ("cooler than expected", "lower than expected", "softening inflation",
                 "disinflation", "dovish", "weaker than expected", "rate cut",
                 "downside surprise", "below forecast")
        hi = any(term in text for term in higher)
        lo = any(term in text for term in lower)
        votes[domain] = "higher" if hi and not lo else "lower" if lo and not hi else "mixed"
    higher_count = sum(v == "higher" for v in votes.values())
    lower_count = sum(v == "lower" for v in votes.values())
    mixed_count = sum(v == "mixed" for v in votes.values())
    if len(votes) < 2:
        return (
            f"فقط {len(votes)} ناشر مستقل قابل‌شناسایی بود؛ برای برداشت از اجماع حداقل دو ناشر مستقل لازم است.",
            "نامشخص",
        )
    if higher_count == lower_count:
        label = "نامشخص"
        message = "ناشران مستقل بررسی‌شده جهت غالب روشنی نشان نمی‌دهند."
    elif higher_count > lower_count:
        label = "بالاتر/قوی‌تر"
        message = "در دیدگاه ناشران مستقل بررسی‌شده، سناریوی بالاتر/قوی‌تر بیشتر دیده می‌شود؛ این اجماع رسمی عددی نیست."
    else:
        label = "پایین‌تر/ضعیف‌تر"
        message = "در دیدگاه ناشران مستقل بررسی‌شده، سناریوی پایین‌تر/ضعیف‌تر بیشتر دیده می‌شود؛ این اجماع رسمی عددی نیست."
    return (f"{message} رأی ناشران: بالاتر {higher_count}، پایین‌تر {lower_count}، متعارض/خنثی {mixed_count}؛ "
            f"تعداد ناشران مستقل: {len(votes)}."), label
def scenario_text(event, articles):
    bias, label = analyst_bias(event, articles)
    c = event["currency"].upper()
    name = event["title"].lower()
    if any(x in name for x in ("cpi", "inflation", "pce", "price index")):
        impacts = ("تورم بالاتر از پیش‌بینی معمولاً به نفع دلار و به ضرر طلاست؛ تورم پایین‌تر می‌تواند اثر معکوس داشته باشد.",
                   "مطابق پیش‌بینی، واکنش طلا و دلار به جزئیات هسته‌ای، بازده اوراق و لحن بازار وابسته می‌ماند.")
    elif any(x in name for x in ("interest rate", "rate decision", "fomc", "monetary policy")):
        impacts = ("نرخ/لحن انقباضی‌تر از انتظار معمولاً از دلار حمایت و بر طلا فشار وارد می‌کند.",
                   "تصمیم مطابق انتظار ممکن است واکنش محدودی داشته باشد؛ بیانیه و مسیر آتی نرخ‌ها مهم است.")
    elif any(x in name for x in ("employment", "payroll", "unemployment", "jobless")):
        impacts = ("داده اشتغال قوی‌تر از انتظار می‌تواند انتظارات نرخ بهره و دلار را بالا ببرد؛ ضعف غیرمنتظره می‌تواند به طلا کمک کند.",
                   "مطابق انتظار، جزئیات دستمزد و نرخ مشارکت نیز می‌توانند جهت بازار را تغییر دهند.")
    else:
        impacts = ("عدد قوی‌تر از انتظار می‌تواند از ارز مربوطه حمایت کند؛ اثر نهایی به ماهیت شاخص و واکنش بازده اوراق بستگی دارد.",
                   "عدد ضعیف‌تر از انتظار می‌تواند ارز مربوطه را تحت فشار قرار دهد؛ واکنش طلا وابسته به اثر آن بر دلار و نرخ‌هاست.")
    return bias, label, impacts

def compare_actual_forecast(actual, forecast, event_title=""):
    def number(value):
        match = re.search(r"[-+]?[0-9][0-9,]*(?:\.[0-9]+)?", value or "")
        if not match:
            return None
        try:
            return float(match.group(0).replace(",", ""))
        except ValueError:
            return None
    a, f = number(actual), number(forecast)
    if a is None or f is None:
        return "به دلیل نبودن عدد قابل‌مقایسه، نتیجه عددی مشخص نیست."
    if a == f:
        return "عدد واقعی مطابق پیش‌بینی منتشر شد."
    title = (event_title or "").lower()
    lower_is_stronger = any(term in title for term in ("unemployment", "jobless claims", "initial claims", "continuing claims", "بیکاری"))
    if lower_is_stronger:
        better = a < f
    else:
        better = a > f
    direction = "پایین‌تر" if a < f else "بالاتر"
    quality = "قوی‌تر/بهتر" if better else "ضعیف‌تر/بدتر"
    return f"عدد واقعی {direction} از پیش‌بینی بود؛ برای این شاخص، نتیجه از نظر اقتصادی {quality} محسوب می‌شود."
def analyst_expectation_comparison(label, actual, forecast, event_title=""):
    comparison = compare_actual_forecast(actual, forecast, event_title)
    if label == "نامشخص":
        return "به‌دلیل نبود جهت غالب روشن در دیدگاه منابع مستقل، تطابق نتیجه با نظر تحلیل‌گران قابل قضاوت نیست."
    if "مطابق پیش‌بینی" in comparison:
        return "عدد واقعی مطابق پیش‌بینی تقویم بود؛ این نتیجه به‌تنهایی دیدگاه جهت‌دار منابع درباره غافلگیری را تأیید نمی‌کند."
    if "قابل‌مقایسه نیست" in comparison:
        return "به‌دلیل نبود عدد واقعی یا پیش‌بینی قابل‌مقایسه، تطابق با دیدگاه منابع مشخص نیست."
    # Compare the raw direction of the surprise because publisher headlines may
    # describe the number itself (higher/lower), not whether it is economically good.
    higher = "بالاتر از پیش‌بینی" in comparison
    surprise = "بالاتر/قوی‌تر" if higher else "پایین‌تر/ضعیف‌تر"
    if surprise == label:
        return f"نتیجه واقعی از نظر عددی {surprise} بود و با جهت غالب گزارش‌های منابع هم‌جهت است."
    return f"نتیجه واقعی از نظر عددی {surprise} بود، اما با جهت غالب گزارش‌های منابع ({label}) هم‌جهت نیست."
def event_message(event, pre=True):
    articles = analyst_sources(event)
    bias, label, impacts = scenario_text(event, articles)
    when = datetime.fromisoformat(event["datetime_kabul"]).strftime("%Y-%m-%d %H:%M")
    lines = [
        "🗓 <b>پیش‌تحلیل رویداد اقتصادی</b>" if pre else "📊 <b>نتیجه رویداد اقتصادی</b>",
        f"🌍 <b>{html.escape(event['currency'])} | {html.escape(event['title'])}</b>",
        f"🕘 زمان کابل: <code>{when}</code>",
        f"اهمیت در Forex Factory: {html.escape(event['impact'])}",
        f"پیش‌بینی عددی Forex Factory: <b>{html.escape(event['forecast'] or 'در دسترس نیست')}</b>",
        f"عدد قبلی: {html.escape(event['previous'] or 'در دسترس نیست')}",
    ]
    if pre:
        lines += [
            "", "<b>انتظار و دیدگاه تحلیل‌گران</b>",
            html.escape(bias),
            f"جهت غالب برداشت‌شده از گزارش‌ها: <b>{html.escape(label)}</b>",
            "توجه: رأی‌ها بر اساس ناشر/دامنه مستقل شمرده شده‌اند؛ بازنشرهای یک ناشر رأی جداگانه نیستند. این اجماع رسمی عددی نیست؛ پیش‌بینی عددی همان مقدار Forex Factory است.",
            "", "<b>سه سناریوی قبل از انتشار</b>",
            f"• مطابق پیش‌بینی: {html.escape(impacts[1])}",
            f"• بالاتر/قوی‌تر از پیش‌بینی: {html.escape(impacts[0])}",
            "• پایین‌تر/ضعیف‌تر از پیش‌بینی: اثر معکوس سناریوی بالاتر؛ با توجه به نوع شاخص، ارز مربوطه و واکنش بازده اوراق.",
            "", "<b>گزارش‌ها و نظر منابع</b>"
        ]
    else:
        lines += [
            "", f"عدد واقعی: <b>{html.escape(event['actual'] or 'هنوز در منبع ثبت نشده')}</b>",
            f"مقایسه با پیش‌بینی: <b>{html.escape(compare_actual_forecast(event['actual'], event['forecast'], event['title']))}</b>",
            f"دیدگاه غالب پیش از انتشار: <b>{html.escape(label)}</b>",
            f"آیا مطابق انتظار تحلیل‌گران بود؟ {html.escape(analyst_expectation_comparison(label, event['actual'], event['forecast'], event['title']))}",
            f"جمع‌بندی دیدگاه منابع پیش از انتشار: {html.escape(bias)}",
            "", "نتیجه بالا بر اساس عدد واقعی و پیش‌بینی ثبت‌شده در تقویم است؛ واکنش بازار ممکن است به جزئیات گزارش و بازده اوراق وابسته باشد."
        ]
    for article in articles[:4]:
        detail = article.get("description", "")
        detail = detail[:260] + ("…" if len(detail) > 260 else "")
        title = html.escape(article["title"][:130])
        source = html.escape(article["source"])
        link = html.escape(article["link"], quote=True)
        line = f'• <a href="{link}">{source}: {title}</a>'
        if detail:
            line += f"\n  دیدگاه/خلاصه: {html.escape(detail)}"
        lines.append(line)
    if not articles:
        lines.append("برای این رویداد گزارش تحلیلی قابل استناد پیدا نشد؛ بنابراین نظر تحلیل‌گران یا تطابق آن با نتیجه اعلام نمی‌شود.")
    lines += [
        "", "<i>منبع خود رویداد و ارقام: Forex Factory. منابع دیگر فقط برای دیدگاه و تحلیل تکمیلی استفاده می‌شوند. این گزارش توصیه معاملاتی نیست.</i>",
        "", "<b>Gold Admin</b>", "<b>Reports Admin</b>"
    ]
    return "\n".join(lines)

def test_pre_news_message(events, now):
    # Use the next upcoming Forex Factory calendar event, prioritizing high impact.
    upcoming = [e for e in events
                if datetime.fromisoformat(e["datetime_utc"]) > now.astimezone(ZoneInfo("UTC"))]
    if not upcoming:
        raise RuntimeError("No upcoming Forex Factory event is available for a pre-release test.")
    upcoming.sort(key=lambda e: (
        0 if e["impact"] == "high" else 1,
        datetime.fromisoformat(e["datetime_utc"])
    ))
    message = event_message(upcoming[0], pre=True)
    return message.replace("پیش‌تحلیل رویداد اقتصادی", "🧪 پیام آزمایشی | پیش‌تحلیل قبل از انتشار", 1)

def test_news_message(events):
    # Sample strictly from an event listed in the Forex Factory economic calendar.
    event = next((e for e in events if "tokyo core cpi" in e["title"].lower()), None)
    if event is None:
        event = next((e for e in events if e.get("forecast") or e.get("previous")), None)
    if event is None:
        raise RuntimeError("No suitable Forex Factory calendar event found for the test message.")
    when = datetime.fromisoformat(event["datetime_kabul"]).strftime("%Y-%m-%d %H:%M")
    impact_fa = {"high": "زیاد", "medium": "متوسط", "low": "کم"}.get(event["impact"], "نامشخص")
    title_fa = "شاخص قیمت مصرف‌کننده هسته‌ای توکیو (سالانه)" if "tokyo core cpi" in event["title"].lower() else event["title"]
    lines = [
        "🧪 <b>پیام آزمایشی رویداد اقتصادی | Gold Reports</b>",
        "",
        f"📌 <b>رویداد:</b> {html.escape(title_fa)}",
        f"🌍 <b>کشور / ارز:</b> ژاپن / {html.escape(event['currency'])}",
        f"📅 <b>تاریخ و ساعت انتشار:</b> <code>{when}</code> (کابل)",
        f"⚠️ <b>اهمیت در Forex Factory:</b> {impact_fa}",
        f"📊 <b>عدد واقعی:</b> {html.escape(event['actual'] or 'هنوز منتشر نشده')}",
        f"🔮 <b>پیش‌بینی:</b> {html.escape(event['forecast'] or 'در تقویم ثبت نشده')}",
        f"📚 <b>عدد قبلی:</b> {html.escape(event['previous'] or 'در تقویم ثبت نشده')}",
        "",
        "<b>سه سناریوی احتمالی</b>",
        "1️⃣ <b>مطابق پیش‌بینی:</b> اگر عدد واقعی نزدیک 3.0٪ باشد، واکنش اولیه ین و طلا ممکن است محدود باشد؛ تمرکز بازار به جزئیات و انتظارات نرخ بهره ژاپن معطوف می‌شود.",
        "2️⃣ <b>بالاتر از پیش‌بینی:</b> تورم هسته‌ای قوی‌تر می‌تواند انتظارات سیاست پولی انقباضی‌تر بانک ژاپن را تقویت و از ین حمایت کند؛ اثر بر طلا غیرمستقیم و وابسته به واکنش دلار و بازده‌هاست.",
        "3️⃣ <b>پایین‌تر از پیش‌بینی:</b> تورم ضعیف‌تر می‌تواند انتظارات افزایش نرخ بهره را کاهش و بر ین فشار وارد کند؛ جهت نهایی طلا به حرکت دلار و بازده اوراق آمریکا بستگی دارد.",
        "",
        "<b>نمادهای مرتبط:</b>",
        "• <b>JPY pairs:</b> واکنش مستقیم‌تر به داده تورم ژاپن.",
        "• <b>XAUUSD:</b> اثر غیرمستقیم؛ از مسیر دلار، بازده اوراق و انتظارات نرخ بهره.",
        "• <b>DXY:</b> برای سنجش واکنش هم‌زمان دلار و اثر آن بر طلا زیر نظر گرفته شود.",
        "",
        "<b>جمع‌بندی:</b> این رویداد به‌تنهایی جهت قطعی طلا را تعیین نمی‌کند. واکنش واقعی بازار و داده‌های هم‌زمان باید بررسی شوند.",
        '🔗 <b>منبع رویداد:</b> <a href="https://www.forexfactory.com/calendar">تقویم اقتصادی Forex Factory</a>',
        "",
        "<i>این پیام صرفاً آزمایشی است و توصیه یا سیگنال معاملاتی نیست.</i>",
        "",
        "<b>Gold Admin</b>",
        "<b>Reports Admin</b>"
    ]
    return "\n".join(lines)

def telegram_post(url, payload, timeout=25, retries=3):
    last_response = None
    for attempt in range(retries):
        response = requests.post(url, json=payload, timeout=timeout)
        last_response = response
        try:
            data = response.json()
        except ValueError:
            data = {}
        if response.ok and data.get("ok"):
            return data
        retry_after = (data.get("parameters") or {}).get("retry_after")
        if response.status_code == 429 and retry_after and attempt < retries - 1:
            print(f"Telegram rate limit; retrying after {retry_after}s", file=sys.stderr)
            time.sleep(int(retry_after) + 1)
            continue
        description = data.get("description") or response.text[:300] or "unknown Telegram API error"
        raise RuntimeError(f"Telegram API failed (HTTP {response.status_code}): {description}")
    raise RuntimeError(f"Telegram API request failed after retries: {last_response.text[:300] if last_response else 'no response'}")


def send_telegram(text):
    if not TOKEN or not CHAT_ID:
        raise RuntimeError("Missing GOLD_REPORTS_BOT_TOKEN or GOLD_REPORTS_CHANNEL_ID secret")
    url = f"https://api.telegram.org/bot{TOKEN}/sendMessage"
    data = telegram_post(url, {
        "chat_id": CHAT_ID, "text": text, "parse_mode": "HTML",
        "disable_web_page_preview": True
    })
    message_id = data["result"]["message_id"]

    # Keep every Gold Reports message pinned silently; never unpin it automatically.
    pin_url = f"https://api.telegram.org/bot{TOKEN}/pinChatMessage"
    try:
        telegram_post(pin_url, {
            "chat_id": CHAT_ID, "message_id": message_id,
            "disable_notification": True
        }, timeout=20)
    except Exception as exc:
        print(f"WARNING: message sent but silent pin failed: {exc}", file=sys.stderr)
    return message_id

def send_long_telegram(message, limit=3500):
    separator = "━━━━━━━━━━━━━━━━━━━━"
    if separator in message:
        # Reports use the separator between event cards. Keep each card intact
        # when Telegram's message-size limit requires multiple messages.
        sections = message.split(separator)
        chunks, current = [], sections[0]
        for section in sections[1:]:
            candidate = current.rstrip() + "\\n" + separator + "\\n" + section.lstrip()
            if len(candidate) > limit and current.strip():
                chunks.append(current.strip())
                current = separator + "\\n" + section.lstrip()
            else:
                current = candidate
        if current.strip():
            chunks.append(current.strip())
    else:
        lines = message.splitlines()
        chunks, current = [], ""
        for line in lines:
            candidate = (current + "\\n" + line).strip() if current else line
            if len(candidate) > limit and current:
                chunks.append(current)
                current = line
            else:
                current = candidate
        if current:
            chunks.append(current)
    for chunk in chunks:
        send_telegram(chunk)

def report_message(events, heading, period, now, holiday_data, all_events):
    published = sum(
        1 for event in events
        if (event.get("actual") or "").strip() not in ("", "-", "—", "N/A")
    )
    pending = len(events) - published
    lines = [
        f"📚 <b>{heading}</b>",
        f"📆 دوره گزارش: <code>{period}</code>",
        f"📌 تعداد رویدادها: <b>{len(events)}</b> | منتشرشده: <b>{published}</b> | باقی‌مانده: <b>{pending}</b>",
        "",
    ]
    if not events:
        lines.append("رویداد مهمی در منبع تقویم پیدا نشد.")
    for index, e in enumerate(events, start=1):
        dt = datetime.fromisoformat(e["datetime_kabul"]).strftime("%Y-%m-%d %H:%M")
        event_utc = datetime.fromisoformat(e["datetime_utc"])
        actual_value = (e.get("actual") or "").strip()
        if actual_value and actual_value not in ("-", "—", "N/A"):
            status = "منتشر شده"
            result = f"\n📢 <b>نتیجه واقعی:</b> <b>{html.escape(actual_value)}</b>"
        elif event_utc <= now.astimezone(ZoneInfo("UTC")):
            status = "زمان انتشار گذشته؛ نتیجه هنوز در منبع ثبت نشده"
            result = ""
        else:
            status = "در انتظار انتشار"
            result = ""
        if index > 1:
            lines.extend(["", "━━━━━━━━━━━━━━━━━━━━", ""])
        lines.extend([
            f"📅 <b>تاریخ و ساعت:</b> <code>{html.escape(dt)}</code> کابل",
            f"🌍 <b>ارز:</b> {html.escape(e['currency'])}",
            f"📰 <b>رویداد:</b> {html.escape(e['title'])}",
            f"⚠️ <b>اهمیت:</b> {html.escape(e['impact'])}",
            f"🔮 <b>پیش‌بینی:</b> {html.escape(e.get('forecast') or '—')}",
            f"📚 <b>عدد قبلی:</b> {html.escape(e.get('previous') or '—')}",
            f"📍 <b>وضعیت:</b> {status}{result}",
        ])
    lines += [
        "",
        "━━━━━━━━━━━━━━━━━━━━",
        "",
        "برای رویدادهای مهم، سناریو و دیدگاه منابع در پیام‌های جداگانه منتشر می‌شود.",
        "",
        "<b>Gold Admin</b>",
        "<b>Reports Admin</b>",
    ]
    return "\n".join(lines)

def publish_session_schedule(state, now, holiday_data, all_events):
    sent = state.setdefault("session_daily_sent", {})
    key = now.date().isoformat()
    if sent.get(key):
        return
    send_long_telegram(session_status_text(now, holiday_data, all_events))
    sent[key] = now.isoformat()


def current_week_range(today):
    # Afghanistan's reporting week runs Saturday through Friday.
    week_start = today - timedelta(days=(today.weekday() - 5) % 7)
    return week_start, week_start + timedelta(days=6)


def get_week_calendar_events(today, days_ahead=0):
    # days_ahead=7 selects the next Saturday-Friday reporting week.
    week_start, week_end = current_week_range(today + timedelta(days=days_ahead))
    # A seven-day reporting week can touch two calendar months.
    month_refs = []
    for ref_date in (week_start, week_end):
        month_key = (ref_date.year, ref_date.month)
        if month_key not in [(d.year, d.month) for d in month_refs]:
            month_refs.append(ref_date)
    unique = {}
    for ref_date in month_refs:
        for event in get_calendar(ref_date):
            unique[(event["datetime_utc"], event["currency"], event["title"])] = event
    return sorted(unique.values(), key=lambda event: event["datetime_utc"])


def publish_scheduled_report(events, state, now, holiday_data):
    day = now.weekday()
    today = now.date()
    if day == 5:  # Saturday: current calendar month
        chosen = [e for e in events if date.fromisoformat(e["date"]).year == today.year
                  and date.fromisoformat(e["date"]).month == today.month]
        key, heading, period = f"month-{today:%Y-%m}", "تقویم و گزارش ماه جاری", today.strftime("%B %Y")
    elif day == 6:  # Sunday: upcoming Afghanistan week, Saturday through Friday
        start, end = current_week_range(today + timedelta(days=7))
        chosen = [e for e in events if start <= date.fromisoformat(e["date"]) <= end]
        key, heading, period = f"week-{start:%Y-%m-%d}", "اخبار و رویدادهای هفته پیشِ رو", f"{start} تا {end}"
    else:
        chosen = [e for e in events if e["date"] == today.isoformat()]
        key, heading, period = f"day-{today:%Y-%m-%d}", "اخبار و رویدادهای اقتصادی امروز", str(today)
    if state.setdefault("daily_sent", {}).get(key):
        return
    # Keep all high/medium-impact events and split long reports under Telegram's message limit.
    chosen = [e for e in chosen if e["impact"] in ("high", "medium")]
    send_long_telegram(report_message(chosen, heading, period, now, holiday_data, events))
    state["daily_sent"][key] = now.isoformat()

def monitor_events(events, state, now):
    utc_now = now.astimezone(ZoneInfo("UTC"))
    for e in events:
        if e["impact"] != "high":
            continue
        event_time = datetime.fromisoformat(e["datetime_utc"])
        delta = (event_time - utc_now).total_seconds()
        key = f'{e["date"]}|{e["currency"]}|{e["title"]}'
        if 0 < delta <= 3600 and not state["pre_sent"].get(key):
            send_telegram(event_message(e, pre=True))
            state["pre_sent"][key] = {"sent": now.isoformat(), "previous": e["previous"]}
        # A calendar page includes the entire month. Without an age limit, a
        # delayed/restarted monitor can publish every historical event as if it
        # had just happened, flooding the channel and triggering Telegram 429s.
        elif -POST_EVENT_GRACE.total_seconds() <= delta <= 0 and e["actual"] and not state["post_sent"].get(key):
            prior = state["pre_sent"].get(key, {}).get("previous", "")
            msg = event_message(e, pre=False)
            if prior and e["previous"] and prior != e["previous"]:
                msg += f"\n\n⚠️ <b>اصلاح عدد قبلی</b>\nقبلی در پیش‌تحلیل: {html.escape(prior)}\nعدد قبلی اصلاح‌شده: {html.escape(e['previous'])}"
            send_telegram(msg)
            state["post_sent"][key] = now.isoformat()

def main():
    if not TOKEN or not CHAT_ID:
        raise RuntimeError("Configure GOLD_REPORTS_BOT_TOKEN and GOLD_REPORTS_CHANNEL_ID GitHub secrets.")
    now = now_kabul()
    mode = os.environ.get("REPORTS_MODE", "monitor")
    events = (get_week_calendar_events(now.date(), days_ahead=7)
              if mode == "daily" and now.weekday() == 6
              else get_calendar(now.date()))
    state = load_state()
    holiday_data = fetch_public_holidays(state, now)
    if mode == "daily":
        publish_session_schedule(state, now, holiday_data, events)
        publish_scheduled_report(events, state, now, holiday_data)
    elif mode == "sessions":
        publish_session_schedule(state, now, holiday_data, events)
    elif mode == "test_news":
        send_telegram(test_news_message(events))
    elif mode == "test_pre_news":
        send_telegram(test_pre_news_message(events, now))
    else:
        monitor_events(events, state, now)
        monitor_session_boundaries(state, now, holiday_data, events)
    save_state(state)

if __name__ == "__main__":
    main()
