
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
    # آمریکا
    "Federal Reserve": "https://www.federalreserve.gov/feeds/press_all.xml",
    "BLS": "https://www.bls.gov/feed/bls_latest.rss",
    "BEA": "https://apps.bea.gov/rss/rss.xml",

    # اروپا و بریتانیا
    "European Central Bank": "https://www.ecb.europa.eu/rss/press.html",
    "Eurostat": "https://ec.europa.eu/eurostat/cache/RSS/rss_estat_news.xml",
    "Bank of England": "https://www.bankofengland.co.uk/rss/news",

    # ژاپن
    "Bank of Japan": "https://www.boj.or.jp/en/rss/whatsnew.xml",

    # اخبار اقتصاد و بازار جهانی
    "Gold Market": "https://news.google.com/rss/search?q=gold+OR+bullion+OR+precious+metals&hl=en-US&gl=US&ceid=US:en",

    "Forex and Central Banks": "https://news.google.com/rss/search?q=Federal+Reserve+OR+ECB+OR+Bank+of+England+OR+Bank+of+Japan+OR+forex+OR+currency&hl=en-US&gl=US&ceid=US:en",

    "Economic Reports": "https://news.google.com/rss/search?q=CPI+OR+PCE+OR+GDP+OR+NFP+OR+inflation+OR+interest+rates+OR+unemployment+OR+PMI&hl=en-US&gl=US&ceid=US:en",

    "Geopolitical News": "https://news.google.com/rss/search?q=war+OR+sanctions+OR+Iran+OR+Israel+OR+Ukraine+OR+China+OR+trade+war+OR+tariffs&hl=en-US&gl=US&ceid=US:en",

    "Oil and Energy": "https://news.google.com/rss/search?q=crude+oil+OR+OPEC+OR+oil+prices+OR+natural+gas+OR+energy+markets&hl=en-US&gl=US&ceid=US:en",

    "China and Global Markets": "https://news.google.com/rss/search?q=China+economy+OR+Asian+markets+OR+Wall+Street+OR+stock+markets+OR+global+economy&hl=en-US&gl=US&ceid=US:en",
}

KEYWORDS = [
    # طلا و فلزات گران‌بها
    "gold", "bullion", "precious metals",
    "gold price", "gold market", "gold demand",
    "gold reserves", "central bank gold",

    # تورم و اقتصاد آمریکا
    "cpi", "core cpi", "pce", "core pce",
    "inflation", "ppi", "gdp", "nfp",
    "nonfarm payroll", "unemployment",
    "employment", "retail sales", "consumer spending",
    "consumer confidence", "pmi", "ism",

    # بانک‌های مرکزی و نرخ بهره
    "federal reserve", "fed", "powell",
    "fomc", "ecb", "european central bank",
    "bank of england", "boe",
    "bank of japan", "boj",
    "interest rate", "rate decision",
    "monetary policy", "quantitative easing",

    # ارزها
    "us dollar", "dollar index", "dxy",
    "euro", "eurusd", "sterling", "british pound",
    "gbpusd", "japanese yen", "usdjpy",
    "forex", "foreign exchange", "currency",
    "exchange rate",

    # اوراق قرضه و بازارها
    "treasury yields", "bond yields",
    "government bonds", "stock market",
    "wall street", "equity markets",
    "market selloff", "market rally",

    # نفت و انرژی
    "crude oil", "brent", "wti",
    "opec", "natural gas", "energy prices",

    # چین و اقتصاد جهانی
    "china economy", "chinese economy",
    "pboc", "people's bank of china",
    "trade war", "global economy",
    "economic crisis", "banking crisis",

    # اخبار سیاسی و ژئوپلیتیکی
    "war", "military strike", "missile",
    "airstrike", "ceasefire", "invasion",
    "sanctions", "geopolitical",
    "iran", "israel", "middle east",
    "ukraine", "russia", "nuclear",
    "tariffs", "trade restrictions",
    "peace talks", "political crisis"
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

    print("Gold News Bot started.")

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
                    print("News sent:", title)

                seen.add(uid)
                save_seen(seen)

        except Exception as error:
            print(f"Error in {source}: {error}")

    if not initialized:
        save_seen(seen)
        print("Initial news history saved.")

    print("News check completed.")


if __name__ == "__main__":
    main()
