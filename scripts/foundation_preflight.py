#!/usr/bin/env python3
"""Read-only preflight checks for the legacy GoldNewsBot repository.

This utility never imports news_bot.py, sends Telegram messages, or writes state.
Run from the repository root: python scripts/foundation_preflight.py
"""
from __future__ import annotations
import argparse
import json
import os
from pathlib import Path

REQUIRED_PATHS = ("news_bot.py", "telegram_news_commands.py", "requirements.txt", "news_archive.json", "seen_news.json", ".github/workflows/news.yml")
JSON_PATHS = ("news_archive.json", "seen_news.json")

def inspect_project(root: Path) -> list[tuple[str, str, str]]:
    results = []
    for rel in REQUIRED_PATHS:
        path = root / rel
        results.append(("PASS" if path.is_file() else "FAIL", "file", rel))
    for rel in JSON_PATHS:
        path = root / rel
        if not path.is_file():
            continue
        try:
            value = json.loads(path.read_text(encoding="utf-8"))
            ok = isinstance(value, list)
            results.append(("PASS" if ok else "FAIL", "json-list", rel))
        except (OSError, UnicodeError, json.JSONDecodeError):
            results.append(("FAIL", "json-parse", rel))
    env_path = root / ".env"
    if env_path.exists():
        results.append(("PASS", "env-file", ".env exists (contents not displayed)"))
    else:
        results.append(("WARN", "env-file", ".env absent; CI secrets may supply runtime config"))
    return results

def main() -> int:
    parser = argparse.ArgumentParser(description="Read-only GoldNewsBot foundation preflight")
    parser.add_argument("--root", type=Path, default=Path(__file__).resolve().parents[1])
    parser.add_argument("--require-runtime-secrets", action="store_true", help="fail if BOT_TOKEN or CHANNEL_ID are not set in environment")
    args = parser.parse_args()
    results = inspect_project(args.root.resolve())
    for status, kind, detail in results:
        print(f"[{status}] {kind}: {detail}")
    if args.require_runtime_secrets:
        for key in ("BOT_TOKEN", "CHANNEL_ID"):
            present = bool(os.getenv(key))
            print(f"[{'PASS' if present else 'FAIL'}] runtime-secret: {key} {'configured' if present else 'missing'}")
            if not present:
                results.append(("FAIL", "runtime-secret", key))
    failures = sum(status == "FAIL" for status, _, _ in results)
    print(f"\nSummary: {len(results)} checks, {failures} failures")
    return 1 if failures else 0

if __name__ == "__main__":
    raise SystemExit(main())
