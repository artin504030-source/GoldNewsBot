"""Resolve modern Google News RSS redirect tokens to publisher URLs.

Google's current resolver is undocumented and may change; failures are explicit
and never masquerade as successful publisher-page extraction.
"""
from __future__ import annotations
import json
import re
from urllib.parse import urlparse
import requests
from goldnewsbot.safe_fetch import validate_url

GOOGLE_NEWS_HOSTS = {"news.google.com"}
PARAMS = re.compile(r'data-n-a-sg="([^"]+)".*?data-n-a-ts="([^"]+)"|data-n-a-ts="([^"]+)".*?data-n-a-sg="([^"]+)"', re.S)

class GoogleNewsDecodeError(RuntimeError):
    pass

def resolve_article_url(url, session=None, timeout=15, resolver=None):
    parsed = urlparse(str(url or ""))
    if parsed.hostname not in GOOGLE_NEWS_HOSTS:
        return validate_url(url, resolver) if resolver else validate_url(url)
    parts = [p for p in parsed.path.split("/") if p]
    if len(parts) < 2 or parts[-2] not in {"articles", "read"}:
        raise GoogleNewsDecodeError("Unsupported Google News article URL")
    article_id = parts[-1]
    session = session or requests.Session()
    headers = {
        "User-Agent": "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/131.0.0.0 Safari/537.36",
        "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
        "Accept-Language": "en-US,en;q=0.9",
        "Upgrade-Insecure-Requests": "1",
    }
    try:
        session.cookies.set("CONSENT", "PENDING+987", domain="news.google.com")
    except (AttributeError, TypeError):
        pass
    html = ""
    last_error = None
    for path in (f"https://news.google.com/rss/articles/{article_id}", f"https://news.google.com/articles/{article_id}"):
        try:
            response = session.get(path, headers=headers, timeout=timeout)
            response.raise_for_status()
            html = response.text[:2_000_000]
            match = PARAMS.search(html)
            if match:
                if match.group(1):
                    signature, timestamp = match.group(1), match.group(2)
                else:
                    timestamp, signature = match.group(3), match.group(4)
                break
            last_error = "Google page did not contain resolver signature/timestamp (consent, rate limit, or page change)"
        except requests.RequestException as exc:
            last_error = f"Google article page request failed: {type(exc).__name__}"
    else:
        raise GoogleNewsDecodeError(last_error or "Google News resolver parameters unavailable")
    try:
        timestamp_int = int(timestamp)
        inner = json.dumps([
            "garturlreq",
            [["X", "X", ["X", "X"], None, None, 1, 1, "US:en", None, 1, None, None, None, None, None, 0, 1],
             "X", "X", 1, [1, 1, 1], 1, 1, None, 0, 0, None, 0],
            article_id, timestamp_int, signature
        ], separators=(",", ":"))
        outer = json.dumps([[["Fbv4je", inner]]], separators=(",", ":"))
        post_headers = {
            **headers,
            "Content-Type": "application/x-www-form-urlencoded;charset=UTF-8",
            "Origin": "https://news.google.com",
            "Referer": "https://news.google.com/",
            "X-Same-Domain": "1",
        }
        response = session.post(
            "https://news.google.com/_/DotsSplashUi/data/batchexecute",
            data={"f.req": outer},
            headers=post_headers,
            timeout=timeout,
        )
        response.raise_for_status()
        raw = response.text
        if "\n\n" in raw:
            raw = raw.split("\n\n", 1)[1]
        else:
            raw = re.sub(r"^\)\]\}'\s*", "", raw)
        frames = json.loads(raw)
        frame = next((row for row in frames if isinstance(row, list) and len(row) > 2 and row[0] == "wrb.fr" and row[1] == "Fbv4je"), None)
        if not frame or not frame[2]:
            raise GoogleNewsDecodeError("Google resolver returned no publisher URL")
        decoded = json.loads(frame[2])
        if not isinstance(decoded, list) or len(decoded) < 2 or not isinstance(decoded[1], str):
            raise GoogleNewsDecodeError("Google resolver response format was unexpected")
        destination = decoded[1]
        return validate_url(destination, resolver) if resolver else validate_url(destination)
    except GoogleNewsDecodeError:
        raise
    except (requests.RequestException, ValueError, TypeError, KeyError, StopIteration) as exc:
        raise GoogleNewsDecodeError(f"Google News URL resolution failed: {type(exc).__name__}") from exc
