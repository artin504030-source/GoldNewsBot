#!/usr/bin/env python3
"""Standalone Gold Reports bot. Does not import or call any other project bot."""
from __future__ import annotations
import calendar
import html
import json
import os
import re
import sys
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
CHAT_ID = os.environ.get("CHANNEL_ID", "")
UA = {"User-Agent": "Mozilla/5.0 (compatible; GoldReportsBot/1.0)"}
FF_URL = "https://www.forexfactory.com/calendar"
GOOGLE_RSS = "https://news.google.com/rss/search?q={query}&hl=en-US&gl=US&ceid=US:en"

def now_kabul():
    return datetime.now(KABUL)

def load_state():
    try:
        return json.loads(STATE_FILE.read_text(encoding="utf-8"))
    except Exception:
        return {"pre_sent": {}, "post_sent": {}, "daily_sent": {}}

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
    tz_match = re.search(r"Calendar Time Zone:\s*([A-Za-z_]+/[A-Za-z_]+)", soup.get_text(" ", strip=True))
    calendar_tz = ZoneInfo(tz_match.group(1)) if tz_match else ZoneInfo("UTC")
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
        if not title or title.lower() in ("all day", "tentative"):
            continue
        event_dt = parse_ff_time(current_day, time_text, calendar_tz)
        if not event_dt:
            continue
        events.append({
            "date": current_day.isoformat(), "datetime_utc": event_dt.astimezone(ZoneInfo("UTC")).isoformat(),
            "datetime_kabul": event_dt.astimezone(KABUL).isoformat(), "title": title,
            "currency": currency, "impact": impact, "actual": actual, "forecast": forecast,
            "previous": previous, "source": url
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
    # This is a transparent headline-text signal, not a measured economist consensus.
    text = " ".join((a["title"] + " " + a["description"]) for a in articles).lower()
    higher = ["hotter than expected", "higher than expected", "sticky inflation", "inflation remains high",
              "hawkish", "stronger than expected", "rate hike", "upside surprise"]
    lower = ["cooler than expected", "lower than expected", "softening inflation", "disinflation",
             "dovish", "weaker than expected", "rate cut", "downside surprise"]
    hi = sum(text.count(x) for x in higher)
    lo = sum(text.count(x) for x in lower)
    if hi == lo:
        return "جهت غالب مشخص نیست؛ منابع بررسی‌شده اجماع روشنی نشان نمی‌دهند.", "نامشخص"
    if hi > lo:
        return "در تیترها و خلاصه‌های منابع بررسی‌شده، ریسک سناریوی بالاتر/قوی‌تر بیشتر دیده می‌شود؛ این اجماع رسمی نیست.", "بالاتر/قوی‌تر"
    return "در تیترها و خلاصه‌های منابع بررسی‌شده، ریسک سناریوی پایین‌تر/ضعیف‌تر بیشتر دیده می‌شود؛ این اجماع رسمی نیست.", "پایین‌تر/ضعیف‌تر"

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

def compare_actual_forecast(actual, forecast):
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
    if a > f:
        return "عدد واقعی بالاتر از پیش‌بینی منتشر شد."
    if a < f:
        return "عدد واقعی پایین‌تر از پیش‌بینی منتشر شد."
    return "عدد واقعی مطابق پیش‌بینی منتشر شد."

def event_message(event, pre=True):
    articles = analyst_sources(event)
    bias, label, impacts = scenario_text(event, articles)
    when = datetime.fromisoformat(event["datetime_kabul"]).strftime("%Y-%m-%d %H:%M")
    lines = [
        "🗓 <b>پیش‌تحلیل رویداد اقتصادی</b>" if pre else "📊 <b>نتیجه رویداد اقتصادی</b>",
        f"🌍 <b>{html.escape(event['currency'])} | {html.escape(event['title'])}</b>",
        f"🕘 زمان کابل: <code>{when}</code>",
        f"اهمیت: {html.escape(event['impact'])}",
        f"پیش‌بینی بازار: <b>{html.escape(event['forecast'] or 'در دسترس نیست')}</b>",
        f"عدد قبلی: {html.escape(event['previous'] or 'در دسترس نیست')}",
    ]
    if pre:
        lines += ["", "<b>دیدگاه منابع و تحلیل‌گران</b>", html.escape(bias),
                  f"جهت تیترهای بررسی‌شده: <b>{html.escape(label)}</b>",
                  "", "<b>سه سناریو</b>",
                  f"• مطابق انتظار: {html.escape(impacts[1])}",
                  f"• بالاتر از انتظار: {html.escape(impacts[0])}",
                  f"• پایین‌تر از انتظار: اثر معکوس سناریوی بالاتر؛ با توجه به نوع شاخص و واکنش بازده‌ها.",
                  "", "<b>منابع منتشرشده</b>"]
    else:
        lines += ["", f"عدد واقعی: <b>{html.escape(event['actual'] or 'هنوز در منبع ثبت نشده')}</b>",
                  f"پیش‌بینی: {html.escape(event['forecast'] or 'ناموجود')}",
                  f"مقایسه: {html.escape(compare_actual_forecast(event['actual'], event['forecast']))}",
                  f"عدد قبلی: {html.escape(event['previous'] or 'ناموجود')}",
                  "", "نتیجه با پیش‌بینی مقایسه می‌شود؛ اصلاح عدد قبلی فقط در صورت مشاهده تغییر در منبع اعلام می‌شود."]
    for a in articles[:4]:
        lines.append(f'• <a href="{html.escape(a["link"], quote=True)}">{html.escape(a["source"])}: {html.escape(a["title"][:130])}</a>')
    if not articles:
        lines.append("منابع تحلیلی قابل استناد برای این رویداد پیدا نشد؛ اجماع تحلیل‌گران اعلام نمی‌شود.")
    lines += ["", "<i>این گزارش سناریوها را توصیف می‌کند و توصیه معاملاتی یا تضمین جهت بازار نیست.</i>",
              "", "<b>Gold Admin</b>", "<b>Reports Admin</b>"]
    return "\n".join(lines)

def send_telegram(text):
    if not TOKEN or not CHAT_ID:
        raise RuntimeError("Missing GOLD_REPORTS_BOT_TOKEN or CHANNEL_ID secret")
    url = f"https://api.telegram.org/bot{TOKEN}/sendMessage"
    r = requests.post(url, json={"chat_id": CHAT_ID, "text": text, "parse_mode": "HTML",
                                 "disable_web_page_preview": True}, timeout=25)
    r.raise_for_status()
    data = r.json()
    if not data.get("ok"):
        raise RuntimeError(f"Telegram send failed: {data}")
    message_id = data["result"]["message_id"]
    pin_url = f"https://api.telegram.org/bot{TOKEN}/pinChatMessage"
    pin = requests.post(pin_url, json={"chat_id": CHAT_ID, "message_id": message_id,
                                       "disable_notification": True}, timeout=20)
    if not pin.ok or not pin.json().get("ok"):
        print(f"WARNING: message sent but pin failed: {pin.text[:300]}", file=sys.stderr)
    return message_id

def send_long_telegram(message, limit=3500):
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

def report_message(events, heading, period):
    lines = [f"📚 <b>{heading}</b>", f"دوره: <code>{period}</code>", ""]
    if not events:
        lines.append("رویداد مهمی در منبع تقویم پیدا نشد.")
    for e in events:
        dt = datetime.fromisoformat(e["datetime_kabul"]).strftime("%m-%d %H:%M")
        actual = f" | واقعی: {e['actual']}" if e["actual"] else ""
        lines.append(f"• <b>{html.escape(dt)} | {html.escape(e['currency'])}</b> — {html.escape(e['title'])} "
                     f"[{html.escape(e['impact'])}] | پیش‌بینی: {html.escape(e['forecast'] or '—')} "
                     f"| قبلی: {html.escape(e['previous'] or '—')}{html.escape(actual)}")
    lines += ["", "برای رویدادهای مهم، سناریو و دیدگاه منابع در پیام‌های جداگانه منتشر می‌شود.",
              "", "<b>Gold Admin</b>", "<b>Reports Admin</b>"]
    return "\n".join(lines)

def publish_scheduled_report(events, state, now):
    day = now.weekday()
    today = now.date()
    if day == 5:  # Saturday: current month
        chosen = [e for e in events if date.fromisoformat(e["date"]).month == today.month]
        key, heading, period = f"month-{today:%Y-%m}", "تقویم و گزارش ماه جاری", today.strftime("%B %Y")
    elif day == 6:  # Sunday: upcoming week
        end = today + timedelta(days=6)
        chosen = [e for e in events if today <= date.fromisoformat(e["date"]) <= end]
        key, heading, period = f"week-{today:%Y-%m-%d}", "چشم‌انداز هفته پیش‌رو", f"{today} تا {end}"
    else:
        chosen = [e for e in events if e["date"] == today.isoformat()]
        key, heading, period = f"day-{today:%Y-%m-%d}", "اخبار و رویدادهای اقتصادی امروز", str(today)
    if state["daily_sent"].get(key):
        return
    # Keep all high/medium-impact events and split long reports under Telegram's message limit.
    chosen = [e for e in chosen if e["impact"] in ("high", "medium")]
    send_long_telegram(report_message(chosen, heading, period))
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
        elif delta <= 0 and e["actual"] and not state["post_sent"].get(key):
            prior = state["pre_sent"].get(key, {}).get("previous", "")
            msg = event_message(e, pre=False)
            if prior and e["previous"] and prior != e["previous"]:
                msg += f"\n\n⚠️ <b>اصلاح عدد قبلی</b>\nقبلی در پیش‌تحلیل: {html.escape(prior)}\nعدد قبلی اصلاح‌شده: {html.escape(e['previous'])}"
            send_telegram(msg)
            state["post_sent"][key] = now.isoformat()

def main():
    if not TOKEN or not CHAT_ID:
        raise RuntimeError("Configure GOLD_REPORTS_BOT_TOKEN and CHANNEL_ID GitHub secrets.")
    now = now_kabul()
    events = get_calendar(now.date())
    state = load_state()
    mode = os.environ.get("REPORTS_MODE", "monitor")
    if mode == "daily":
        publish_scheduled_report(events, state, now)
    else:
        monitor_events(events, state, now)
    save_state(state)

if __name__ == "__main__":
    main()
