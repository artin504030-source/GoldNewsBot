"""Side-effect-free public article preview with structured-data extraction."""
from html.parser import HTMLParser
import json
import re

from .safe_fetch import fetch_public_page
from .classification import classify_news


class _ArticleParser(HTMLParser):
    BLOCKED = {"script", "style", "noscript", "nav", "footer", "header", "aside", "form", "svg", "button"}
    ARTICLE_HINTS = ("article", "story", "content", "post", "entry", "body")

    def __init__(self):
        super().__init__(convert_charrefs=True)
        self.stack = []
        self.blocked_depth = 0
        self.article_depth = 0
        self.paragraph_depth = 0
        self.current = []
        self.paragraphs = []
        self.fallback_paragraphs = []
        self.general_parts = []
        self.jsonld_depth = 0
        self.jsonld_parts = []
        self.jsonld_bodies = []
        self.meta_descriptions = []

    def handle_starttag(self, tag, attrs):
        attrs = dict(attrs)
        classes = (attrs.get("class", "") + " " + attrs.get("id", "")).lower()
        if tag == "meta":
            key = (attrs.get("property") or attrs.get("name") or "").lower()
            if key in {"og:description", "description", "twitter:description"} and attrs.get("content"):
                self.meta_descriptions.append(attrs["content"].strip())
        if tag == "script" and "ld+json" in attrs.get("type", "").lower():
            self.jsonld_depth += 1
            self.jsonld_parts = []
            return
        if tag in self.BLOCKED:
            self.blocked_depth += 1
        is_article = tag in {"article", "main"} or any(h in classes for h in self.ARTICLE_HINTS)
        if is_article and not self.blocked_depth:
            self.article_depth += 1
        if tag == "p" and not self.blocked_depth:
            self.paragraph_depth += 1
            self.current = []
        self.stack.append((tag, is_article))

    def handle_endtag(self, tag):
        if tag == "script" and self.jsonld_depth:
            raw = "".join(self.jsonld_parts).strip()
            if raw:
                try:
                    self.jsonld_bodies.extend(_article_bodies(json.loads(raw)))
                except (ValueError, TypeError):
                    pass
            self.jsonld_depth = 0
            self.jsonld_parts = []
            return
        if tag == "p" and self.paragraph_depth:
            value = re.sub(r"\s+", " ", " ".join(self.current)).strip()
            if value:
                self.fallback_paragraphs.append(value)
                if self.article_depth:
                    self.paragraphs.append(value)
            self.current = []
            self.paragraph_depth -= 1
        for i in range(len(self.stack) - 1, -1, -1):
            stack_tag, is_article = self.stack[i]
            if stack_tag == tag:
                removed = self.stack[i:]
                self.stack = self.stack[:i]
                for _, was_article in reversed(removed):
                    if was_article and self.article_depth:
                        self.article_depth -= 1
                if tag in self.BLOCKED and self.blocked_depth:
                    self.blocked_depth -= 1
                break

    def handle_data(self, data):
        if self.jsonld_depth:
            self.jsonld_parts.append(data)
        elif not self.blocked_depth and data.strip():
            self.general_parts.append(data.strip())
            if self.paragraph_depth:
                self.current.append(data.strip())


def _article_bodies(value):
    bodies = []
    if isinstance(value, dict):
        body = value.get("articleBody")
        if isinstance(body, str) and body.strip():
            bodies.append(body.strip())
        for child in value.values():
            bodies.extend(_article_bodies(child))
    elif isinstance(value, list):
        for child in value:
            bodies.extend(_article_bodies(child))
    return bodies


def extract_text(html, *, max_chars=30000, min_chars=80):
    parser = _ArticleParser()
    parser.feed(html or "")
    # Prefer publisher-supplied schema.org articleBody, then article/main paragraphs.
    candidates = parser.jsonld_bodies or parser.paragraphs or parser.fallback_paragraphs
    if not candidates and parser.general_parts:
        candidates = [" ".join(parser.general_parts)]
    text = "\n\n".join(dict.fromkeys(re.sub(r"\s+", " ", x).strip() for x in candidates if x.strip()))
    if len(text) < min_chars and parser.meta_descriptions:
        text = "\n\n".join(parser.meta_descriptions)
    return text[:max_chars] if len(text) >= min_chars else ""


def preview_article(url, title, *, session=None, resolver=None, min_chars=80):
    kw = {"session": session} if session is not None else {}
    if resolver is not None:
        kw["resolver"] = resolver
    html, final_url = fetch_public_page(url, **kw)
    body = extract_text(html, min_chars=min_chars)
    c = classify_news(title, body)
    return {"title": title, "url": final_url, "body": body,
            "category": c.primary, "categories": list(c.categories),
            "related_markets": list(c.related_markets),
            "matched_terms": list(c.matched_terms), "telegram_sent": False}
