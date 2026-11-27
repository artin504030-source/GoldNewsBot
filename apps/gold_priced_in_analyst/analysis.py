from __future__ import annotations

from datetime import datetime, timezone, timedelta
from html import escape
from pathlib import Path
import re
import tempfile
import requests

YAHOO_SYMBOL = "GC=F"  # COMEX gold futures; used as a transparent proxy, not broker XAUUSD.
CROSS_MARKET_SYMBOLS = {"DXY": "DX-Y.NYB", "US10Y": "^TNX"}


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



def get_cross_market_bars(session=None):
    """Best-effort DXY and US 10Y nominal-yield proxies."""
    session = session or requests.Session()
    result, errors = {}, {}
    for label, symbol in CROSS_MARKET_SYMBOLS.items():
        try:
            response = session.get(
                f"https://query1.finance.yahoo.com/v8/finance/chart/{symbol}",
                params={"range": "5d", "interval": "5m"},
                headers={"User-Agent": "Mozilla/5.0 GoldPricedInAnalyst/1.0"},
                timeout=20,
            )
            response.raise_for_status()
            payload = response.json()["chart"]["result"][0]
            timestamps = payload.get("timestamp") or []
            closes = payload["indicators"]["quote"][0].get("close") or []
            points = [(datetime.fromtimestamp(int(ts), timezone.utc), float(px))
                      for ts, px in zip(timestamps, closes) if px is not None]
            if len(points) < 10:
                raise ValueError("insufficient bars")
            result[label] = points
        except Exception as exc:
            errors[label] = type(exc).__name__
    return result, errors


def _change(points, start, end):
    rows = [(t, p) for t, p in (points or []) if start <= t <= end]
    if len(rows) < 2 or rows[0][1] == 0:
        return None
    return (rows[-1][1] / rows[0][1] - 1) * 100


def _cross_market_lines(data, start, end):
    labels = {"DXY": "شاخص دلار", "US10Y": "بازده اسمی اوراق ۱۰ساله"}
    output = []
    for key, label in labels.items():
        change = _change((data or {}).get(key), start, end)
        output.append(f"{label}: {change:+.2f}%" if change is not None else f"{label}: داده کافی نیست")
    return output


def expected_gold_direction(event_name, forecast, previous):
    name = (event_name or "").lower()
    f, p = numeric(forecast), numeric(previous)
    if f is None or p is None or f == p:
        return None
    if any(x in name for x in ("cpi", "inflation", "pce", "تورم", "payroll", "employment", "اشتغال")):
        return "down" if f > p else "up"
    if any(x in name for x in ("unemployment", "بیکاری")):
        return "down" if f < p else "up"
    return None


def classify_pre(points, event_dt, forecast, previous, event_name, cross_market=None):
    now = datetime.now(timezone.utc)
    usable = [(t, p) for t, p in points if t <= now]
    if len(usable) < 10:
        return "اطلاعات کافی برای تشخیص وجود ندارد", "داده‌های قیمت پیش از گزارش کافی نیست."
    end_t, end_p = usable[-1]
    start = next(((t, p) for t, p in reversed(usable[:-1]) if end_t - t >= timedelta(hours=12)), None)
    if not start:
        return "اطلاعات کافی برای تشخیص وجود ندارد", "بازه مقایسه ۱۲ ساعته در داده‌های دریافتی موجود نیست."
    change = (end_p / start[1] - 1) * 100
    expected = expected_gold_direction(event_name, forecast, previous)
    if expected is None:
        return "اطلاعات کافی برای تشخیص وجود ندارد", (
            f"تغییر ۱۲ ساعته طلا {change:+.2f}% بوده؛ اما از پیش‌بینی و عدد قبلی، جهت مورد انتظار این رویداد قابل استنتاج مطمئن نیست."
        )
    aligned = (change < 0 and expected == "down") or (change > 0 and expected == "up")
    cross_start = end_t - timedelta(hours=12)
    dxy = _change((cross_market or {}).get("DXY"), cross_start, end_t)
    us10y = _change((cross_market or {}).get("US10Y"), cross_start, end_t)
    cross_agrees = dxy is not None and us10y is not None and (
        (expected == "up" and dxy < 0 and us10y < 0) or
        (expected == "down" and dxy > 0 and us10y > 0)
    )
    cross_note = "؛ ".join(_cross_market_lines(cross_market, cross_start, end_t))
    if abs(change) < 0.20:
        return "شواهد کافی برای تأیید پیش‌خورشدن دیده نمی‌شود", (
            f"تغییر ۱۲ ساعته طلا {change:+.2f}% بوده و حرکت هم‌جهت معناداری با اثر مورد انتظار دیده نمی‌شود؛ این به‌تنهایی نبود پیش‌خورشدن را ثابت نمی‌کند."
        )
    if aligned:
        return "تا حدی پیش‌خور شده؛ شواهد محدود", (
            f"تغییر ۱۲ ساعته طلا {change:+.2f}% و هم‌جهت با اثر معمولِ مورد انتظار از ارقام پیش‌بینی/قبلی است. وضعیت بازارهای تأییدی: {cross_note}. " + ("دلار و بازده نیز هم‌جهت‌اند؛ شواهد چندبازاری قوی‌تر است، اما اثبات قطعی نیست." if cross_agrees else "تأیید هم‌زمان دلار و بازده کامل نیست؛ اطمینان محدود باقی می‌ماند.")
        )
    return "شواهد کافی برای تأیید پیش‌خورشدن دیده نمی‌شود", (
        f"تغییر ۱۲ ساعته طلا {change:+.2f}% با جهت معمولِ مورد انتظار از ارقام پیش‌بینی/قبلی هم‌راستا نیست. خبر ممکن است از مسیر دیگری قیمت‌گذاری شده باشد؛ داده تکمیلی لازم است. وضعیت بازارهای تأییدی: {cross_note}."
    )

def classify_post(points, event_dt, actual, forecast, cross_market=None):
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
    cross_note = "؛ ".join(_cross_market_lines(cross_market, event_dt - timedelta(minutes=60), window_end))
    return f"عدد واقعی {surprise} بود. قرارداد آتی طلا در {elapsed} دقیقه نخستِ داده‌های موجود پس از انتشار {move:+.2f}% تغییر کرد. وضعیت بازارهای هم‌زمان: {cross_note}. این واکنش مشاهده‌شده است؛ نسبت‌دادن تمام حرکت به خبر بدون کنترل اخبار هم‌زمان قطعی نیست."


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
    cross_market, cross_errors = get_cross_market_bars()
    impact, symbols = impact_text(kind, text, fields)
    lines = ["🟡 <b>بررسی پیش‌خورشدن و واکنش بازار</b>", ""]
    if kind == "pre":
        if points:
            status, evidence = classify_pre(points, event_dt, fields.get("forecast", ""), fields.get("previous", ""), text, cross_market)
        else:
            status, evidence = "اطلاعات کافی برای تشخیص وجود ندارد", data_error
        lines += [f"🔎 <b>وضعیت پیش‌خورشدن:</b> {escape(status)}", escape(evidence)]
        lines += ["", "<b>انتظارات و ریسک رویداد</b>", escape(impact)]
        lines += ["", "<b>نمادهای مرتبط</b>", escape(symbols)]
        lines += ["", "توجه: حرکت قیمت به‌تنهایی اثبات نمی‌کند خبر پیش‌خور شده است. برای نتیجه قطعی، داده انتظارات بازار و تغییرات نرخ/دلار نیز لازم است."]
    else:
        if points:
            reaction = classify_post(points, event_dt, fields.get("actual", ""), fields.get("forecast", ""), cross_market)
        else:
            reaction = data_error
        lines += [f"📊 <b>واکنش پس از انتشار:</b> {escape(reaction)}", "", "<b>تأثیر بنیادی احتمالی</b>", escape(impact)]
        lines += ["", "<b>نمادهای مرتبط</b>", escape(symbols)]
        lines += ["", "واکنش کوتاه‌مدت قرارداد آتی طلا نماینده دقیق قیمت اجرایی XAUUSD نیست و ممکن است تحت‌تأثیر خبرهای هم‌زمان باشد."]
    lines += ["", "<b>وضعیت داده‌های بین‌بازاری</b>"]
    for label, symbol in CROSS_MARKET_SYMBOLS.items():
        if label in cross_errors:
            lines.append(f"• {escape(label)} ({escape(symbol)}): دریافت نشد؛ تحلیل با محدودیت داده همراه است.")
        else:
            latest = cross_market[label][-1][0]
            age = max(0, int((datetime.now(timezone.utc) - latest).total_seconds() / 60))
            lines.append(f"• {escape(label)} ({escape(symbol)}): آخرین کندل {age} دقیقه قبل.")
    lines += ["", "<i>منابع: Yahoo Finance؛ طلا GC=F (قرارداد آتی، نه قیمت اجرایی XAUUSD)، دلار DX-Y.NYB و ^TNX (بازده اسمی ۱۰ساله، نه بازده واقعی). داده‌ها ممکن است با تأخیر باشند. این گزارش سیگنال خرید یا فروش نیست.</i>",
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
        title = "Gold futures — post-release reaction"
    if len(selected) < 5:
        selected = points[-100:]
        title += " — full available data window"
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
