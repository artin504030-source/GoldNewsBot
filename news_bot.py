
import os
import re
import json
import html
import time
import requests
import feedparser

from pathlib import Path
from dotenv import load_dotenv

# -----------------------------
# تنظیمات اولیه
# -----------------------------

BASE_DIR = Path(__file__).resolve().parent
load_dotenv(BASE_DIR / ".env")

TOKEN = os.getenv("BOT_TOKEN")
CHANNEL_ID = os.getenv("CHANNEL_ID")

if not TOKEN or not CHANNEL_ID:
    raise SystemExit("تنظیمات تلگرام پیدا نشد.")

STATE_FILE = BASE_DIR / "seen_news.json"

API_URL = f"https://api.telegram.org/bot{TOKEN}/sendMessage"

# -----------------------------
# منابع خبری
# -----------------------------

FEEDS = {
    "Federal Reserve": "https://www.federalreserve.gov/feeds/press_all.xml",
    "BLS": "https://www.bls.gov/feed/bls_latest.rss",
    "BEA": "https://apps.bea.gov/rss/rss.xml",

    "European Central Bank": "https://www.ecb.europa.eu/rss/press.html",
    "Eurostat": "https://ec.europa.eu/eurostat/cache/RSS/rss_estat_news.xml",
    "Bank of England": "https://www.bankofengland.co.uk/rss/news",

    "Bank of Japan": "https://www.boj.or.jp/en/rss/whatsnew.xml",

    "Gold Market": "https://news.google.com/rss/search?q=gold+OR+bullion+OR+precious+metals&hl=en-US&gl=US&ceid=US:en",

    "Forex and Central Banks": "https://news.google.com/rss/search?q=Federal+Reserve+OR+ECB+OR+Bank+of+England+OR+Bank+of+Japan+OR+forex+OR+currency&hl=en-US&gl=US&ceid=US:en",

    "Economic Reports": "https://news.google.com/rss/search?q=CPI+OR+PCE+OR+GDP+OR+NFP+OR+inflation+OR+interest+rates+OR+unemployment+OR+PMI&hl=en-US&gl=US&ceid=US:en",

    "Geopolitical News": "https://news.google.com/rss/search?q=war+OR+sanctions+OR+Iran+OR+Israel+OR+Ukraine+OR+China+OR+trade+war+OR+tariffs&hl=en-US&gl=US&ceid=US:en",

    "Oil and Energy": "https://news.google.com/rss/search?q=crude+oil+OR+OPEC+OR+oil+prices+OR+natural+gas+OR+energy+markets&hl=en-US&gl=US&ceid=US:en",

    "China and Global Markets": "https://news.google.com/rss/search?q=China+economy+OR+Asian+markets+OR+Wall+Street+OR+stock+markets+OR+global+economy&hl=en-US&gl=US&ceid=US:en",
}

# -----------------------------
# کلمات کلیدی اخبار مرتبط
# -----------------------------

KEYWORDS = [
    "gold", "bullion", "precious metals",
    "gold price", "gold market", "gold demand",
    "gold reserves", "central bank gold",

    "cpi", "core cpi", "pce", "core pce",
    "inflation", "ppi", "gdp", "nfp",
    "nonfarm payroll", "unemployment",
    "employment", "retail sales", "consumer spending",
    "consumer confidence", "pmi", "ism",

    "federal reserve", "fed", "powell",
    "fomc", "ecb", "european central bank",
    "bank of england", "boe",
    "bank of japan", "boj",
    "interest rate", "rate decision",
    "monetary policy", "quantitative easing",

    "us dollar", "dollar index", "dxy",
    "euro", "eurusd", "sterling", "british pound",
    "gbpusd", "japanese yen", "usdjpy",
    "forex", "foreign exchange", "currency",
    "exchange rate",

    "treasury yields", "bond yields",
    "government bonds", "stock market",
    "wall street", "equity markets",
    "market selloff", "market rally",

    "crude oil", "brent", "wti",
    "opec", "natural gas", "energy prices",

    "china economy", "chinese economy",
    "pboc", "people's bank of china",
    "trade war", "global economy",
    "economic crisis", "banking crisis",

    "war", "military strike", "missile",
    "airstrike", "ceasefire", "invasion",
    "sanctions", "geopolitical",
    "iran", "israel", "middle east",
    "ukraine", "russia", "nuclear",
    "tariffs", "trade restrictions",
    "peace talks", "political crisis"
]

# -----------------------------
# مدیریت سوابق اخبار
# -----------------------------

def load_seen():
    if STATE_FILE.exists():
        try:
            return set(
                json.loads(
                    STATE_FILE.read_text(encoding="utf-8")
                )
            )
        except Exception:
            print("هشدار: فایل سوابق قابل خواندن نیست.")

    return set()


def save_seen(seen):
    STATE_FILE.write_text(
        json.dumps(list(seen), ensure_ascii=False),
        encoding="utf-8"
    )


# -----------------------------
# دریافت و ارسال تلگرام
# -----------------------------

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


# -----------------------------
# پاکسازی متن خبر
# -----------------------------

def clean_summary(value):
    value = re.sub(r"<[^>]+>", " ", value or "")
    value = html.unescape(value)
    value = re.sub(r"\s+", " ", value).strip()

    return value


def shorten_summary(summary, max_length=500):
    summary = clean_summary(summary)

    if not summary:
        return ""

    # حذف عنوان تکراری از ابتدای خلاصه
    return summary[:max_length].strip()


# -----------------------------
# تشخیص ارتباط خبر
# -----------------------------

def is_relevant(title, summary):
    text = (title + " " + summary).lower()

    return any(keyword in text for keyword in KEYWORDS)


# -----------------------------
# تشخیص نماد مرتبط
# -----------------------------

def detect_symbols(title, summary):
    text = (title + " " + summary).lower()

    symbols = []

    # طلا
    if any(word in text for word in [
        "gold price", "gold market", "gold demand",
        "gold reserves", "bullion", "gold"
    ]):
        symbols.append("XAUUSD")

    # آمریکا و دلار
    us_terms = [
        "federal reserve", "fed ", "fomc",
        "powell", "us inflation", "u.s. inflation",
        "us cpi", "u.s. cpi", "nonfarm payroll",
        "nfp", "treasury yields", "us dollar",
        "dollar index", "dxy", "united states"
    ]

    if any(word in text for word in us_terms):
        if "USD" not in symbols:
            symbols.append("USD")

        if "XAUUSD" not in symbols:
            symbols.append("XAUUSD (ارتباط غیرمستقیم)")

    # منطقه یورو
    euro_terms = [
        "european central bank", "ecb",
        "eurozone", "euro area", "euro"
    ]

    if any(word in text for word in euro_terms):
        symbols.append("EURUSD")

    # بریتانیا
    uk_terms = [
        "bank of england", "boe",
        "british pound", "sterling", "united kingdom"
    ]

    if any(word in text for word in uk_terms):
        symbols.append("GBPUSD")

    # ژاپن
    japan_terms = [
        "bank of japan", "boj",
        "japanese yen", "japan inflation"
    ]

    if any(word in text for word in japan_terms):
        symbols.append("USDJPY")

    # حذف موارد تکراری
    symbols = list(dict.fromkeys(symbols))

    if not symbols:
        return "نماد مرتبط مشخص نیست"

    return "، ".join(symbols)


# -----------------------------
# تعیین اهمیت خبر
# -----------------------------

def detect_importance(title, summary):
    text = (title + " " + summary).lower()

    high_terms = [
        "interest rate decision",
        "rate decision",
        "fomc",
        "federal reserve decision",
        "fed rate",
        "ecb rate decision",
        "bank of england rate",
        "cpi report",
        "core cpi",
        "nonfarm payroll",
        "nfp report",
        "pce inflation",
        "central bank gold reserves",
        "military strike",
        "invasion",
        "major escalation",
        "ceasefire agreement",
        "financial crisis",
        "banking crisis"
    ]

    medium_terms = [
        "inflation",
        "interest rate",
        "monetary policy",
        "gdp",
        "unemployment",
        "employment",
        "retail sales",
        "treasury yields",
        "bond yields",
        "sanctions",
        "trade war",
        "tariffs",
        "economic growth",
        "central bank",
        "gold demand",
        "gold reserves",
        "oil prices"
    ]

    low_terms = [
        "researchers",
        "research",
        "study",
        "scientists",
        "analysis",
        "forecast",
        "opinion",
        "interview"
    ]

    if any(term in text for term in high_terms):
        return "زیاد"

    if any(term in text for term in low_terms):
        return "کم"

    if any(term in text for term in medium_terms):
        return "متوسط"

    return "کم"


# -----------------------------
# ترجمه رایگان انگلیسی به فارسی
# -----------------------------

def translate_to_persian(text):
    if not text:
        return "متن برای ترجمه موجود نیست."

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
            translated = data["responseData"]["translatedText"]
            return html.unescape(translated)

        print("خطای ترجمه:", data.get("responseDetails"))

    except Exception as error:
        print("خطای سرویس ترجمه:", error)

    return "ترجمه فارسی فعلاً در دسترس نیست."


# -----------------------------
# ساخت پیام خبری
# -----------------------------

def make_message(source, entry):
    title = clean_summary(
        entry.get("title", "بدون عنوان")
    )

    raw_summary = clean_summary(
        entry.get("summary", "")
    )

    link = entry.get("link", "")
    published = entry.get("published", "زمان نامشخص")

    # خلاصه‌ای که صرفاً تکرار عنوان است، خلاصه مستقل محسوب نمی‌شود
    if raw_summary.lower().strip() == title.lower().strip():
        summary = ""
    else:
        summary = shorten_summary(raw_summary)

    symbols = detect_symbols(title, raw_summary)
    importance = detect_importance(title, raw_summary)

    persian_title = translate_to_persian(title)

    if summary:
        persian_summary = translate_to_persian(summary)
    else:
        persian_summary = (
            "منبع خبری خلاصه تکمیلی ارائه نکرده است."
        )

    english_summary = (
        summary if summary else
        "No additional summary provided by source."
    )

    message = (
        "کانال خبری گلد نیوز | Gold News Channel\n"
        "🟡 گزارش خبری\n\n"

        f"نماد خبر: {symbols}\n"
        f"📰 عنوان: {persian_title}\n"
        f"اهمیت خبر: {importance}\n"

        f"🏛 منبع: {source}\n"
        f"🕒 زمان انتشار: {published}\n\n"

        "🇬🇧 ENGLISH SUMMARY:\n"
        f"{english_summary}\n\n"

        "🇮🇷 خلاصه فارسی:\n"
        f"{persian_summary}\n\n"

        "🔗 لینک گزارش اصلی:\n"
        f"{link}"
    )

    # محدودیت تلگرام
    return message[:4000]


# -----------------------------
# اجرای اصلی ربات
# -----------------------------

def main():
    seen = load_seen()
    initialized = STATE_FILE.exists()

    print("Gold News Bot started.")

    for source, url in FEEDS.items():

        try:
            entries = get_entries(url)

            for entry in reversed(entries):

                uid = source + ":" + str(entry_id(entry))

                if not uid.strip() or uid in seen:
                    continue

                title = entry.get("title", "")
                summary = entry.get("summary", "")

                if initialized and is_relevant(title, summary):

                    message = make_message(source, entry)

                    send_telegram(message)

                    print("News sent:", title)

                    # فاصله کوتاه برای کاهش فشار روی سرویس ترجمه
                    time.sleep(1)

                seen.add(uid)
                save_seen(seen)

        except Exception as error:
            print(f"Error in {source}: {error}")

    if not initialized:
        save_seen(seen)
        print("Initial news history saved.")

    print("News check completed.")


def entry_id(entry):
    return (
        entry.get("id")
        or entry.get("link")
        or entry.get("title", "")
    )


if __name__ == "__main__":
    main()
