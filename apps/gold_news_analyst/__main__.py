from __future__ import annotations
import json, os, tempfile
from pathlib import Path
from datetime import datetime, timezone
import requests
from .config import Settings
from .engine import eligible, fingerprint
from .report import render

def load_json(path, default):
    try: return json.loads(Path(path).read_text(encoding="utf-8"))
    except FileNotFoundError: return default
    except (json.JSONDecodeError, OSError) as exc: raise RuntimeError(f"Cannot read {path}: {exc}") from exc

def save_json_atomic(path, data):
    target = Path(path); target.parent.mkdir(parents=True, exist_ok=True)
    fd, temp_name = tempfile.mkstemp(prefix=f".{target.name}.", suffix=".tmp", dir=str(target.parent))
    try:
        with os.fdopen(fd, "w", encoding="utf-8") as handle:
            json.dump(data, handle, ensure_ascii=False, indent=2); handle.flush(); os.fsync(handle.fileno())
        Path(temp_name).replace(target)
    except Exception:
        try: Path(temp_name).unlink(missing_ok=True)
        except OSError: pass
        raise

def send(token, chat_id, text):
    response = requests.post(f"https://api.telegram.org/bot{token}/sendMessage", data={"chat_id": chat_id, "text": text, "parse_mode": "HTML", "disable_web_page_preview": True}, timeout=25)
    response.raise_for_status(); body = response.json()
    if not body.get("ok"): raise RuntimeError("Telegram rejected analyst message")
    return body

def main():
    cfg = Settings.from_env(); now = datetime.now(timezone.utc)
    archive = load_json(cfg.archive_path, []); state = load_json(cfg.state_path, {"sent": []})
    if not isinstance(archive, list) or not isinstance(state, dict): raise RuntimeError("Invalid archive/state structure")
    sent = set(state.get("sent", []))
    candidates = [x for x in archive if isinstance(x, dict) and eligible(x, now, cfg.max_age_hours, cfg.min_relevance) and fingerprint(x) not in sent]
    candidates.sort(key=lambda x: x.get("published_utc", ""), reverse=True); selected = candidates[:cfg.max_items]
    print(f"archive={len(archive)} eligible={len(candidates)} selected={len(selected)} dry_run={cfg.dry_run}")
    if cfg.dry_run:
        for item in selected: print(render(item))
        return
    for item in selected:
        send(cfg.token, cfg.chat_id, render(item)); sent.add(fingerprint(item))
        state["sent"] = sorted(sent)[-2000:]; save_json_atomic(cfg.state_path, state)

if __name__ == "__main__": main()
