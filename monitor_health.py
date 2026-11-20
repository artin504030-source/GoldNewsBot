import json
import os
from datetime import datetime, timezone, timedelta
from pathlib import Path

import requests

ROOT = Path(__file__).resolve().parent
STATE_PATH = ROOT / "health_alert_state.json"
SOURCE_PATH = ROOT / "source_health.json"
OWNER, REPO = os.getenv("GITHUB_REPOSITORY", "artin504030-source/GoldNewsBot").split("/", 1)
GITHUB_TOKEN = os.getenv("GITHUB_TOKEN")
BOT_TOKEN = os.getenv("BOT_TOKEN")
CHAT_ID = os.getenv("ALERT_CHAT_ID") or os.getenv("CHANNEL_ID")
API = f"https://api.github.com/repos/{OWNER}/{REPO}"
WORKFLOWS = {
    "Gold News Breaking Monitor": {"file": "breaking_news.yml", "interval": 5, "stale": 20},
    "Gold News Bot": {"file": "news.yml", "interval": 15, "stale": 45},
    "Gold News Daily Digest": {"file": "daily_digest.yml", "interval": 1440, "stale": 1560},
}


def parse_dt(value):
    if not value:
        return None
    try:
        return datetime.fromisoformat(value.replace("Z", "+00:00")).astimezone(timezone.utc)
    except (TypeError, ValueError):
        return None


def load_state():
    try:
        data = json.loads(STATE_PATH.read_text(encoding="utf-8"))
        return data if isinstance(data, dict) else {"active_alerts": {}}
    except (FileNotFoundError, json.JSONDecodeError):
        return {"active_alerts": {}}


def send_telegram(text):
    if os.getenv("DRY_RUN", "false").lower() == "true":
        print("[DRY RUN] Telegram alert was not sent:")
        print(text)
        return
    if not BOT_TOKEN or not CHAT_ID:
        raise RuntimeError("BOT_TOKEN or CHANNEL_ID/ALERT_CHAT_ID is missing")
    response = requests.post(
        f"https://api.telegram.org/bot{BOT_TOKEN}/sendMessage",
        data={"chat_id": CHAT_ID, "text": text, "disable_web_page_preview": True},
        timeout=25,
    )
    response.raise_for_status()
    payload = response.json()
    if not payload.get("ok"):
        raise RuntimeError(f"Telegram API error: {payload}")


def set_alert(state, key, fingerprint, message):
    current = state.setdefault("active_alerts", {})
    old = current.get(key)
    if old and old.get("fingerprint") == fingerprint:
        return False
    send_telegram(message)
    current[key] = {"fingerprint": fingerprint, "sent_at_utc": datetime.now(timezone.utc).isoformat()}
    print(f"Alert sent: {key}")
    return True


def clear_alert(state, key, recovery_message):
    old = state.setdefault("active_alerts", {}).pop(key, None)
    if old:
        send_telegram(recovery_message)
        print(f"Recovery sent: {key}")
        return True
    return False


def get_scheduled_runs(workflow_file):
    if not GITHUB_TOKEN:
        raise RuntimeError("GITHUB_TOKEN is missing")
    response = requests.get(
        f"{API}/actions/workflows/{workflow_file}/runs",
        params={"branch": "main", "per_page": 30},
        headers={"Authorization": f"Bearer {GITHUB_TOKEN}", "Accept": "application/vnd.github+json", "X-GitHub-Api-Version": "2022-11-28"},
        timeout=25,
    )
    response.raise_for_status()
    runs = response.json().get("workflow_runs", [])
    scheduled = [run for run in runs if run.get("event") == "schedule" and run.get("head_branch") == "main"]
    scheduled.sort(key=lambda item: item.get("created_at") or "", reverse=True)
    return scheduled


def inspect_workflows(state, now):
    for name, config in WORKFLOWS.items():
        key = "workflow:" + name
        try:
            runs = get_scheduled_runs(config["file"])
        except Exception as exc:
            # Do not turn a transient GitHub API problem into a false bot-down alert.
            print(f"Could not inspect {name}: {exc}")
            continue
        recent = runs[:3]
        failed = len(recent) == 3 and all(run.get("status") == "completed" and run.get("conclusion") == "failure" for run in recent)
        if failed:
            ids = ",".join(str(run.get("id")) for run in recent)
            set_alert(state, key + ":failures", ids,
                f"🚨 هشدار ربات Gold News\nسه اجرای زمان‌بندی‌شده پیاپی ناموفق بوده است.\nسیستم: {name}\nلطفاً Actions را بررسی کنید:\n{recent[0].get('html_url', '')}")
        else:
            clear_alert(state, key + ":failures", f"✅ رفع مشکل\nاجرای زمان‌بندی‌شده {name} دوباره به وضعیت عادی برگشته است.")

        latest = runs[0] if runs else None
        created = parse_dt((latest or {}).get("created_at"))
        stale = latest is None or created is None or (now - created) > timedelta(minutes=config["stale"])
        if stale:
            age = "هیچ اجرای زمان‌بندی‌شده‌ای پیدا نشد" if created is None else f"آخرین اجرا در {created.isoformat()} UTC ثبت شده است"
            fingerprint = (latest or {}).get("id", "no-run")
            set_alert(state, key + ":stale", str(fingerprint),
                f"⏰ هشدار تأخیر در اجرای ربات\nسیستم: {name}\n{age}\nحد تأخیر مجاز: {config['stale']} دقیقه\n{(latest or {}).get('html_url', '')}")
        else:
            clear_alert(state, key + ":stale", f"✅ اجرای خودکار {name} دوباره در زمان‌بندی مورد انتظار مشاهده شد.")


def inspect_sources(state, now):
    try:
        data = json.loads(SOURCE_PATH.read_text(encoding="utf-8"))
    except (FileNotFoundError, json.JSONDecodeError):
        print("source_health.json is not available yet")
        return
    for name, item in (data.get("sources") or {}).items():
        checked = parse_dt(item.get("last_checked_utc"))
        is_recent = checked is not None and (now - checked) <= timedelta(minutes=90)
        key = "source:" + name
        if item.get("last_status") == "failure" and is_recent:
            fingerprint = item.get("last_checked_utc") or item.get("last_error") or "failure"
            set_alert(state, key, str(fingerprint),
                f"⚠️ اختلال در منبع خبری\nمنبع: {name}\nخطا: {str(item.get('last_error') or 'خطای نامشخص')[:350]}\nزمان بررسی: {item.get('last_checked_utc', 'نامشخص')} UTC")
        else:
            clear_alert(state, key, f"✅ اتصال منبع خبری «{name}» دوباره موفق ثبت شد.")


def main():
    now = datetime.now(timezone.utc)
    state = load_state()
    inspect_workflows(state, now)
    inspect_sources(state, now)
    STATE_PATH.write_text(json.dumps(state, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(f"Health monitor completed at {now.isoformat()}; active alerts={len(state.get('active_alerts', {}))}")


if __name__ == "__main__":
    main()
