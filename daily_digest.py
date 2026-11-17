import os
from datetime import datetime, timedelta, timezone
from pathlib import Path
import requests
from dotenv import load_dotenv
from gold_news_features import load_archive, fetch_calendar_events, kabul_time

BASE = Path(__file__).resolve().parent
load_dotenv(BASE / ".env")
TOKEN = os.getenv("BOT_TOKEN")
CHANNEL_ID = os.getenv("CHANNEL_ID")


def send(text):
    if os.getenv("DRY_RUN", "false").lower() == "true":
        print("[DRY RUN] Daily digest preview (not sent):\n" + text)
        return
    if not TOKEN or not CHANNEL_ID:
        raise SystemExit("Telegram settings missing")
    response = requests.post(f"https://api.telegram.org/bot{TOKEN}/sendMessage",
        data={"chat_id": CHANNEL_ID, "text": text, "disable_web_page_preview": True}, timeout=25)
    response.raise_for_status()
    result = response.json()
    if not result.get("ok"):
        raise RuntimeError(str(result))


def main():
    now = datetime.now(timezone.utc)
    cutoff = now - timedelta(hours=24)
    recent = []
    for item in load_archive():
        try:
            stamp = datetime.fromisoformat(item.get("archived_at_utc", "").replace("Z", "+00:00"))
            if stamp >= cutoff:
                recent.append(item)
        except Exception:
            continue
    recent.sort(key=lambda x: (x.get("relevance_score", 0), x.get("importance", "")), reverse=True)
    lines = ["📊 گزارش روزانه فاندامنتال طلا", f"🕒 زمان گزارش: {kabul_time(now)}", "",
             "این گزارش فقط مرور خبرهاست و پیش‌بینی جهت قیمت یا سیگنال معاملاتی نیست.", "",
             f"📰 خبرهای ثبت‌شده در ۲۴ ساعت گذشته: {len(recent)}"]
    for item in recent[:10]:
        lines.extend([f"• {item.get('title','بدون عنوان')}",
                      f"  ارتباط با طلا: {item.get('relevance','نامشخص')} ({item.get('relevance_score',0)}/100) | اهمیت: {item.get('importance','نامشخص')}",
                      f"  منبع: {item.get('source','نامشخص')} | {item.get('published_kabul','')}",
                      f"  {item.get('link','')}"])
    if not recent:
        lines.append("در آرشیو ۲۴ ساعت گذشته خبری ثبت نشده است.")
    lines.extend(["", "📅 رویدادهای تقویم اقتصادی (منبع: Forex Factory)"])
    try:
        events = fetch_calendar_events(15)
        if events:
            for e in events:
                lines.append(f"• {e['country']} | {e['title']} | زمان درج‌شده در فید (منطقه زمانی نامشخص): {e['date']} {e['time']} | اهمیت: {e['impact']} | پیش‌بینی: {e['forecast'] or '—'} | قبلی: {e['previous'] or '—'}")
        else:
            lines.append("رویدادی از فید تقویم دریافت نشد.")
    except Exception as exc:
        print("Calendar unavailable:", exc)
        lines.append("تقویم اقتصادی فعلاً در دسترس نیست؛ زمان‌بندی رویدادها را از منبع رسمی بررسی کنید.")
    send("\n".join(lines)[:3900])
    print("Daily fundamental digest sent")

if __name__ == "__main__":
    main()
