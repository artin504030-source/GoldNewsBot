from __future__ import annotations

import json
import os
import re
import tempfile
from datetime import datetime, timezone, timedelta
from pathlib import Path
from html import escape

import requests

from .analysis import analyze_report, make_chart

TOKEN = os.getenv("GOLD_PRICED_IN_ANALYST_BOT_TOKEN", "").strip()
CHAT_ID = os.getenv("CHANNEL_ID", "").strip()
STATE_PATH = Path(os.getenv("GOLD_PRICED_IN_ANALYST_STATE_PATH", "gold_priced_in_analyst_state.json"))
PRE_TITLE = "پیش‌تحلیل رویداد اقتصادی"
POST_TITLE = "نتیجه رویداد اقتصادی"


def load_state():
    if not STATE_PATH.exists():
        return {"offset": 0, "processed": []}
    data = json.loads(STATE_PATH.read_text(encoding="utf-8"))
    if not isinstance(data, dict):
        raise RuntimeError("Invalid analyst state")
    data.setdefault("offset", 0)
    data.setdefault("processed", [])
    return data


def save_state(state):
    STATE_PATH.parent.mkdir(parents=True, exist_ok=True)
    fd, name = tempfile.mkstemp(prefix=".priced-in-", dir=str(STATE_PATH.parent))
    try:
        with os.fdopen(fd, "w", encoding="utf-8") as handle:
            json.dump(state, handle, ensure_ascii=False, indent=2)
            handle.flush()
            os.fsync(handle.fileno())
        Path(name).replace(STATE_PATH)
    except Exception:
        Path(name).unlink(missing_ok=True)
        raise


def telegram(method, payload, timeout=30):
    response = requests.post(f"https://api.telegram.org/bot{TOKEN}/{method}", json=payload, timeout=timeout)
    response.raise_for_status()
    data = response.json()
    if not data.get("ok"):
        raise RuntimeError(f"Telegram {method} failed: {data.get('description', 'unknown error')}")
    return data["result"]


def is_target_post(message):
    text = message.get("text") or message.get("caption") or ""
    if PRE_TITLE in text:
        return "pre"
    if POST_TITLE in text:
        return "post"
    return None


def extract_fields(text):
    fields = {}
    for line in text.splitlines():
        line = re.sub(r"<[^>]+>", "", line).strip()
        for label, key in (
            ("زمان کابل:", "time"), ("پیش‌بینی عددی Forex Factory:", "forecast"),
            ("عدد واقعی:", "actual"), ("عدد قبلی:", "previous"),
        ):
            if label in line:
                fields[key] = line.split(label, 1)[1].strip()
        if " | " in line and not fields.get("event"):
            fields["event"] = line.replace("🌍", "").strip()
    return fields


def process_update(update):
    message = update.get("channel_post") or update.get("edited_channel_post")
    if not message or str(message.get("chat", {}).get("id")) != CHAT_ID:
        return False
    kind = is_target_post(message)
    if not kind:
        return False
    msg_id = int(message["message_id"])
    text = message.get("text") or message.get("caption") or ""
    fields = extract_fields(text)
    analysis, chart_symbol, event_dt = analyze_report(kind, text, fields)
    reply = telegram("sendMessage", {
        "chat_id": CHAT_ID,
        "text": analysis,
        "parse_mode": "HTML",
        "disable_web_page_preview": True,
        "reply_to_message_id": msg_id,
        "allow_sending_without_reply": True,
    })
    try:
        chart_path, chart_note = make_chart(chart_symbol, event_dt, kind)
        with open(chart_path, "rb") as photo:
            response = requests.post(
                f"https://api.telegram.org/bot{TOKEN}/sendPhoto",
                data={"chat_id": CHAT_ID, "reply_to_message_id": msg_id,
                      "caption": escape(chart_note), "parse_mode": "HTML"},
                files={"photo": photo}, timeout=45,
            )
            response.raise_for_status()
            result = response.json()
            if not result.get("ok"):
                raise RuntimeError(result.get("description", "sendPhoto failed"))
    except Exception as exc:
        print(f"Chart delivery unavailable for message {msg_id}: {type(exc).__name__}: {exc}")
    return True


def main():
    if not TOKEN or not CHAT_ID:
        raise RuntimeError("Set GOLD_PRICED_IN_ANALYST_BOT_TOKEN and CHANNEL_ID.")
    state = load_state()
    offset = int(state.get("offset", 0))
    result = telegram("getUpdates", {
        "offset": offset,
        "timeout": 0,
        "allowed_updates": ["channel_post", "edited_channel_post"],
    }, timeout=25)
    updates = sorted(result, key=lambda item: item["update_id"])
    processed = set(state.get("processed", []))
    for update in updates:
        update_id = int(update["update_id"])
        try:
            message = update.get("channel_post") or update.get("edited_channel_post") or {}
            msg_id = message.get("message_id")
            unique = f'{message.get("chat", {}).get("id")}:{msg_id}'
            if unique and unique not in processed:
                if process_update(update):
                    processed.add(unique)
                    state["processed"] = sorted(processed)[-1000:]
            state["offset"] = update_id + 1
            save_state(state)
        except Exception as exc:
            # Do not advance offset on a failed delivery; the update is retried next run.
            print(f"Update {update_id} failed: {type(exc).__name__}: {exc}")
            raise
    print(f"Checked {len(updates)} Telegram updates; processed eligible posts: {len(processed)}.")


if __name__ == "__main__":
    main()
