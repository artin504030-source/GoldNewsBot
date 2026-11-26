from __future__ import annotations

from datetime import datetime, timezone, timedelta
from html import escape
from pathlib import Path
import re
import tempfile
import requests

YAHOO_SYMBOL = "GC=F"  # COMEX gold futures; used as a transparent proxy, not broker XAUUSD.


def parse_event_time(text):
    match = re.search(r"(20\d{2}-\d{2}-\d{2}\s+\d{2}:\d{2})", text or "")
    if not match:
        return None
    try:
        # Gold Reports prints Kabul local time.
        from zoneinfo import ZoneInfo
        return datetime.strptime(match.group(1), "%Y-%m-%d %H:%M").replace(tzinfo=ZoneInfo("Asia/Kabul")).astimezone(timezone.utc)
    except ValueError:
        return None


def numeric(value):
    match = re.search(r"[-+]?[0-9][0-9,]*(?:\.[0-9]+)?", value or "")
    if not match:
        return None
    try:
        return float(match.group(0).replace(",", ""))
    except ValueError:
        return None


def get_bars(session=None):
    session = session or requests.Session()
    response = session.get(
        f"https://query1.finance.yahoo.com/v8/finance/chart/{YAHOO_SYMBOL}",
        params={"range": "5d", "interval": "5m"},
        headers={"User-Agent": "Mozilla/5.0 GoldPricedInAnalyst/1.0"},
        timeout=20,
    )
    response.raise_for_status()
    result = response.json()["chart"]["result"][0]
    timestamps = result.get("timestamp") or []
    quote = result["indicators"]["quote"][0]
    closes = quote.get("close") or []
    points = [(datetime.fromtimestamp(int(ts), timezone.utc), float(px))
              for ts, px in zip(timestamps, closes) if px is not None]
    if len(points) < 10:
        raise ValueError("داده تاریخی کافی از قرارداد آتی طلا دریافت نشد.")
    return points


def classify_pre(points, event_dt, forecast, previous, event_name):
    now = datetime.now(timezone.utc)
    usable = [(t, p) for t, p in points if t <= now]
    if len(usable) < 10:
        return "اطلاعات کافی برای تشخیص وجود ندارد", "داده‌های قیمت پیش از گزارش کافی نیست."
    end_t, end_p = usable[-1]
    start = next(((t, p) for t, p in reversed(usable[:-1]) if end_t - t >= timedelta(hours=12)), None)
    if not start:
        return "اطلاعات کافی برای تشخیص وجود ندارد", "بازه مقایسه ۱۲ ساعته در داده‌های دریافتی موجود نیست."
    change = (end_p / start[1] - 1) * 100
    abs_move = abs(change)
    if abs_move < 0.20:
        return "شواهد کافی برای تأیید پیش‌خورشدن دیده نمی‌شود", f"تغییر ۱۲ ساعته قرارداد آتی طلا حدود {change:+.2f}% بوده؛ این داده به‌تنهایی ثابت نمی‌کند خبر پیش‌خور نشده باشد."
    if abs_move < 0.55:
        return "تا حدی پیش‌خور شده؛ شواهد محدود", f"تغییر ۱۲ ساعته حدود {change:+.2f}% است؛ اما بدون داده مستقل از انتظارات بازار، نتیجه قطعی نیست."
    return "احتمال پیش‌خورشدن بخشی از انتظارات؛ تأییدنشده", f"حرکت ۱۲ ساعته حدود {change:+.2f}% بوده است. برای اثبات پیش‌خورشدن باید با تغییر انتظارات نرخ بهره/دلار و خبرهای هم‌زمان تطبیق داده شود."


def classify_post(points, event_dt, actual, forecast):
    if not event_dt:
        return "زمان دقیق رویداد در پیام قابل استخراج نیست؛ واکنش پس از انتشار به‌طور معتبر جدا نمی‌شود."
    actual_n, forecast_n = numeric(actual), numeric(forecast)
    if actual_n is None or forecast_n is None:
        return "عدد واقعی یا پیش‌بینی قابل‌مقایسه نیست؛ غافلگیری آماری مشخص نشد."
    surprise = "بالاتر از پیش‌بینی" if actual_n > forecast_n else "پایین‌تر از پیش‌بینی" if actual_n < forecast_n else "مطابق پیش‌بینی"
    before = [(t, p) for t, p in points if event_dt - timedelta(minutes=60) <= t < event_dt]
    latest_time = max((t for t, _ in points), default=event_dt)
    window_end = min(event_dt + timedelta(hours=2), latest_time)
    after = [(t, p) for t, p in points if event_dt <= t <= window_end]
    if not before or len(after) < 2:
        return f"عدد واقعی {surprise} بود؛ اما هنوز داده کافی پس از زمان انتشار برای سنجش واکنش قیمت وجود ندارد."
    p0, p1 = before[-1][1], after[-1][1]
    move = (p1 / p0 - 1) * 100
    elapsed = max(0, int((after[-1][0] - event_dt).total_seconds() / 60))
    return f"عدد واقعی {surprise} بود. قرارداد آتی طلا در {elapsed} دقیقه نخستِ داده‌های موجود پس از انتشار {move:+.2f}% تغییر کرد. این واکنش مشاهده‌شده است؛ نسبت‌دادن تمام حرکت به خبر بدون کنترل اخبار هم‌زمان قطعی نیست."


def impact_text(kind, text, fields):
    event = fields.get("event", text.splitlines()[1] if len(text.splitlines()) > 1 else "رویداد اقتصادی")
    lower = event.lower()
    currency = "USD" if "usd" in lower or "دلار" in lower else "ارز مرتبط در پیام گزارش"
    if any(x in lower for x in ("cpi", "inflation", "pce", "تورم")):
        return ("تورم بالاتر از انتظار معمولاً انتظارات نرخ بهره و بازده واقعی را بالا می‌برد و می‌تواند به دلار کمک و بر طلا فشار وارد کند؛ تورم پایین‌تر می‌تواند مسیر معکوس داشته باشد. واکنش نهایی به اجزای گزارش و بازده اوراق بستگی دارد.",
                "نمادهای تحت نظر: XAUUSD، DXY و بازده اوراق آمریکا.")
    if any(x in lower for x in ("payroll", "employment", "unemployment", "اشتغال", "بیکاری")):
        return ("اشتغال قوی‌تر از انتظار می‌تواند احتمال سیاست پولی انقباضی‌تر را تقویت و به دلار کمک کند؛ ضعف غیرمنتظره می‌تواند از طلا حمایت کند. دستمزد و نرخ مشارکت نیز مهم‌اند.",
                "نمادهای تحت نظر: XAUUSD، DXY و بازده اوراق آمریکا.")
    if any(x in lower for x in ("interest rate", "fomc", "fed", "نرخ بهره", "فدرال")):
        return ("تصمیم یا لحن انقباضی‌تر از انتظار می‌تواند دلار و بازده اوراق را تقویت و بر طلا فشار وارد کند؛ لحن نرم‌تر می‌تواند اثر معکوس داشته باشد.",
                "نمادهای تحت نظر: XAUUSD، DXY، بازده ۲ و ۱۰ ساله آمریکا.")
    return (f"اثر {currency} بر طلا عمدتاً از مسیر دلار، انتظارات نرخ بهره و بازده اوراق منتقل می‌شود. جهت اثر این رویداد بدون شناخت دقیق شاخص و اجزای آن قطعی نیست.",
            "نماد اصلی بررسی: XAUUSD؛ در صورت ارتباط با دلار، DXY و بازده اوراق نیز مهم‌اند.")


def analyze_report(kind, text, fields):
    event_dt = parse_event_time(fields.get("time", text))
    try:
        points = get_bars()
    except Exception as exc:
        points = []
        data_error = f"داده چارت دریافت نشد ({type(exc).__name__})."
    else:
        data_error = ""
    impact, symbols = impact_text(kind, text, fields)
    lines = ["🟡 <b>بررسی پیش‌خورشدن و واکنش بازار</b>", ""]
    if kind == "pre":
        if points:
            status, evidence = classify_pre(points, event_dt, fields.get("forecast", ""), fields.get("previous", ""), text)
        else:
            status, evidence = "اطلاعات کافی برای تشخیص وجود ندارد", data_error
        lines += [f"🔎 <b>وضعیت پیش‌خورشدن:</b> {escape(status)}", escape(evidence)]
        lines += ["", "<b>انتظارات و ریسک رویداد</b>", escape(impact)]
        lines += ["", "<b>نمادهای مرتبط</b>", escape(symbols)]
        lines += ["", "توجه: حرکت قیمت به‌تنهایی اثبات نمی‌کند خبر پیش‌خور شده است. برای نتیجه قطعی، داده انتظارات بازار و تغییرات نرخ/دلار نیز لازم است."]
    else:
        if points:
            reaction = classify_post(points, event_dt, fields.get("actual", ""), fields.get("forecast", ""))
        else:
            reaction = data_error
        lines += [f"📊 <b>واکنش پس از انتشار:</b> {escape(reaction)}", "", "<b>تأثیر بنیادی احتمالی</b>", escape(impact)]
        lines += ["", "<b>نمادهای مرتبط</b>", escape(symbols)]
        lines += ["", "واکنش کوتاه‌مدت قرارداد آتی طلا نماینده دقیق قیمت اجرایی XAUUSD نیست و ممکن است تحت‌تأثیر خبرهای هم‌زمان باشد."]
    lines += ["", "<i>منبع چارت: Yahoo Finance، قرارداد آتی طلا GC=F؛ داده ممکن است با تأخیر باشد. این گزارش سیگنال خرید یا فروش نیست.</i>",
              "", "<b>Gold Admin</b>", "<b>Priced-In Admin</b>"]
    return "\n".join(lines), "GC=F", event_dt


def make_chart(symbol, event_dt, kind):
    import matplotlib
    matplotlib.use("Agg")
    import matplotlib.pyplot as plt
    points = get_bars()
    now = datetime.now(timezone.utc)
    if kind == "pre":
        selected = [(t, p) for t, p in points if t >= now - timedelta(hours=36) and t <= now]
        title = "Gold futures — pre-release price action"
    else:
        anchor = event_dt or now
        selected = [(t, p) for t, p in points if anchor - timedelta(hours=8) <= t <= anchor + timedelta(hours=8)]
        if len(selected) < 5:
            selected = [(t, p) for t, p in points if t >= now - timedelta(hours=24)]
        title = "Gold futures — post-release reaction"
    if len(selected) < 5:
        raise ValueError("Not enough chart bars for a readable image.")
    fig, ax = plt.subplots(figsize=(10, 5), dpi=140)
    times = [t for t, _ in selected]
    prices = [p for _, p in selected]
    ax.plot(times, prices, linewidth=1.6)
    if event_dt:
        ax.axvline(event_dt, linestyle="--", linewidth=1.2)
        ax.text(event_dt, max(prices), " Release", va="top")
    ax.set_title(title)
    ax.set_xlabel("Time (UTC)")
    ax.set_ylabel("USD per troy ounce")
    ax.grid(True, alpha=0.25)
    fig.autofmt_xdate()
    fig.tight_layout()
    fd, path = tempfile.mkstemp(prefix="gold-priced-in-", suffix=".png")
    import os
    os.close(fd)
    fig.savefig(path, format="png")
    plt.close(fig)
    note = "چارت قرارداد آتی طلا (GC=F)؛ خط‌چین زمان انتشار رویداد را نشان می‌دهد." if event_dt else "چارت قرارداد آتی طلا (GC=F)؛ زمان انتشار دقیق در پیام قابل استخراج نبود."
    return path, note
