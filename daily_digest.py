import json
import os
from collections import Counter
from datetime import datetime, timedelta, timezone
from pathlib import Path
import requests
from dotenv import load_dotenv
from gold_news_features import load_archive, fetch_calendar_events, kabul_time
from market_digest import build_multi_market_digest
from news_history import summarize_history, format_history_summary
from source_health import summarize_source_health, format_source_health

BASE = Path(__file__).resolve().parent
load_dotenv(BASE / ".env")
TOKEN = os.getenv("BOT_TOKEN")
CHANNEL_ID = os.getenv("CHANNEL_ID")
REPORT_FILE = BASE / "daily_report.json"


def split_message(message, limit=3800):
    """Split plain-text Telegram messages below Telegram's 4096-character limit."""
    chunks = []
    current = ""
    for line in (message or "").splitlines():
        while len(line) > limit:
            if current:
                chunks.append(current)
                current = ""
            chunks.append(line[:limit])
            line = line[limit:]
        candidate = line if not current else current + "\\n" + line
        if len(candidate) > limit:
            if current:
                chunks.append(current)
            current = line
        else:
            current = candidate
    if current:
        chunks.append(current)
    return chunks or [" " ]


def send(message):
    if os.getenv("DRY_RUN", "false").lower() == "true":
        print("[DRY RUN] Daily digest preview (not sent):\\n" + message)
        return
    if not TOKEN or not CHANNEL_ID:
        raise SystemExit("Telegram settings missing")
    chunks = split_message(message)
    print(f"Sending daily digest in {len(chunks)} Telegram message(s).")
    for index, chunk in enumerate(chunks, start=1):
        response = requests.post(
            f"https://api.telegram.org/bot{TOKEN}/sendMessage",
            data={"chat_id": CHANNEL_ID, "text": chunk, "disable_web_page_preview": True},
            timeout=25,
        )
        try:
            result = response.json()
        except ValueError:
            response.raise_for_status()
            raise RuntimeError("Telegram returned a non-JSON response.")
        if not response.ok or not result.get("ok"):
            description = result.get("description", "unknown Telegram error")
            raise RuntimeError(
                f"Telegram sendMessage failed for digest part {index}/{len(chunks)} "
                f"(HTTP {response.status_code}): {description}"
            )
        print(f"Sent digest part {index}/{len(chunks)} (message_id={result.get('result', {}).get('message_id')}).")


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
    events = []
    try:
        events = fetch_calendar_events(12)
    except Exception as exc:
        print("Calendar unavailable:", exc)
    multi = build_multi_market_digest(recent, events, kabul_time(now))
    history = summarize_history(load_archive(), now, days=7)
    history_text = format_history_summary(history)
    source_health = summarize_source_health()
    source_health_text = format_source_health(source_health)
    message = multi["message"] + "\n\n" + history_text + "\n\n" + source_health_text
    report = {
        "generated_at_utc": now.isoformat(),
        "generated_at_kabul": kabul_time(now),
        "window_hours": 24,
        "message": message,
        "news": multi["news"],
        "news_history": history,
        "source_health": source_health,
        "source_health_text": source_health_text,
        "market_counts": multi["market_counts"],
        "calendar_events": multi["calendar_events"],
        "calendar_source": "Forex Factory public weekly XML feed",
        "calendar_timezone_note": "Source timezone is unspecified; event times are shown as provided; no conversion applied.",
        "calendar_currency_mapping": "Country/currency associations and related symbols are heuristic context, not price predictions."
    }
    REPORT_FILE.write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"Dashboard multi-market report saved: {REPORT_FILE.name} ({len(recent)} news items, {len(events)} calendar events)")
    return message



def main():
    now = datetime.now(timezone.utc)
    message = build_digest(now)
    send(message)
    print("Daily fundamental digest completed")


if __name__ == "__main__":
    main()
