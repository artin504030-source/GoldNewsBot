
import os
import re
import json
import time
import html
import requests
import feedparser


from pathlib import Path
from dotenv import load_dotenv

BASE_DIR = Path(__file__).resolve().parent
load_dotenv(BASE_DIR / ".env")

TOKEN = os.getenv("BOT_TOKEN")
CHANNEL_ID = os.getenv("CHANNEL_ID")

if not TOKEN or not CHANNEL_ID:
    raise SystemExit("تنظیمات تلگرام پیدا نشد.")

STATE_FILE = BASE_DIR / "seen_news.json"
CHECK_INTERVAL = 120

FEEDS = {
    "Federal Reserve": "https://www.federalreserve.gov/feeds/press_all.xml",
    "BLS": "https://www.bls.gov/feed/bls_latest.rss",
    "BEA": "https://apps.bea.gov/rss/rss.xml",
    "Gold Market News": "https://news.google.com/rss/search?q=gold+OR+bullion+OR+precious+metals+when:1d&hl=en-US&gl=US&ceid=US:en",
    "US Economic Reports": "https://news.google.com/rss/search?q=US+CPI+OR+PCE+OR+GDP+OR+payrolls+OR+inflation+OR+FOMC+OR+interest+rates+OR+unemployment+when:1d&hl=en-US&gl=US&ceid=US:en",
}

KEYWORDS = [
    "cpi",
    "core cpi",
    "inflation",
    "consumer price",
    "pce",
    "core pce",
    "nonfarm payroll",
    "employment situation",
    "unemployment",
    "job openings",
    "labor market",
    "fomc",
    "federal funds",
    "interest rate",
    "monetary policy",
    "federal reserve",
    "powell",
    "gross domestic product",
    "gdp",
    "personal income",
    "consumer spending",
    "retail sales",
    "producer price",
    "ppi",
    "treasury yields",
    "bond yields",
    "us dollar",
    "dollar index",
    "dxy",
    "gold",
    "bullion",
    "precious metals",
    "gold price",
    "gold market",
    "gold demand",
    "central bank gold",
    "gold reserves",
    "central bank purchases",
    "world gold council"
]

API_URL = f"https://api.telegram.org/bot{TOKEN}/sendMessage"

def load_seen():
    if STATE_FILE.exists():
        try:
            return set(json.loads(STATE_FILE.read_text(encoding="utf-8")))
        except Exception:
            print("هشدار: فایل سوابق قابل خواندن نیست.")
    return set()

def save_seen(seen):
    STATE_FILE.write_text(
        json.dumps(list(seen), ensure_ascii=False),
        encoding="utf-8"
    )

def send_telegram(message):
    response = requests.post(
        API_URL,
        data={
            "chat_id": CHANNEL_ID,
            "text": message,
            "disable_web_page_preview": True
        },
        timeout=25
    )
    response.raise_for_status()

    result = response.json()
    if not result.get("ok"):
        raise RuntimeError(str(result))

def get_entries(url):
    response = requests.get(
        url,
        headers={"User-Agent": "GoldNewsBot/1.0"},
        timeout=25
    )
    response.raise_for_status()
    return feedparser.parse(response.content).entries

def clean_summary(value):
    value = re.sub(r"<[^>]+>", " ", value or "")
    value = html.unescape(value)
    return re.sub(r"\s+", " ", value).strip()[:1000]

def is_relevant(title, summary):
    text = (title + " " + summary).lower()
    return any(word in text for word in KEYWORDS)

def entry_id(entry):
    return (
        entry.get("id")
        or entry.get("link")
        or entry.get("title", "")
    )


def translate_to_persian(text):
    try:
        response = requests.get(
            "https://api.mymemory.translated.net/get",
            params={
                "q": text[:4500],
                "langpair": "en|fa"
            },
            timeout=20
        )
        response.raise_for_status()
        data = response.json()

        if data.get("responseStatus") == 200:
            return data["responseData"]["translatedText"]

        print("خطای ترجمه:", data.get("responseDetails"))
        return "ترجمه فارسی فعلاً در دسترس نیست."

    except Exception as error:
        print("خطای سرویس ترجمه:", error)
        return "ترجمه فارسی فعلاً در دسترس نیست."

def make_message(source, entry):
    title = entry.get("title", "بدون عنوان")
    summary = clean_summary(entry.get("summary", ""))
    link = entry.get("link", "")
    published = entry.get("published", "زمان نامشخص")

    if summary:
        persian_summary = translate_to_persian(summary)
    else:
        persian_summary = "منبع خلاصه‌ای ارائه نکرده است."

    return (
        "🟡 گزارش خبری بازار طلا | XAUUSD\n\n"
        f"📰 عنوان: {title}\n"
        f"🏛 منبع: {source}\n"
        f"🕒 زمان انتشار: {published}\n\n"
        "🇬🇧 ENGLISH SUMMARY:\n"
        f"{summary or 'No summary provided by source.'}\n\n"
        "🇮🇷 خلاصه فارسی:\n"
        f"{persian_summary}\n\n"
        f"🔗 لینک گزارش اصلی:\n{link}"
    )[:4000]

def main():
    seen = load_seen()
    initialized = STATE_FILE.exists()

    print("Gold News Bot شروع شد.")
    print("بررسی منابع هر ۲ دقیقه انجام می‌شود.")

    while True:
        try:
            for source, url in FEEDS.items():
                try:
                    entries = get_entries(url)

                    for entry in reversed(entries):
                        uid = source + ":" + entry_id(entry)

                        if not uid.strip() or uid in seen:
                            continue

                        title = entry.get("title", "")
                        summary = entry.get("summary", "")

                        if initialized and is_relevant(title, summary):
                            message = make_message(source, entry)
                            send_telegram(message)
                            print("خبر ارسال شد:", title)

                        seen.add(uid)
                        save_seen(seen)

                except Exception as error:
                    print(f"خطا در منبع {source}: {error}")

            if not initialized:
                initialized = True
                save_seen(seen)
                print("آماده شد؛ خبرهای بعدی ارسال خواهند شد.")

        except Exception as error:
            print("خطای عمومی:", error)

        time.sleep(CHECK_INTERVAL)

if __name__ == "__main__":
    main()
