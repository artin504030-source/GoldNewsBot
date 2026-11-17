import json
import re
from datetime import datetime, timezone
from difflib import SequenceMatcher
from pathlib import Path
from urllib.parse import urlsplit, urlunsplit, parse_qsl, urlencode
from zoneinfo import ZoneInfo

KABUL = ZoneInfo("Asia/Kabul")
ARCHIVE_FILE = Path(__file__).resolve().parent / "news_archive.json"

GOLD_TERMS = ("gold", "bullion", "precious metal", "xauusd", "gold etf", "gold reserve")
US_TERMS = ("federal reserve", "fomc", "fed rate", "cpi", "core cpi", "pce", "nonfarm payroll", "non-farm payroll", "treasury yield", "dollar index", "dxy", "us inflation", "u.s. inflation")
CENTRAL_TERMS = ("ecb", "european central bank", "bank of england", "boe", "bank of japan", "boj", "pboc", "interest rate", "monetary policy")
GEO_TERMS = ("war", "military strike", "airstrike", "ceasefire", "sanction", "iran", "israel", "ukraine", "russia", "tariff", "trade war", "geopolitical")
ENERGY_TERMS = ("oil", "opec", "natural gas", "energy market")
GLOBAL_TERMS = ("china economy", "global economy", "wall street", "stock market", "financial crisis", "banking crisis", "bond yields")


def analyse_news(title, summary=""):
    text = (title + " " + summary).lower()
    score = 0
    category = "اقتصاد جهانی"
    if any(x in text for x in GOLD_TERMS):
        score += 45
        category = "طلا و فلزات گران‌بها"
    if any(x in text for x in US_TERMS):
        score += 30
        category = "اقتصاد آمریکا و دلار" if score < 45 else category
    if any(x in text for x in CENTRAL_TERMS):
        score += 22
        category = "بانک‌های مرکزی و نرخ بهره" if score < 45 else category
    if any(x in text for x in GEO_TERMS):
        score += 16
        category = "ژئوپلیتیک" if score < 45 else category
    if any(x in text for x in ENERGY_TERMS):
        score += 12
        category = "انرژی" if score < 45 else category
    if any(x in text for x in GLOBAL_TERMS):
        score += 10
        category = "بازارهای جهانی" if score < 45 else category
    score = min(score, 100)
    label = "بسیار مرتبط" if score >= 45 else "مرتبط" if score >= 25 else "ارتباط محدود"
    return {"score": score, "label": label, "category": category}


def kabul_time(value):
    if not value:
        return "زمان نامشخص"
    try:
        if isinstance(value, str):
            dt = datetime.fromisoformat(value.replace("Z", "+00:00"))
        else:
            dt = value
        if dt.tzinfo is None:
            dt = dt.replace(tzinfo=timezone.utc)
        return dt.astimezone(KABUL).strftime("%Y-%m-%d %H:%M (کابل)")
    except Exception:
        return str(value)


def canonical_url(url):
    if not url:
        return ""
    try:
        p = urlsplit(url.strip())
        query = [(k, v) for k, v in parse_qsl(p.query, keep_blank_values=True)
                 if not k.lower().startswith("utm_") and k.lower() not in {"fbclid", "gclid", "ocid", "cmpid"}]
        return urlunsplit((p.scheme.lower(), p.netloc.lower(), p.path.rstrip("/"), urlencode(query), ""))
    except Exception:
        return url.strip()


def load_archive():
    try:
        data = json.loads(ARCHIVE_FILE.read_text(encoding="utf-8"))
        return data if isinstance(data, list) else []
    except FileNotFoundError:
        return []
    except Exception as exc:
        print("Archive read error:", exc)
        return []


def save_archive(items):
    temp = ARCHIVE_FILE.with_suffix(".tmp")
    temp.write_text(json.dumps(items[-3000:], ensure_ascii=False, indent=2), encoding="utf-8")
    temp.replace(ARCHIVE_FILE)


def is_duplicate(title, link, archive):
    key = canonical_url(link)
    normalized = re.sub(r"[^a-z0-9\u0600-\u06ff]+", " ", title.lower()).strip()
    for item in archive[-500:]:
        old_link = canonical_url(item.get("link", ""))
        if key and old_link and key == old_link:
            return True
        old_title = re.sub(r"[^a-z0-9\u0600-\u06ff]+", " ", item.get("title", "").lower()).strip()
        if normalized and old_title and SequenceMatcher(None, normalized, old_title).ratio() >= 0.91:
            return True
    return False


def source_status(source):
    official = ("federal reserve", "bls", "bea", "european central bank", "eurostat", "bank of england", "bank of japan")
    name = (source or "").lower()
    return "منبع رسمی" if any(term in name for term in official) else "منبع رسانه‌ای/تجمیع‌گر؛ نیازمند بررسی منبع اصلی"


def _matching_archive_item(title, link, items):
    key = canonical_url(link)
    normalized = re.sub(r"[^a-z0-9\u0600-\u06ff]+", " ", title.lower()).strip()
    for item in reversed(items[-500:]):
        old_link = canonical_url(item.get("link", ""))
        if key and old_link and key == old_link:
            return item
        old_title = re.sub(r"[^a-z0-9\u0600-\u06ff]+", " ", item.get("title", "").lower()).strip()
        if normalized and old_title and SequenceMatcher(None, normalized, old_title).ratio() >= 0.91:
            return item
    return None


def record_source_confirmation(source, title, link):
    items = load_archive()
    match = _matching_archive_item(title, link, items)
    if not match:
        return 0
    sources = match.get("confirmed_sources") or [match.get("source", "نامشخص")]
    if source and source not in sources:
        sources.append(source)
    match["confirmed_sources"] = sources
    match["source_count"] = len(sources)
    match["confirmation_status"] = "تأیید چند منبع" if len(sources) >= 2 else "یک منبع ثبت‌شده"
    match["last_confirmation_utc"] = datetime.now(timezone.utc).isoformat()
    save_archive(items)
    return len(sources)


def archive_news(source, title, summary, link, published, importance):
    analysis = analyse_news(title, summary)
    items = load_archive()
    items.append({
        "source": source, "source_status": source_status(source), "confirmed_sources": [source], "source_count": 1, "confirmation_status": "یک منبع ثبت‌شده", "title": title, "summary": summary[:1200], "link": link,
        "published_utc": published, "published_kabul": kabul_time(published),
        "importance": importance, "relevance_score": analysis["score"],
        "relevance": analysis["label"], "category": analysis["category"],
        "archived_at_utc": datetime.now(timezone.utc).isoformat()
    })
    save_archive(items)


def fetch_calendar_events(limit=12):
    """Read the public Forex Factory weekly XML calendar; timestamps without offsets remain unconverted."""
    import requests
    import xml.etree.ElementTree as ET
    url = "https://nfs.faireconomy.media/ff_calendar_thisweek.xml"
    response = requests.get(url, headers={"User-Agent": "GoldNewsBot/2.0"}, timeout=20)
    response.raise_for_status()
    root = ET.fromstring(response.content)
    events = []
    now = datetime.now(timezone.utc)
    for node in root.findall(".//event"):
        get = lambda name: (node.findtext(name) or "").strip()
        title, country, date, clock, impact = get("title"), get("country"), get("date"), get("time"), get("impact")
        if not title or not date:
            continue
        stamp = date + (" " + clock if clock else "")
        events.append({"title": title, "country": country, "date": date, "time": clock,
                       "impact": impact, "forecast": get("forecast"), "previous": get("previous"),
                       "source_time": stamp})
    return events[:limit]
