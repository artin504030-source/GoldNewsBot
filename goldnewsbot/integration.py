"""Adapter from the safe preview pipeline to the existing Gold News Bot."""
from urllib.parse import urlparse

from .pipeline_preview import preview_article
from .classification import classify_news
from apps.gold_news_analyst.google_news import GOOGLE_NEWS_HOSTS, resolve_article_url


def fetch_and_classify_article(url, title, fallback=""):
    resolved_url = url
    try:
        if urlparse(str(url or "")).hostname in GOOGLE_NEWS_HOSTS:
            resolved_url = resolve_article_url(url)
        preview = preview_article(resolved_url, title)
        body = (preview.get("body") or "").strip()
        if body:
            # A short extract is still real publisher text: preserve it and mark
            # it as potentially incomplete instead of replacing it with RSS text.
            return {
                "body": body[:30000],
                "full_article": len(body) >= 450,
                "url": preview.get("url") or resolved_url,
                "categories": preview["categories"],
                "related_markets": preview["related_markets"],
                "matched_terms": preview["matched_terms"],
            }
    except Exception as exc:
        print("Safe article extraction failed; using RSS fallback:", exc)
    c = classify_news(title, fallback)
    return {
        "body": str(fallback or "")[:3000],
        "full_article": False,
        "url": resolved_url,
        "categories": list(c.categories),
        "related_markets": list(c.related_markets),
        "matched_terms": list(c.matched_terms),
    }
