"""Adapter from the safe preview pipeline to the existing Gold News Bot."""
from .pipeline_preview import preview_article
from .classification import classify_news
def fetch_and_classify_article(url,title,fallback=""):
    try:
        preview=preview_article(url,title)
        body=(preview.get("body") or "").strip()
        if len(body)>=450:
            return {"body":body[:12000],"full_article":True,"categories":preview["categories"],"related_markets":preview["related_markets"],"matched_terms":preview["matched_terms"]}
    except Exception as exc:
        print("Safe article extraction failed; using RSS fallback:",exc)
    c=classify_news(title,fallback)
    return {"body":str(fallback or "")[:3000],"full_article":False,"categories":list(c.categories),"related_markets":list(c.related_markets),"matched_terms":list(c.matched_terms)}
