import os
import requests

token = os.getenv("BOT_TOKEN")
chat_id = os.getenv("CHANNEL_ID")
if token and chat_id:
    try:
        r = requests.post(f"https://api.telegram.org/bot{token}/sendMessage",
            data={"chat_id": chat_id, "text": "⚠️ هشدار سلامت Gold News Bot: اجرای GitHub Actions با خطا متوقف شد. لطفاً بخش Actions مخزن را بررسی کنید."}, timeout=20)
        r.raise_for_status()
        if not r.json().get("ok"):
            print("Telegram alert failed:", r.text[:300])
    except Exception as exc:
        print("Could not send health alert:", exc)
else:
    print("Telegram secrets unavailable; cannot send health alert.")
