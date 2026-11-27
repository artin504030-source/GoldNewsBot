from __future__ import annotations

import json
import os
import re
import tempfile
import time
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
    for attempt in range(4):
        response = requests.post(f"https://api.telegram.org/bot{TOKEN}/{method}", json=payload, timeout=timeout)
        try:
            data = response.json()
        except ValueError:
            response.raise_for_status()
            raise RuntimeError(f"Telegram {method} returned invalid JSON.")

        if response.status_code == 429 or data.get("error_code") == 429:
            retry_after = int((data.get("parameters") or {}).get("retry_after", 2))
            if attempt == 3:
                raise RuntimeError(f"Telegram {method} rate limited after retries; retry_after={retry_after}s.")
            wait_seconds = min(max(retry_after + 1, 2), 60)
            print(f"Telegram rate limit on {method}; waiting {wait_seconds}s before retry.")
            time.sleep(wait_seconds)
            continue

        response.raise_for_status()
        if not data.get("ok"):
            raise RuntimeError(f"Telegram {method} failed: {data.get('description', 'unknown error')}")
        return data["result"]
    raise RuntimeError(f"Telegram {method} failed after retry attempts.")


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


def is_target_chat(chat):
    configured = CHAT_ID.strip()
    if str(chat.get("id", "")) == configured:
        return True
    username = (chat.get("username") or "").lstrip("@").lower()
    return bool(configured.startswith("@") and username == configured[1:].lower())


def verify_channel_admin():
    me = telegram("getMe", {})
    member = telegram("getChatMember", {"chat_id": CHAT_ID, "user_id": me["id"]})
    status = member.get("status")
    print(f"Priced-In bot identity verified; target channel admin status: {status}.")
    if status not in ("administrator", "creator"):
        raise RuntimeError(
            "Priced-In Analyst bot is not an administrator in the target channel. "
            "Promote this bot to channel admin, then retry."
        )
    if not member.get("can_pin_messages", False):
        print(
            "WARNING: Priced-In Analyst bot lacks can_pin_messages permission. "
            "Analysis and chart will still be delivered; pinning will be attempted and may fail."
        )


def pin_channel_message(message_id):
    try:
        telegram("pinChatMessage", {
            "chat_id": CHAT_ID,
            "message_id": int(message_id),
            "disable_notification": True,
        })
        return True
    except Exception as exc:
        print(f"WARNING: Could not silently pin Telegram message {message_id}: {type(exc).__name__}: {exc}")
        return False


def send_chart_photo(chart_path, caption, reply_to_message_id):
    for attempt in range(4):
        with open(chart_path, "rb") as photo:
            response = requests.post(
                f"https://api.telegram.org/bot{TOKEN}/sendPhoto",
                data={
                    "chat_id": CHAT_ID,
                    "reply_to_message_id": int(reply_to_message_id),
                    "caption": escape(caption),
                    "parse_mode": "HTML",
                },
                files={"photo": photo},
                timeout=60,
            )
        try:
            data = response.json()
        except ValueError:
            response.raise_for_status()
            raise RuntimeError("Telegram sendPhoto returned invalid JSON.")

        if response.status_code == 429 or data.get("error_code") == 429:
            retry_after = int((data.get("parameters") or {}).get("retry_after", 2))
            if attempt == 3:
                raise RuntimeError(f"Telegram sendPhoto rate limited after retries; retry_after={retry_after}s.")
            wait_seconds = min(max(retry_after + 1, 2), 60)
            print(f"Telegram rate limit on sendPhoto; waiting {wait_seconds}s before retry.")
            time.sleep(wait_seconds)
            continue

        response.raise_for_status()
        if not data.get("ok"):
            raise RuntimeError(data.get("description", "Telegram sendPhoto failed"))
        return data["result"]
    raise RuntimeError("Telegram sendPhoto failed after retry attempts.")


def process_update(update):
    message = update.get("channel_post") or update.get("edited_channel_post")
    if not message or not is_target_chat(message.get("chat", {})):
        return False
    kind = is_target_post(message)
    if not kind:
        return False
    msg_id = int(message["message_id"])
    text = message.get("text") or message.get("caption") or ""
    fields = extract_fields(text)
    analysis, chart_symbol, event_dt = analyze_report(kind, text, fields)

    # Pin the written analysis first so it remains available even if chart delivery fails.
    reply = telegram("sendMessage", {
        "chat_id": CHAT_ID,
        "text": analysis,
        "parse_mode": "HTML",
        "disable_web_page_preview": True,
        "reply_to_message_id": msg_id,
        "allow_sending_without_reply": True,
    })
    analysis_pinned = pin_channel_message(reply["message_id"])
    if analysis_pinned:
        print(f"Pinned Priced-In analysis message {reply['message_id']}.")

    chart_path = None
    try:
        chart_path, chart_note = make_chart(chart_symbol, event_dt, kind)
        chart_message = send_chart_photo(chart_path, chart_note, msg_id)
        chart_pinned = pin_channel_message(chart_message["message_id"])
        print(
            f"Sent chart message {chart_message['message_id']} for report {msg_id}; "
            f"silently_pinned={chart_pinned}."
        )
    except Exception as exc:
        print(f"Chart delivery/pinning failed for report {msg_id}: {type(exc).__name__}: {exc}")
        raise
    finally:
        if chart_path:
            Path(chart_path).unlink(missing_ok=True)
    return True


def discard_pending_updates(state):
    offset = int(state.get("offset", 0))
    discarded = 0
    for _ in range(10):
        updates = telegram("getUpdates", {
            "offset": offset,
            "timeout": 0,
            "allowed_updates": ["channel_post", "edited_channel_post"],
        }, timeout=25)
        if not updates:
            break
        updates = sorted(updates, key=lambda item: item["update_id"])
        offset = int(updates[-1]["update_id"]) + 1
        discarded += len(updates)
        state["offset"] = offset
        save_state(state)
        if len(updates) < 100:
            break
    print(f"Discarded {discarded} pending historical Telegram updates; next offset={offset}.")
    return discarded


def main():
    if not TOKEN or not CHAT_ID:
        raise RuntimeError("Set GOLD_PRICED_IN_ANALYST_BOT_TOKEN and CHANNEL_ID.")
    verify_channel_admin()
    state = load_state()
    if os.getenv("PRICED_IN_MODE", "analyze").strip().lower() == "discard_pending":
        discard_pending_updates(state)
        return
    offset = int(state.get("offset", 0))
    result = telegram("getUpdates", {
        "offset": offset,
        "timeout": 0,
        "allowed_updates": ["channel_post", "edited_channel_post"],
    }, timeout=25)
    updates = sorted(result, key=lambda item: item["update_id"])
    print(f"Telegram polling completed: {len(updates)} pending updates; saved offset={offset}.")
    processed = set(state.get("processed", []))
    for update in updates:
        update_id = int(update["update_id"])
        try:
            message = update.get("channel_post") or update.get("edited_channel_post") or {}
            msg_id = message.get("message_id")
            if message and is_target_chat(message.get("chat", {})):
                print(f"Received target-channel post {msg_id}; recognized event heading: {bool(is_target_post(message))}.")
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
