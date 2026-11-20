import os
import requests


def main():
    token = os.getenv("BOT_TOKEN")
    chat_id = os.getenv("ALERT_CHAT_ID") or os.getenv("CHANNEL_ID")
    if not token or not chat_id:
        print("Telegram secrets unavailable; cannot send immediate health alert.")
        return
    workflow = os.getenv("GITHUB_WORKFLOW", "Gold News Bot")
    run_url = os.getenv("GITHUB_SERVER_URL", "https://github.com") + "/" + os.getenv("GITHUB_REPOSITORY", "") + "/actions/runs/" + os.getenv("GITHUB_RUN_ID", "")
    message = (f"🚨 هشدار سلامت Gold News\nاجرای سیستم با خطا پایان یافت.\n"
               f"سیستم: {workflow}\nشاخه: {os.getenv('GITHUB_REF_NAME', 'main')}\n"
               f"تلاش: {os.getenv('GITHUB_RUN_ATTEMPT', '1')}\nجزئیات اجرا: {run_url}")
    response = requests.post(f"https://api.telegram.org/bot{token}/sendMessage",
        data={"chat_id": chat_id, "text": message, "disable_web_page_preview": True}, timeout=20)
    response.raise_for_status()
    result = response.json()
    if not result.get("ok"):
        raise RuntimeError(f"Telegram alert failed: {result}")
    print("Immediate Telegram failure alert sent.")


if __name__ == "__main__":
    main()
