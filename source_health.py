import json
from datetime import datetime, timezone
from pathlib import Path

DEFAULT_FILE = Path(__file__).resolve().parent / "source_health.json"

def _now():
    return datetime.now(timezone.utc).isoformat()

def load_source_health(path=DEFAULT_FILE):
    try:
        data = json.loads(Path(path).read_text(encoding="utf-8"))
        return data if isinstance(data, dict) else {"sources": {}}
    except (FileNotFoundError, json.JSONDecodeError):
        return {"sources": {}}

def record_source_check(source, success, entries_count=0, error=None, mode="regular", path=DEFAULT_FILE, checked_at=None):
    data = load_source_health(path)
    data.setdefault("sources", {})
    stamp = checked_at or _now()
    item = data["sources"].setdefault(source, {"success_count": 0, "failure_count": 0})
    item.update({"last_status": "success" if success else "failure", "last_checked_utc": stamp, "last_entries_count": int(entries_count), "last_mode": mode, "last_error": None if success else str(error or "Unknown error")[:500]})
    if success:
        item["success_count"] = int(item.get("success_count", 0)) + 1
        item["last_success_utc"] = stamp
    else:
        item["failure_count"] = int(item.get("failure_count", 0)) + 1
        item["last_failure_utc"] = stamp
    data["updated_at_utc"] = stamp
    data["last_mode"] = mode
    target = Path(path)
    target.parent.mkdir(parents=True, exist_ok=True)
    temp = target.with_suffix(target.suffix + ".tmp")
    temp.write_text(json.dumps(data, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    temp.replace(target)
    return data

def summarize_source_health(path=DEFAULT_FILE):
    data = load_source_health(path)
    sources = data.get("sources", {})
    healthy = [name for name, item in sources.items() if item.get("last_status") == "success"]
    failed = [name for name, item in sources.items() if item.get("last_status") == "failure"]
    unknown = [name for name, item in sources.items() if item.get("last_status") not in {"success", "failure"}]
    return {"updated_at_utc": data.get("updated_at_utc"), "last_mode": data.get("last_mode"), "checked_count": len(sources), "healthy_count": len(healthy), "failed_count": len(failed), "unknown_count": len(unknown), "healthy_sources": healthy, "failed_sources": failed, "sources": sources}

def format_source_health(summary):
    lines = ["🩺 وضعیت منابع خبری (آخرین بررسی ثبت‌شده)", f"موفق: {summary['healthy_count']} | ناموفق: {summary['failed_count']} | ثبت‌شده: {summary['checked_count']}"]
    if summary.get("updated_at_utc"):
        lines.append("آخرین به‌روزرسانی: " + summary["updated_at_utc"].replace("T", " ").replace("+00:00", " UTC"))
    for name, item in summary.get("sources", {}).items():
        status = "✅" if item.get("last_status") == "success" else "❌" if item.get("last_status") == "failure" else "⚪"
        detail = f"{item.get('last_entries_count', 0)} مورد" if item.get("last_status") == "success" else str(item.get("last_error") or "خطای نامشخص")[:100]
        lines.append(f"{status} {name}: {detail}")
    lines.append("توجه: وضعیت هر منبع مربوط به آخرین تلاش ثبت‌شده است؛ منابعی که در اجرای اخیر بررسی نشده‌اند ممکن است وضعیت قدیمی داشته باشند.")
    return "\n".join(lines)
