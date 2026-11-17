import json
import os
from collections import Counter
from datetime import datetime, timedelta, timezone
from pathlib import Path
import requests
from dotenv import load_dotenv
from gold_news_features import load_archive, fetch_calendar_events, kabul_time

BASE = Path(__file__).resolve().parent
load_dotenv(BASE / ".env")
TOKEN = os.getenv("BOT_TOKEN")
CHANNEL_ID = os.getenv("CHANNEL_ID")
REPORT_FILE = BASE / "daily_report.json"


def send(message):
    if os.getenv("DRY_RUN", "false").lower() == "true":
        print("[DRY RUN] Daily digest preview (not sent):\n" + message)
        return
    if not TOKEN or not CHANNEL_ID:
        raise SystemExit("Telegram settings missing")
    response = requests.post(
        f"https://api.telegram.org/bot{TOKEN}/sendMessage",
        data={"chat_id": CHANNEL_ID, "text": message, "disable_web_page_preview": True},
        timeout=25,
    )
    response.raise_for_status()
    result = response.json()
    if not result.get("ok"):
        raise RuntimeError(str(result))


def recent_archive_items(now):
    cutoff = now - timedelta(hours=24)
    recent = []
    for item in load_archive():
        raw = item.get("archived_at_utc") or item.get("published_utc") or ""
        try:
            stamp = datetime.fromisoformat(raw.replace("Z", "+00:00"))
            if stamp.tzinfo is None:
                stamp = stamp.replace(tzinfo=timezone.utc)
            if cutoff <= stamp.astimezone(timezone.utc) <= now:
                recent.append(item)
        except (TypeError, ValueError):
            continue
    return recent


def build_digest(now):
    recent = recent_archive_items(now)

    def score(item):
        try:
            relevance_score = int(item.get("relevance_score", 0) or 0)
        except (TypeError, ValueError):
            relevance_score = 0
        return relevance_score, {"زیاد": 3, "متوسط": 2, "کم": 1}.get(item.get("importance"), 0)

    recent.sort(key=score, reverse=True)
    importance = Counter(x.get("importance", "نامشخص") for x in recent)
    categories = Counter(x.get("category", "نامشخص") for x in recent)
    lines = [
        "📊 گزارش روزانه فاندامنتال طلا | Gold News",
        f"🕒 زمان تهیه: {kabul_time(now)}",
        "",
        "این گزارش مرور داده‌ها و خبرهای ثبت‌شده است؛ پیش‌بینی جهت قیمت یا سیگنال معاملاتی نیست.",
        "",
        f"📰 تعداد خبرهای ثبت‌شده در ۲۴ ساعت گذشته: {len(recent)}",
        f"🔴 اهمیت زیاد: {importance.get('زیاد', 0)} | 🟠 متوسط: {importance.get('متوسط', 0)} | 🟢 کم: {importance.get('کم', 0)}",
    ]
    if categories:
        lines.append("دسته‌های خبری: " + "؛ ".join(f"{name}: {count}" for name, count in categories.most_common(5)))
    lines.append("")
    lines.append("⭐ خبرهای مهم و مرتبط با طلا:")
    for item in recent[:8]:
        title = item.get("title", "بدون عنوان")
        lines.extend([
            f"• {title}",
            f"  ارتباط با طلا: {item.get('relevance', 'نامشخص')} ({item.get('relevance_score', 0)}/100) | اهمیت: {item.get('importance', 'نامشخص')}",
            f"  دسته: {item.get('category', 'نامشخص')} | منبع: {item.get('source', 'نامشخص')}",
            f"  زمان کابل: {item.get('published_kabul', 'نامشخص')}",
            f"  منابع ثبت‌کننده: {', '.join(item.get('confirmed_sources') or [item.get('source', 'نامشخص')])}",
            f"  {item.get('link', '')}",
        ])
    if not recent:
        lines.append("در ۲۴ ساعت گذشته خبر تازه‌ای در آرشیو ثبت نشده است.")

    events = []
    lines.extend(["", "📅 رویدادهای تقویم اقتصادی | Forex Factory"])
    try:
        events = fetch_calendar_events(12)
        if events:
            for event in events:
                lines.append(
                    f"• {event['country']} | {event['title']} | {event['date']} {event['time']} "
                    f"(منطقه زمانی منبع نامشخص) | اهمیت: {event['impact']} | "
                    f"پیش‌بینی: {event['forecast'] or '—'} | قبلی: {event['previous'] or '—'}"
                )
        else:
            lines.append("رویدادی از فید تقویم دریافت نشد.")
    except Exception as exc:
        print("Calendar unavailable:", exc)
        lines.append("تقویم اقتصادی فعلاً در دسترس نیست؛ زمان رویدادها را از منبع رسمی بررسی کنید.")

    lines.extend(["", "🔎 آرشیو و جست‌وجوی خبرها: بخش dashboard مخزن GoldNewsBot"])
    message = "\n".join(lines)[:3900]

    # Publish the exact bot-generated report data for the public website.
    report = {
        "generated_at_utc": now.isoformat(),
        "generated_at_kabul": kabul_time(now),
        "window_hours": 24,
        "message": message,
        "news": recent[:30],
        "calendar_events": events,
        "calendar_source": "Forex Factory public weekly XML feed",
        "calendar_timezone_note": "Source timezone is unspecified; event times are shown as provided."
    }
    REPORT_FILE.write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"Dashboard report saved: {REPORT_FILE.name} ({len(recent)} news items, {len(events)} calendar events)")
    return message


def main():
    now = datetime.now(timezone.utc)
    message = build_digest(now)
    send(message)
    print("Daily fundamental digest completed")


if __name__ == "__main__":
    main()
