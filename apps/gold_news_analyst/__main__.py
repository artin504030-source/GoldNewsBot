from __future__ import annotations
import json, os, tempfile
from pathlib import Path
from datetime import datetime, timezone
import requests
from .config import Settings
from .engine import eligible, fingerprint, parse_time
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

def send(token, chat_id, text, reply_to_message_id=None):
    payload = {"chat_id": chat_id, "text": text, "parse_mode": "HTML", "disable_web_page_preview": True}
    if reply_to_message_id:
        payload["reply_to_message_id"] = int(reply_to_message_id)
        payload["allow_sending_without_reply"] = True
    response = requests.post(f"https://api.telegram.org/bot{token}/sendMessage", data=payload, timeout=25)
    response.raise_for_status(); body = response.json()
    if not body.get("ok"): raise RuntimeError("Telegram rejected analyst message")
    return body

def fetch_article(item, enabled=True, session=None):
    result = {"body": "", "final_url": item.get("link", ""), "status": "not_attempted"}
    if not enabled:
        result["error"] = "دریافت متن مقاله غیرفعال است"
        return result
    url = item.get("link", "")
    if not isinstance(url, str) or not url.startswith(("https://", "http://")):
        result["error"] = "لینک معتبر HTTP/HTTPS موجود نیست"
        return result
    try:
        from goldnewsbot.safe_fetch import fetch_public_page
        from goldnewsbot.pipeline_preview import extract_text
        from .google_news import resolve_article_url
        session = session or requests.Session()
        publisher_url = resolve_article_url(url, session=session, timeout=15)
        html, final_url = fetch_public_page(publisher_url, session=session, timeout=12, max_bytes=1_000_000, max_redirects=3)
        body = extract_text(html, max_chars=24000, min_chars=80)
        result.update({"body": body, "final_url": final_url, "status": "fetched" if len(body) >= 300 else "partial"})
        if len(body) < 300:
            result["error"] = "صفحه ناشر باز شد، اما متن مقاله کافی استخراج نشد"
    except Exception as exc:
        # Article fetch is best-effort; the analyst must explicitly downgrade confidence.
        result["status"] = "failed"
        result["error"] = f"دریافت/تبدیل لینک خبر ناموفق بود: {type(exc).__name__}: {str(exc)[:160]}"
    return result

def main():
    cfg = Settings.from_env(); now = datetime.now(timezone.utc)
    archive = load_json(cfg.archive_path, []); state = load_json(cfg.state_path, {"sent": []})
    if not isinstance(archive, list) or not isinstance(state, dict): raise RuntimeError("Invalid archive/state structure")
    sent = set(state.get("sent", []))
    # For workflow_run events, analyse only items archived by the News Bot or
    # Breaking Monitor run that just completed. archive_news() is called only
    # after Telegram delivery, so the analyst replies to the corresponding post.
    triggered_after = parse_time(os.getenv("GOLD_NEWS_ANALYST_TRIGGERED_AFTER", ""))
    candidates = [
        x for x in archive
        if isinstance(x, dict)
        and eligible(x, now, cfg.max_age_hours, cfg.min_relevance)
        and fingerprint(x) not in sent
        and (
            triggered_after is None
            or (parse_time(x.get("archived_at_utc")) is not None
                and parse_time(x.get("archived_at_utc")) >= triggered_after)
        )
    ]
    candidates.sort(key=lambda x: x.get("published_utc", ""), reverse=True); selected = candidates[:cfg.max_items]
    print(f"archive={len(archive)} eligible={len(candidates)} selected={len(selected)} dry_run={cfg.dry_run} triggered_after={triggered_after.isoformat() if triggered_after else 'manual/backfill'}")
    if not selected:
        print("No new eligible news items.")
        return
    http_session = requests.Session()
    for item in selected:
        article = fetch_article(item, cfg.article_fetch, http_session)
        print(f"article status={article.get('status')} url={article.get('final_url')} chars={len(article.get('body',''))}")
        message = render(item, article)
        if cfg.dry_run:
            print(message)
            print("\n" + "=" * 72 + "\n")
            continue
        reply_to_id = item.get("telegram_message_id")
        send(cfg.token, item.get("telegram_chat_id") or cfg.chat_id, message, reply_to_message_id=reply_to_id)
        sent.add(fingerprint(item))
        state["sent"] = sorted(sent)[-2000:]
        save_json_atomic(cfg.state_path, state)

if __name__ == "__main__": main()
