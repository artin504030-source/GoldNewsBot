import os
import re
import json
import html
import time
import requests
import feedparser

from gold_news_features import analyse_news, kabul_time, load_archive, is_duplicate, archive_news, source_status, record_source_confirmation
from market_analysis import analyze_market_news
from breaking_news_analysis import score_breaking_news, format_breaking_badge
from source_health import record_source_check

from pathlib import Path
from datetime import datetime, timezone, timedelta
from email.utils import parsedate_to_datetime
from dotenv import load_dotenv

BASE_DIR = Path(__file__).resolve().parent
load_dotenv(BASE_DIR / ".env")

TOKEN = os.getenv("BOT_TOKEN")
CHANNEL_ID = os.getenv("CHANNEL_ID")

if not TOKEN or not CHANNEL_ID:
    raise SystemExit("تنظیمات تلگرام پیدا نشد.")


STATE_FILE = BASE_DIR / "seen_news.json"
API_URL = f"https://api.telegram.org/bot{TOKEN}/sendMessage"

# حداکثر سه خبر در هر اجرای ۱۵ دقیقه‌ای
MAX_NEWS_PER_RUN = min(10, max(1, int(os.getenv("NEWS_MAX_PER_RUN", "2" if os.getenv("BREAKING_ONLY", "false").lower() == "true" else "3"))))
MAX_AGE_HOURS = min(168, max(1, int(os.getenv("NEWS_MAX_AGE_HOURS", "36"))))
BREAKING_ONLY = os.getenv("BREAKING_ONLY", "false").lower() == "true"
BREAKING_TERMS = (
    "breaking", "just in", "emergency meeting", "emergency rate", "unexpected rate",
    "surprise rate", "fed cuts rates", "fed raises rates", "rate cut announced",
    "rate hike announced", "military strike", "airstrike", "missile attack", "invasion",
    "major escalation", "ceasefire agreement", "bank collapse", "bank failure",
    "bank defaults", "sovereign default", "financial panic", "emergency sanctions",
    "explosion", "attack on", "central bank intervention"
)
TRANSLATION_DELAY = 1.0


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

BREAKING_FEEDS = {
    name: url for name, url in FEEDS.items()
    if name in {"Federal Reserve", "BLS", "BEA", "European Central Bank", "Bank of England", "Bank of Japan", "Geopolitical News", "Economic Reports"}
}

EXCLUDE_TERMS = [
    "gold medal", "gold medals", "wins gold", "won gold", "athlete", "championship",
    "tournament", "swimmer", "football", "soccer", "basketball", "olympic", "sports",
    "retailers that sell gold", "jewelry", "jewellery", "vending machine", "gold shop", "gold store"
]
RELEVANCE_GROUPS = [
    ["gold price", "gold market", "gold futures", "gold bullion", "bullion market", "gold etf", "gold demand", "gold reserves", "central bank gold", "gold holdings", "precious metals", "precious metal prices", "gold investment", "gold trading", "gold drops", "gold rises", "gold tumbles", "gold rally"],
    ["federal reserve", "fomc", "fed rate", "fed funds", "us cpi", "u.s. cpi", "core cpi", "pce inflation", "nonfarm payroll", "non-farm payroll", "treasury yield", "us dollar", "u.s. dollar", "dollar index", "dxy", "us inflation", "u.s. inflation", "us economy", "u.s. economy", "interest rate decision"],
    ["european central bank", "ecb", "eurozone inflation", "euro area inflation", "bank of england", "boe rate", "bank of japan", "boj", "japanese yen", "gdp growth", "inflation report", "retail sales report", "unemployment rate", "employment report", "pmi report", "bond yields", "treasury yields", "forex market", "foreign exchange market", "currency markets"],
    ["iran sanctions", "iran israel", "middle east conflict", "military strike", "airstrike", "ceasefire", "russia ukraine", "trade war", "tariffs", "oil prices", "crude oil", "opec", "china economy", "global financial markets", "banking crisis", "financial crisis"]
]
HIGH_IMPORTANCE = ["fomc rate decision", "fed rate decision", "interest rate decision", "rate decision", "cpi report", "core cpi", "nonfarm payroll", "non-farm payroll", "nfp report", "pce inflation", "central bank gold reserves", "central bank cuts rates", "central bank raises rates", "emergency rate", "military strike", "invasion", "major escalation", "ceasefire agreement", "banking crisis", "financial crisis"]
MEDIUM_IMPORTANCE = ["inflation", "interest rate", "monetary policy", "gdp", "unemployment", "employment", "retail sales", "treasury yields", "bond yields", "sanctions", "trade war", "tariffs", "economic growth", "central bank", "gold demand", "gold reserves", "oil prices", "forex", "currency"]
LOW_IMPORTANCE = ["research", "researchers", "study", "scientists", "analysis", "opinion", "interview", "company", "mining project", "exploration"]

class TelegramRateLimitError(RuntimeError):
    pass


def clean_text(value):
    value = re.sub(r"<[^>]+>", " ", value or "")
    value = html.unescape(value)
    return re.sub(r"\s+", " ", value).strip()


def load_seen():
    if not STATE_FILE.exists():
        return set()
    try:
        data = json.loads(STATE_FILE.read_text(encoding="utf-8"))
        return set(data if isinstance(data, list) else [])
    except Exception as error:
        print("Cannot read seen_news.json:", error)
        return set()

def save_seen(seen):
    temp_file = STATE_FILE.with_suffix(".tmp")
    temp_file.write_text(json.dumps(sorted(seen), ensure_ascii=False), encoding="utf-8")
    temp_file.replace(STATE_FILE)

def get_entries(url):
    """Fetch RSS/Atom with bounded retries for transient failures."""
    last_error = None
    for attempt in range(3):
        try:
            response = requests.get(url, headers={"User-Agent": "GoldNewsBot/2.0"}, timeout=25)
            if response.status_code == 429:
                retry_after = response.headers.get("Retry-After", "")
                try: delay = max(1, min(int(retry_after), 60))
                except (TypeError, ValueError): delay = 2 ** attempt
                if attempt == 2: response.raise_for_status()
                time.sleep(delay)
                continue
            if response.status_code >= 500 and attempt < 2:
                time.sleep(2 ** attempt); continue
            response.raise_for_status()
            return feedparser.parse(response.content).entries
        except requests.RequestException as error:
            last_error = error
            if attempt < 2: time.sleep(2 ** attempt)
    if last_error: raise last_error
    raise RuntimeError(f"Feed fetch failed after retries: {url}")

def entry_id(entry):
    return str(entry.get("id") or entry.get("link") or entry.get("title", "")).strip()

def entry_datetime(entry):
    for field in ("published", "updated", "created"):
        value = entry.get(field)
        if value:
            try:
                dt = parsedate_to_datetime(value)
                if dt.tzinfo is None:
                    dt = dt.replace(tzinfo=timezone.utc)
                return dt.astimezone(timezone.utc)
            except Exception:
                pass
    parsed = entry.get("published_parsed") or entry.get("updated_parsed")
    if parsed:
        try:
            return datetime(*parsed[:6], tzinfo=timezone.utc)
        except Exception:
            pass
    return None

def is_recent(entry):
    published = entry_datetime(entry)
    if published is None:
        return False
    now = datetime.now(timezone.utc)
    age = now - published
    return timedelta(minutes=-10) <= age <= timedelta(hours=MAX_AGE_HOURS)

def is_breaking_news(title, summary=""):
    text = clean_text(title + " " + summary).lower()
    return any(term in text for term in BREAKING_TERMS)

def is_relevant(title, summary):
    text = clean_text(title + " " + summary).lower()
    if any(term in text for term in EXCLUDE_TERMS):
        return False
    return any(term in text for group in RELEVANCE_GROUPS for term in group)

def detect_symbols(title, summary):
    text = clean_text(title + " " + summary).lower()
    symbols = []
    gold_context = any(term in text for term in ["gold price", "gold market", "gold futures", "gold bullion", "bullion market", "gold etf", "gold demand", "gold reserves", "central bank gold", "gold holdings", "gold trading", "gold rises", "gold drops", "gold tumbles", "gold rally", "precious metals"])
    if gold_context:
        symbols.append("XAUUSD")
    us_terms = ["federal reserve", "fomc", "fed rate", "fed funds", "us cpi", "u.s. cpi", "core cpi", "pce inflation", "nonfarm payroll", "non-farm payroll", "treasury yield", "us dollar", "u.s. dollar", "dollar index", "dxy", "us inflation", "u.s. inflation", "united states"]
    if any(term in text for term in us_terms):
        symbols.append("USD")
        if "XAUUSD" not in symbols:
            symbols.append("XAUUSD (ارتباط غیرمستقیم)")
    euro_terms = ["european central bank", "ecb", "eurozone", "euro area", "euro"]
    if any(term in text for term in euro_terms): symbols.append("EURUSD")
    uk_terms = ["bank of england", "boe", "british pound", "sterling", "united kingdom"]
    if any(term in text for term in uk_terms): symbols.append("GBPUSD")
    japan_terms = ["bank of japan", "boj", "japanese yen", "japan inflation"]
    if any(term in text for term in japan_terms): symbols.append("USDJPY")
    symbols = list(dict.fromkeys(symbols))
    return "، ".join(symbols) if symbols else "نماد مرتبط مشخص نیست"

def detect_importance(title, summary):
    text = clean_text(title + " " + summary).lower()
    if any(term in text for term in HIGH_IMPORTANCE): return "زیاد"
    if any(term in text for term in LOW_IMPORTANCE): return "کم"
    if any(term in text for term in MEDIUM_IMPORTANCE): return "متوسط"
    return "کم"

def translate_to_persian(text):
    if not text: return ""
    try:
        response = requests.get("https://api.mymemory.translated.net/get", params={"q": text[:4500], "langpair": "en|fa"}, timeout=20)
        response.raise_for_status()
        data = response.json()
        if data.get("responseStatus") == 200:
            return html.unescape(data["responseData"]["translatedText"])
        print("Translation service:", data.get("responseDetails"))
    except Exception as error:
        print("Translation error:", error)
    return "ترجمه فارسی فعلاً در دسترس نیست."

def send_telegram(message):
    if os.getenv("DRY_RUN", "false").lower() == "true":
        print("[DRY RUN] Telegram message was not sent:"); print(message[:1000]); return False
    last_error = None
    for attempt in range(3):
        try:
            response = requests.post(API_URL, data={"chat_id": CHANNEL_ID, "text": message, "disable_web_page_preview": True}, timeout=25)
            try: result = response.json()
            except Exception: result = {}
            if response.status_code == 429:
                retry_after = result.get("parameters", {}).get("retry_after", 30)
                try: delay = max(1, min(int(retry_after), 300))
                except (TypeError, ValueError): delay = 2 ** attempt
                print(f"Telegram rate limit. Waiting {delay}s.")
                if attempt == 2: raise TelegramRateLimitError(f"Telegram 429 after retries; retry_after={retry_after}")
                time.sleep(delay); continue
            if response.status_code >= 500 and attempt < 2:
                time.sleep(2 ** attempt); continue
            response.raise_for_status()
            if not result.get("ok"): raise RuntimeError(str(result))
            return True
        except requests.RequestException as error:
            last_error = error
            if attempt < 2: time.sleep(2 ** attempt)
    if last_error: raise last_error
    raise TelegramRateLimitError("Telegram message delivery failed after retries.")

def make_message(source, entry):
    title = clean_text(entry.get("title", "بدون عنوان"))
    raw_summary = clean_text(entry.get("summary", ""))
    link = entry.get("link", "")
    published = entry.get("published", "زمان نامشخص")
    published_dt = entry_datetime(entry)
    kabul_published = kabul_time(published_dt) if published_dt else "زمان نامشخص"
    relevance = analyse_news(title, raw_summary)
    breaking = is_breaking_news(title, raw_summary)
    breaking_assessment = score_breaking_news(title, raw_summary, source=source)
    summary = raw_summary
    if summary.lower().strip() == title.lower().strip(): summary = ""
    summary = summary[:600]
    symbols = detect_symbols(title, raw_summary)
    importance = detect_importance(title, raw_summary)
    market_analysis = analyze_market_news(title, raw_summary)
    affected_symbols = ", ".join(market_analysis["symbols"])
    persian_title = translate_to_persian(title)
    time.sleep(TRANSLATION_DELAY)
    persian_summary = translate_to_persian(summary) if summary else "منبع خبری خلاصه تکمیلی ارائه نکرده است."
    english_summary = summary if summary else "No additional summary provided by source."
    return (
        "کانال خبری گلد نیوز | Gold News Channel\n"
        f"{'🚨 خبر فوری\n' if breaking else '🟡 گزارش خبری\n'}\n"
        f"نماد خبر: {symbols}\n"
        f"🚨 درجه فوریت: {format_breaking_badge(breaking_assessment)}\n"
        f"📰 عنوان: {persian_title}\n"
        f"اهمیت خبر: {importance}\n"
        f"ارتباط با طلا: {relevance['label']} ({relevance['score']}/100)\n"
        f"📌 نمادهای مرتبط: {affected_symbols}\n"
        f"🔎 لحن خبر: {market_analysis['potential_effect']}\n"
        f"🎚 اطمینان: {market_analysis['confidence']}\n"
        f"🧠 توضیح: {market_analysis['reason']}\n"
        f"دسته‌بندی: {relevance['category']}\n"
        f"🏛 منبع: {source} ({source_status(source)})\n"
        f"🕒 زمان انتشار منبع: {published}\n"
        f"🕒 زمان کابل: {kabul_published}\n\n"
        "🇬🇧 ENGLISH SUMMARY:\n"
        f"{english_summary}\n\n"
        "🇮🇷 خلاصه فارسی:\n"
        f"{persian_summary}\n\n"
        "🔗 لینک گزارش اصلی:\n"
        f"{link}"
    )[:4000]

def main():
    seen = load_seen()
    initialized = STATE_FILE.exists()
    sent_count = 0
    preview_count = 0
    archive = load_archive()
    stop_sending = False
    print("Gold News Bot started.")
    print("Loaded seen items:", len(seen))
    print("Maximum news per run:", MAX_NEWS_PER_RUN)
    print("Maximum news age (hours):", MAX_AGE_HOURS)
    print("Breaking-only mode:", BREAKING_ONLY)
    feeds_to_check = BREAKING_FEEDS if BREAKING_ONLY else FEEDS
    for source, url in feeds_to_check.items():
        if stop_sending or sent_count + preview_count >= MAX_NEWS_PER_RUN: break
        try:
            entries = get_entries(url)
            record_source_check(source, True, len(entries), mode="breaking" if BREAKING_ONLY else "regular")
            print(f"Source OK | {source} | entries={len(entries)}")
            for entry in reversed(entries):
                if stop_sending or sent_count + preview_count >= MAX_NEWS_PER_RUN: break
                uid = source + ":" + entry_id(entry)
                if not uid.strip() or uid in seen: continue
                title = clean_text(entry.get("title", ""))
                summary = clean_text(entry.get("summary", ""))
                if not initialized:
                    seen.add(uid); save_seen(seen); continue
                if not is_recent(entry):
                    seen.add(uid); save_seen(seen)
                    print("Skipped old/undated news:", title); continue
                if not is_relevant(title, summary):
                    seen.add(uid); save_seen(seen)
                    print("Filtered irrelevant news:", title); continue
                assessment = score_breaking_news(title, summary, source=source)
                if BREAKING_ONLY and assessment["score"] < assessment["threshold"]: continue
                if is_duplicate(title, entry.get("link", ""), archive):
                    confirmations = record_source_confirmation(source, title, entry.get("link", ""))
                    print(f"Duplicate confirmed by another source; total sources={confirmations}:", title)
                    archive = load_archive(); seen.add(uid); save_seen(seen)
                    print("Skipped cross-feed duplicate:", title); continue
                symbols = detect_symbols(title, summary)
                importance = detect_importance(title, summary)
                print(f"Candidate | urgency={assessment['level']} score={assessment['score']} | importance={importance} | symbols={symbols} | title={title}")
                message = make_message(source, entry)
                try:
                    sent = send_telegram(message)
                    if not sent:
                        preview_count += 1
                        print("Dry-run candidate checked:", preview_count)
                        if preview_count >= MAX_NEWS_PER_RUN: break
                        continue
                except TelegramRateLimitError as error:
                    print("Stopping sends due to Telegram limit:", error)
                    stop_sending = True; break
                seen.add(uid); save_seen(seen)
                published_dt = entry_datetime(entry)
                archive_news(source, title, summary, entry.get("link", ""), published_dt.isoformat() if published_dt else "", importance)
                archive = load_archive(); sent_count += 1
                print("News sent successfully:", title)
                time.sleep(3)
        except Exception as error:
            record_source_check(source, False, error=error, mode="breaking" if BREAKING_ONLY else "regular")
            print(f"Error in {source}: {error}")
    if not initialized:
        save_seen(seen)
        print("Initial news history saved. No old news was sent.")
    print("News sent in this run:", sent_count)
    if preview_count: print("Dry-run candidates previewed:", preview_count)
    print("Seen items saved:", len(seen))
    print("News check completed.")

if __name__ == "__main__":
    main()
