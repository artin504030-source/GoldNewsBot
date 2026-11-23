"""Send a one-off, explicitly requested Telegram delivery test."""
import json
import os
import sys
import urllib.parse
import urllib.request
import urllib.error
from datetime import datetime, timezone


def main() -> int:
    token = os.getenv("TELEGRAM_BOT_TOKEN")
    chat_id = os.getenv("TELEGRAM_CHAT_ID")
    label = os.getenv("TELEGRAM_TEST_LABEL", "Telegram")
    footer = os.getenv("TELEGRAM_TEST_FOOTER", "Gold Admin")
    if not token or not chat_id:
        raise RuntimeError("Telegram test secrets are missing")
    stamp = datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M UTC")
    message = (f"🧪 <b>تست تحویل پیام | {label}</b>\n"
               f"این پیام برای بررسی اتصال ربات به کانال ارسال شده است.\n"
               f"زمان: <code>{stamp}</code>\n\n"
               f"<b>{footer.replace('|', '</b>\n<b>')}</b>")
    body = urllib.parse.urlencode({"chat_id": chat_id, "text": message,
                                   "parse_mode": "HTML", "disable_web_page_preview": "true"}).encode()
    req = urllib.request.Request(f"https://api.telegram.org/bot{token}/sendMessage", data=body)
    try:
        with urllib.request.urlopen(req, timeout=20) as response:
            result = json.loads(response.read().decode())
    except urllib.error.HTTPError as exc:
        raise RuntimeError(f"Telegram HTTP {exc.code}: {exc.read().decode('utf-8', 'replace')}") from exc
    if not result.get("ok"):
        raise RuntimeError(f"Telegram rejected test message: {result}")
    msg = result.get("result", {})
    chat = msg.get("chat", {})
    print(f"Telegram accepted test message: message_id={msg.get('message_id')}, chat_type={chat.get('type')}, chat_title={chat.get('title', 'private')}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
