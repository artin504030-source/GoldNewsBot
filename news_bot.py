import os
import re
import json
import html
from html.parser import HTMLParser
import time
import requests
import feedparser

from gold_news_features import analyse_news, kabul_time, load_archive, is_duplicate, archive_news, source_status, record_source_confirmation
from breaking_news_analysis import score_breaking_news, format_breaking_badge
from source_health import record_source_check
from goldnewsbot.integration import fetch_and_classify_article

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
    "explosion", "attack on", "central bank intervention", "strait of hormuz", "oil tanker", "pipeline disruption", "oil export ban", "oil embargo", "opec+", "shipping attack"
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
    "Oil Trade and Supply": "https://news.google.com/rss/search?q=oil+exports+OR+oil+imports+OR+crude+oil+exports+OR+oil+production+OR+oil+supply+OR+OPEC%2B+OR+oil+embargo&hl=en-US&gl=US&ceid=US:en",
    "Energy Shipping Routes": "https://news.google.com/rss/search?q=Strait+of+Hormuz+OR+Red+Sea+shipping+OR+Suez+Canal+OR+Bab+el-Mandeb+OR+oil+tanker+OR+pipeline+disruption&hl=en-US&gl=US&ceid=US:en",
    "Conflict and Security": "https://news.google.com/rss/search?q=war+OR+military+attack+OR+airstrike+OR+missile+OR+invasion+OR+ceasefire+OR+peace+talks+OR+geopolitical+crisis+OR+sanctions&hl=en-US&gl=US&ceid=US:en",
    "Trade and Sanctions": "https://news.google.com/rss/search?q=trade+sanctions+OR+oil+sanctions+OR+export+ban+OR+import+restrictions+OR+tariffs+OR+trade+embargo+OR+shipping+restrictions&hl=en-US&gl=US&ceid=US:en",
    "China and Global Markets": "https://news.google.com/rss/search?q=China+economy+OR+Asian+markets+OR+Wall+Street+OR+stock+markets+OR+global+economy&hl=en-US&gl=US&ceid=US:en",
}

BREAKING_FEEDS = {
    name: url for name, url in FEEDS.items()
    if name in {"Federal Reserve", "BLS", "BEA", "European Central Bank", "Bank of England", "Bank of Japan", "Geopolitical News", "Conflict and Security", "Oil Trade and Supply", "Energy Shipping Routes", "Trade and Sanctions", "Economic Reports"}
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
    ["iran sanctions", "iran israel", "middle east conflict", "military strike", "airstrike", "ceasefire", "russia ukraine", "trade war", "tariffs", "oil prices", "crude oil", "opec", "china economy", "global financial markets", "banking crisis", "financial crisis", "oil exports", "oil imports", "oil supply", "oil production", "oil embargo", "oil tanker", "strait of hormuz", "red sea shipping", "suez canal", "bab el-mandeb", "pipeline disruption", "export ban", "import restrictions", "shipping attack", "trade sanctions"]
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

class ArticleTextParser(HTMLParser):
    """Extract readable article paragraphs while ignoring page chrome."""
    BLOCKED = {"script", "style", "nav", "footer", "header", "aside", "form", "noscript", "svg"}

    def __init__(self):
        super().__init__(convert_charrefs=True)
        self.blocked_depth = 0
        self.in_paragraph = False
        self.current = []
        self.paragraphs = []

    def handle_starttag(self, tag, attrs):
        if tag in self.BLOCKED:
            self.blocked_depth += 1
        elif tag == "p" and not self.blocked_depth:
            self.in_paragraph = True
            self.current = []

    def handle_endtag(self, tag):
        if tag in self.BLOCKED and self.blocked_depth:
            self.blocked_depth -= 1
        elif tag == "p" and self.in_paragraph:
            value = re.sub(r"\s+", " ", " ".join(self.current)).strip()
            if len(value) >= 35:
                self.paragraphs.append(value)
            self.current = []
            self.in_paragraph = False

    def handle_data(self, data):
        if self.in_paragraph and not self.blocked_depth:
            value = data.strip()
            if value:
                self.current.append(value)


def fetch_article_text(url, fallback=""):
    """Return article paragraphs; use RSS text only when page extraction fails."""
    if url:
        try:
            response = requests.get(
                url,
                headers={"User-Agent": "Mozilla/5.0 (compatible; GoldNewsBot/2.0)"},
                timeout=18,
                allow_redirects=True,
            )
            response.raise_for_status()
            parser = ArticleTextParser()
            parser.feed(response.text)
            paragraphs = list(dict.fromkeys(parser.paragraphs))
            article = "\n\n".join(paragraphs)
            if len(article) >= 450:
                return article[:12000], True
        except Exception as error:
            print("Article extraction failed; using RSS fallback:", error)
    return (clean_text(fallback)[:3000], False)


def _translation_chunks(text, limit=430):
    text = str(text or "").strip()
    chunks = []
    while text:
        if len(text) <= limit:
            chunks.append(text)
            break
        cut = text.rfind(" ", 0, limit + 1)
        if cut < limit // 2:
            cut = limit
        chunks.append(text[:cut].strip())
        text = text[cut:].strip()
    return chunks


def _contains_persian(text):
    return any("\u0600" <= char <= "\u06ff" for char in str(text or ""))


def _google_translate_fallback(text):
    """Free Google Translate endpoint fallback; no API key is required."""
    response = requests.get(
        "https://translate.googleapis.com/translate_a/single",
        params={"client": "gtx", "sl": "auto", "tl": "fa", "dt": "t", "q": text},
        timeout=20,
    )
    response.raise_for_status()
    payload = response.json()
    result = "".join(item[0] for item in (payload[0] or []) if item and item[0])
    if not result or not _contains_persian(result):
        raise ValueError("fallback returned no Persian text")
    return html.unescape(result)


def translate_to_persian(text):
    if not text:
        return ""
    if _contains_persian(text):
        return str(text)
    translated = []
    chunks = _translation_chunks(text)
    for index, chunk in enumerate(chunks, start=1):
        result = ""
        try:
            response = requests.get(
                "https://api.mymemory.translated.net/get",
                params={"q": chunk, "langpair": "en|fa"},
                timeout=20,
            )
            response.raise_for_status()
            data = response.json()
            candidate = html.unescape(data.get("responseData", {}).get("translatedText", ""))
            if str(data.get("responseStatus")) == "200" and _contains_persian(candidate):
                result = candidate
            else:
                print("MyMemory translation unavailable; trying fallback.")
        except Exception as error:
            print("MyMemory translation error; trying fallback:", error)
        if not result:
            try:
                result = _google_translate_fallback(chunk)
            except Exception as error:
                print("Google translation fallback failed:", error)
                result = "[ترجمه این بخش موقتاً در دسترس نیست]"
        translated.append(result)
        if index < len(chunks):
            time.sleep(0.2)
    return " ".join(part.strip() for part in translated if part.strip())


def _telegram_parts(message, limit=3800):
    remaining = str(message or "").strip()
    parts = []
    content_limit = limit - 80
    while remaining:
        if len(remaining) <= content_limit:
            parts.append(remaining)
            break
        cut = remaining.rfind("\n\n", 0, content_limit + 1)
        if cut < content_limit // 2:
            cut = remaining.rfind("\n", 0, content_limit + 1)
        if cut < content_limit // 2:
            cut = remaining.rfind(" ", 0, content_limit + 1)
        if cut < content_limit // 2:
            cut = content_limit
        parts.append(remaining[:cut].strip())
        remaining = remaining[cut:].strip()
    total = len(parts)
    if total > 1:
        parts = [f"📄 متن خبر | بخش {i + 1} از {total}\n\n{part}" for i, part in enumerate(parts)]
    return parts


def send_telegram(message):
    if os.getenv("DRY_RUN", "false").lower() == "true":
        print("[DRY RUN] Telegram message was not sent:")
        print(message[:1000])
        return False

    parts = _telegram_parts(message)
    first_message_id = None
    for part_number, part in enumerate(parts, start=1):
        last_error = None
        delivered = False
        for attempt in range(3):
            try:
                response = requests.post(
                    API_URL,
                    data={"chat_id": CHANNEL_ID, "text": part, "disable_web_page_preview": True},
                    timeout=25,
                )
                try:
                    result = response.json()
                except Exception:
                    result = {}
                if response.status_code == 429:
                    retry_after = result.get("parameters", {}).get("retry_after", 30)
                    try:
                        delay = max(1, min(int(retry_after), 300))
                    except (TypeError, ValueError):
                        delay = 2 ** attempt
                    if attempt == 2:
                        raise TelegramRateLimitError(f"Telegram 429 after retries; retry_after={retry_after}")
                    time.sleep(delay)
                    continue
                if response.status_code >= 500 and attempt < 2:
                    time.sleep(2 ** attempt)
                    continue
                response.raise_for_status()
                if not result.get("ok"):
                    raise RuntimeError(str(result))
                if first_message_id is None:
                    first_message_id = (result.get("result") or {}).get("message_id")
                delivered = True
                break
            except requests.RequestException as error:
                last_error = error
                if attempt < 2:
                    time.sleep(2 ** attempt)
        if not delivered:
            if last_error:
                raise last_error
            raise TelegramRateLimitError(f"Telegram delivery failed for part {part_number}.")
        if part_number < len(parts):
            time.sleep(0.4)
    return {"message_id": first_message_id, "chat_id": CHANNEL_ID}


def make_message(source, entry):
    title = clean_text(entry.get("title", "بدون عنوان"))
    raw_summary = clean_text(entry.get("summary", ""))
    link = entry.get("link", "")
    published_dt = entry_datetime(entry)
    kabul_published = kabul_time(published_dt) if published_dt else clean_text(entry.get("published", "زمان نامشخص"))

    article_result = fetch_and_classify_article(link, title, raw_summary, preserve_partial=True)
    article_text = article_result["body"]
    full_article = article_result["full_article"]
    publisher_link = article_result.get("url") or link

    source_info = entry.get("source")
    if isinstance(source_info, dict):
        publisher_name = source_info.get("title") or source_info.get("name")
    else:
        publisher_name = getattr(source_info, "title", None) or source_info
    if not publisher_name:
        title_parts = title.rsplit(" - ", 1)
        publisher_name = title_parts[-1] if len(title_parts) == 2 else source
    publisher_name = clean_text(str(publisher_name or source))

    persian_title = translate_to_persian(title)
    time.sleep(TRANSLATION_DELAY)
    persian_article = translate_to_persian(article_text) if article_text else "متن خبر از ناشر قابل دریافت نبود."
    article_status = (
        ""
        if full_article
        else "⚠️ متن کامل از ناشر در دسترس نبود؛ متن موجود از خبر ارسال شده است و ممکن است ناقص باشد."
    )
    body_lines = [
        f"📅 تاریخ انتشار: {kabul_published}",
        "",
        "🔎 متن خبر:",
    ]
    if article_status:
        body_lines.extend([article_status, ""])
    body_lines.extend([
        persian_article,
        "",
        f"🏛 منبع: {publisher_name}",
    ])
    if publisher_link:
        body_lines.append(f"🔗 لینک منبع: {publisher_link}")
    body_lines.extend([
        "",
        "⚠️ این تحلیل بر اساس اطلاعات زمان انتشار خبر است و سیگنال معاملاتی یا توصیه خریدوفروش نیست.",
    ])
    return (
        "📰 خبر | Gold News\n\n"
        f"📰 عنوان: {persian_title}\n"
        + "\n".join(body_lines)
        + "\n\nGold Admin\nNews Admin"
    )

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
                archive_news(source, title, article_text or summary, entry.get("link", ""), published_dt.isoformat() if published_dt else "", importance,
                             telegram_message_id=sent.get("message_id"), telegram_chat_id=sent.get("chat_id"))
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
