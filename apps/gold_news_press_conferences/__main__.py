"""Collect and publish verified economic press-conference transcripts with event-specific images."""
from __future__ import annotations

import json
import os
import re
import tempfile
import time
from datetime import datetime, timezone, timedelta
from email.utils import parsedate_to_datetime
from html.parser import HTMLParser
from pathlib import Path
from urllib.parse import urljoin, urlparse

import feedparser
import requests

from apps.gold_news_analyst.google_news import resolve_article_url
from goldnewsbot.safe_fetch import fetch_public_page
from goldnewsbot.pipeline_preview import extract_text

BASE = Path(__file__).resolve().parents[2]
SEEN_PATH = BASE / "press_conferences_seen.json"
ARCHIVE_PATH = BASE / "news_archive.json"
FEED_URL = (
    "https://news.google.com/rss/search?"
    "q=(Federal+Reserve+OR+FOMC+OR+ECB+OR+European+Central+Bank+OR+Bank+of+England+"
    "OR+Bank+of+Japan+OR+Bank+of+Canada+OR+RBA+OR+RBNZ+OR+SNB+OR+PBOC+"
    "OR+IMF+OR+World+Bank+OR+US+Treasury)+"
    "(%22press+conference%22+OR+transcript+OR+%22opening+statement%22+OR+"
    "%22prepared+remarks%22+OR+%22questions+and+answers%22+OR+Q%26A)"
    "&hl=en-US&gl=US&ceid=US:en"
)
MAX_AGE_HOURS = 72
MAX_ITEMS = 5
CONFERENCE_TERMS = (
    "press conference", "transcript", "q&a", "questions and answers",
    "opening statement", "prepared remarks", "media briefing",
)
INSTITUTIONS = (
    "federal reserve", "fomc", "ecb", "european central bank", "bank of england",
    "bank of japan", "bank of canada", "reserve bank of australia",
    "reserve bank of new zealand", "swiss national bank", "people's bank of china",
    "pboc", "imf", "international monetary fund", "world bank", "us treasury",
    "treasury secretary", "central bank",
)


class ImageMetaParser(HTMLParser):
    def __init__(self):
        super().__init__(convert_charrefs=True)
        self.images = []

    def handle_starttag(self, tag, attrs):
        if tag != "meta":
            return
        values = dict(attrs)
        key = (values.get("property") or values.get("name") or "").lower()
        if key in {"og:image", "og:image:url", "twitter:image", "twitter:image:src"}:
            value = values.get("content", "").strip()
            if value:
                self.images.append(value)


def clean(value):
    return re.sub(r"\\s+", " ", str(value or "")).strip()


def published_at(entry):
    for key in ("published", "updated"):
        raw = entry.get(key)
        if raw:
            try:
                dt = parsedate_to_datetime(raw)
                if dt.tzinfo is None:
                    dt = dt.replace(tzinfo=timezone.utc)
                return dt.astimezone(timezone.utc)
            except (TypeError, ValueError, OverflowError):
                pass
    parsed = entry.get("published_parsed") or entry.get("updated_parsed")
    if parsed:
        try:
            from datetime import datetime as dt
            return dt(*parsed[:6], tzinfo=timezone.utc)
        except (TypeError, ValueError):
            pass
    return None


def is_conference_candidate(title, summary):
    text = clean(title + " " + summary).casefold()
    return (
        any(term in text for term in CONFERENCE_TERMS)
        and any(term in text for term in INSTITUTIONS)
    )


def translate_to_persian(text, session=None):
    session = session or requests.Session()
    chunks, remaining = [], str(text or "").strip()
    while remaining:
        if len(remaining) <= 2800:
            chunks.append(remaining)
            break
        cut = remaining.rfind(" ", 0, 2800)
        if cut < 1000:
            cut = 2800
        chunks.append(remaining[:cut].strip())
        remaining = remaining[cut:].strip()
    translated = []
    for chunk in chunks:
        response = session.get(
            "https://translate.googleapis.com/translate_a/single",
            params={"client": "gtx", "sl": "auto", "tl": "fa", "dt": "t", "q": chunk},
            timeout=25,
        )
        response.raise_for_status()
        payload = response.json()
        part = "".join(
            row[0] for row in (payload[0] or [])
            if isinstance(row, list) and row and isinstance(row[0], str)
        ).strip()
        if not part or not re.search(r"[\\u0600-\\u06ff]", part):
            raise ValueError("Persian translation was not returned")
        translated.append(part)
        time.sleep(0.15)
    return "\\n\\n".join(translated)


def get_event_image(entry, page_html, final_url):
    parser = ImageMetaParser()
    parser.feed(page_html or "")
    candidates = list(parser.images)
    for key in ("media_thumbnail", "media_content"):
        for item in entry.get(key, []) or []:
            if isinstance(item, dict) and item.get("url"):
                candidates.append(item["url"])
    for link in entry.get("links", []) or []:
        if link.get("rel") == "enclosure" and str(link.get("type", "")).startswith("image/"):
            candidates.append(link.get("href", ""))
    for candidate in candidates:
        absolute = urljoin(final_url, candidate)
        parsed = urlparse(absolute)
        if parsed.scheme == "https" and parsed.netloc and not parsed.username and not parsed.password:
            return absolute
    return ""


def load_json(path, default):
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except FileNotFoundError:
        return default


def save_json(path, value):
    path.parent.mkdir(parents=True, exist_ok=True)
    fd, name = tempfile.mkstemp(prefix="." + path.name, suffix=".tmp", dir=str(path.parent))
    try:
        with os.fdopen(fd, "w", encoding="utf-8") as handle:
            json.dump(value, handle, ensure_ascii=False, indent=2)
            handle.flush()
            os.fsync(handle.fileno())
        Path(name).replace(path)
    except Exception:
        Path(name).unlink(missing_ok=True)
        raise


def telegram_post(token, chat_id, image_url, caption, text):
    # Split long transcripts into Telegram-safe chunks. With an image, attach the
    # first text chunk as a reply; without an image, send it as a normal message.
    chunks, remaining = [], str(text or "").strip()
    while remaining:
        if len(remaining) <= 3800:
            chunks.append(remaining)
            break
        cut = remaining.rfind("\\n\\n", 0, 3800)
        if cut < 1800:
            cut = remaining.rfind(" ", 0, 3800)
        if cut < 1800:
            cut = 3800
        chunks.append(remaining[:cut].strip())
        remaining = remaining[cut:].strip()

    if image_url:
        photo = requests.post(
            f"https://api.telegram.org/bot{token}/sendPhoto",
            data={"chat_id": chat_id, "photo": image_url, "caption": caption[:1000]},
            timeout=35,
        )
        photo.raise_for_status()
        payload = photo.json()
        if not payload.get("ok"):
            raise RuntimeError("Telegram rejected the event image: " + str(payload)[:250])
        message_id = (payload.get("result") or {}).get("message_id")
        reply_to = message_id
    else:
        if not chunks:
            raise ValueError("Transcript text is empty")
        first = requests.post(
            f"https://api.telegram.org/bot{token}/sendMessage",
            data={"chat_id": chat_id, "text": chunks.pop(0),
                  "disable_web_page_preview": True},
            timeout=30,
        )
        first.raise_for_status()
        payload = first.json()
        if not payload.get("ok"):
            raise RuntimeError("Telegram rejected the transcript text")
        message_id = (payload.get("result") or {}).get("message_id")
        reply_to = message_id

    for chunk in chunks:
        response = requests.post(
            f"https://api.telegram.org/bot{token}/sendMessage",
            data={"chat_id": chat_id, "text": chunk,
                  "reply_to_message_id": reply_to, "allow_sending_without_reply": True,
                  "disable_web_page_preview": True},
            timeout=30,
        )
        response.raise_for_status()
        if not response.json().get("ok"):
            raise RuntimeError("Telegram rejected a transcript text part")
    return message_id

def process_entry(entry, token, chat_id, seen, archive, session):
    title = clean(entry.get("title"))
    summary = clean(entry.get("summary"))
    link = clean(entry.get("link"))
    uid = clean(entry.get("id") or link or title)
    if not uid or uid in seen or not is_conference_candidate(title, summary):
        return False
    stamp = published_at(entry)
    now = datetime.now(timezone.utc)
    if stamp is None or stamp > now + timedelta(minutes=10) or now - stamp > timedelta(hours=MAX_AGE_HOURS):
        seen.add(uid)
        return False
    publisher_url = resolve_article_url(link, session=session, timeout=20)
    page_html, final_url = fetch_public_page(
        publisher_url, session=session, timeout=18, max_bytes=2_000_000, max_redirects=4
    )
    transcript = extract_text(page_html, max_chars=30000, min_chars=500)
    if len(transcript) < 500:
        print("Skipped: no substantial transcript/article text:", title)
        return False
    page_text = (title + " " + summary + " " + transcript[:5000]).casefold()
    if not any(term in page_text for term in CONFERENCE_TERMS):
        print("Skipped: content does not confirm a press conference:", title)
        return False
    if not any(term in page_text for term in INSTITUTIONS):
        print("Skipped: economic institution not confirmed:", title)
        return False
    image_url = get_event_image(entry, page_html, final_url)
    if not image_url:
        print("No conference-specific image found; publishing transcript as text:", title)

    persian_title = translate_to_persian(title, session)
    persian_transcript = translate_to_persian(transcript, session)
    published_kabul = stamp.astimezone(__import__("zoneinfo").ZoneInfo("Asia/Kabul")).strftime("%Y-%m-%d %H:%M (کابل)")
    message = (
        "🏛 صورت‌جلسه / متن نشست خبری اقتصادی | Gold News\\n\\n"
        f"📰 عنوان اصلی: {title}\\n"
        f"🇮🇷 عنوان فارسی: {persian_title}\\n"
        f"📅 زمان انتشار: {published_kabul}\\n"
        "📄 ترجمه فارسی متن منتشرشده نشست:\\n\\n"
        f"{persian_transcript}\\n\\n"
        f"🏛 منبع: {urlparse(final_url).netloc}\\n"
        f"🔗 منبع اصلی: {final_url}\\n\\n"
        "Gold Admin\\nNews Admin"
    )
    caption = (
        "🏛 نشست خبری اقتصادی | Gold News\\n"
        f"{persian_title}\\n"
        f"📅 {published_kabul}\\n"
        "متن ترجمه‌شده در پیام‌های بعدی آمده است."
    )
    message_id = telegram_post(token, chat_id, image_url, caption, message)
    archive.append({
        "source": "Economic Press Conference",
        "source_status": "منبع ناشر؛ اعتبار باید از لینک اصلی بررسی شود",
        "claim_status": "متن نشست منتشرشده؛ نقل‌قول‌ها نیازمند ارجاع به متن اصلی",
        "independent_verification": "احراز نشده",
        "confirmed_sources": ["Economic Press Conference"],
        "source_count": 1,
        "confirmation_status": "یک منبع ثبت‌شده؛ نه تأیید مستقل",
        "title": title,
        "summary": transcript[:30000],
        "link": final_url,
        "published_utc": stamp.isoformat(),
        "published_kabul": published_kabul,
        "importance": "زیاد",
        "relevance_score": 80,
        "relevance": "بسیار مرتبط",
        "category": "نشست خبری اقتصادی و سیاست پولی",
        "archived_at_utc": datetime.now(timezone.utc).isoformat(),
        "telegram_message_id": message_id,
        "telegram_chat_id": chat_id,
        "content_type": "economic_press_conference_transcript",
        "persian_title": persian_title,
        "translated_body": persian_transcript[:30000],
        "image_url": image_url or None,
    })
    seen.add(uid)
    print(f"Published verified conference transcript: {title}")
    return True


def main():
    token = os.getenv("BOT_TOKEN", "").strip()
    chat_id = os.getenv("CHANNEL_ID", "").strip()
    if not token or not chat_id:
        raise RuntimeError("BOT_TOKEN and CHANNEL_ID are required")
    seen = set(load_json(SEEN_PATH, []))
    archive = load_json(ARCHIVE_PATH, [])
    if not isinstance(archive, list):
        raise RuntimeError("news_archive.json must contain a list")
    session = requests.Session()
    response = session.get(FEED_URL, headers={"User-Agent": "GoldNewsBot/2.0"}, timeout=25)
    response.raise_for_status()
    entries = feedparser.parse(response.content).entries
    published = 0
    for entry in sorted(entries, key=lambda item: published_at(item) or datetime.min.replace(tzinfo=timezone.utc)):
        if published >= MAX_ITEMS:
            break
        try:
            if process_entry(entry, token, chat_id, seen, archive, session):
                published += 1
                save_json(ARCHIVE_PATH, archive[-3000:])
                save_json(SEEN_PATH, sorted(seen))
        except Exception as exc:
            print(f"Press-conference item failed safely ({clean(entry.get('title'))}): {type(exc).__name__}: {str(exc)[:200]}")
    save_json(SEEN_PATH, sorted(seen))
    print(f"Press conference scan complete: {published} published, {len(entries)} feed items checked")


if __name__ == "__main__":
    main()
