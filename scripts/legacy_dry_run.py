#!/usr/bin/env python3
"""Safe, one-feed RSS preview for GoldNewsBot. No Telegram or state writes."""
from __future__ import annotations
import argparse
import ast
from pathlib import Path
import requests
import xml.etree.ElementTree as ET

USER_AGENT = "GoldNewsBot-ReadOnly-Preview/1.0"

def load_feed_registry(bot_file: Path) -> dict[str, str]:
    """Read the literal FEEDS dict from news_bot.py without importing it."""
    tree = ast.parse(bot_file.read_text(encoding="utf-8"), filename=str(bot_file))
    for node in tree.body:
        if isinstance(node, ast.Assign) and any(isinstance(t, ast.Name) and t.id == "FEEDS" for t in node.targets):
            value = ast.literal_eval(node.value)
            if not isinstance(value, dict) or not all(isinstance(k, str) and isinstance(v, str) for k, v in value.items()):
                raise ValueError("FEEDS must be a string-to-string literal dictionary")
            return value
    raise ValueError("Could not find a literal FEEDS dictionary in news_bot.py")

def fetch_preview(url: str, limit: int = 5, timeout: int = 15, http_get=requests.get) -> list[dict[str, str]]:
    if not 1 <= limit <= 20:
        raise ValueError("limit must be between 1 and 20")
    response = http_get(url, headers={"User-Agent": USER_AGENT}, timeout=timeout)
    response.raise_for_status()
    try:
        xml_root = ET.fromstring(response.content)
    except ET.ParseError as exc:
        raise ValueError("Feed could not be parsed") from exc
    output = []
    entries = xml_root.findall("./channel/item")
    if not entries:
        entries = [node for node in xml_root.iter() if node.tag.rsplit("}", 1)[-1] == "entry"]
    for entry in entries[:limit]:
        fields = {}
        for child in list(entry):
            name = child.tag.rsplit("}", 1)[-1]
            fields[name] = (child.text or "").strip()
            if name == "link" and not fields[name]:
                fields[name] = child.attrib.get("href", "")
        output.append({"title": fields.get("title") or "(untitled)", "link": fields.get("link", ""), "published": fields.get("pubDate") or fields.get("published") or fields.get("updated") or "unknown"})
    return output

def main() -> int:
    parser = argparse.ArgumentParser(description="Read-only RSS preview; no Telegram messages are sent")
    parser.add_argument("--source", required=True, help="Exact source name from FEEDS in news_bot.py")
    parser.add_argument("--limit", type=int, default=5)
    parser.add_argument("--root", type=Path, default=Path(__file__).resolve().parents[1])
    args = parser.parse_args()
    feeds = load_feed_registry(args.root / "news_bot.py")
    if args.source not in feeds:
        parser.error("Unknown source. Available sources: " + ", ".join(feeds))
    try:
        items = fetch_preview(feeds[args.source], limit=args.limit)
    except (requests.RequestException, ValueError) as exc:
        print(f"Preview failed: {type(exc).__name__}: {exc}")
        return 1
    print(f"Read-only preview | source={args.source} | items={len(items)}")
    for index, item in enumerate(items, 1):
        print(f"\n{index}. {item['title']}\n   Published: {item['published']}\n   Link: {item['link']}")
    print("\nNo Telegram message sent. No seen/archive files changed.")
    return 0

if __name__ == "__main__":
    raise SystemExit(main())
