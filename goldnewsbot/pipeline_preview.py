"""Side-effect-free public article preview."""
from html.parser import HTMLParser
import re
from .safe_fetch import fetch_public_page
from .classification import classify_news
class _Text(HTMLParser):
    BLOCKED={"script","style","noscript","nav","footer","header","aside","form","svg"}
    def __init__(self): super().__init__(convert_charrefs=True); self.depth=0; self.parts=[]
    def handle_starttag(self,tag,attrs):
        if tag in self.BLOCKED:self.depth+=1
    def handle_endtag(self,tag):
        if tag in self.BLOCKED and self.depth:self.depth-=1
    def handle_data(self,data):
        if not self.depth and data.strip():self.parts.append(data.strip())
def extract_text(html,*,max_chars=30000,min_chars=80):
    p=_Text(); p.feed(html or ""); text=re.sub(r"\s+"," "," ".join(p.parts)).strip()
    return text[:max_chars] if len(text)>=min_chars else ""
def preview_article(url,title,*,session=None,resolver=None):
    kw={"session":session} if session is not None else {}
    if resolver is not None:kw["resolver"]=resolver
    html,final_url=fetch_public_page(url,**kw); body=extract_text(html); c=classify_news(title,body)
    return {"title":title,"url":final_url,"body":body,"category":c.primary,"categories":list(c.categories),"related_markets":list(c.related_markets),"matched_terms":list(c.matched_terms),"telegram_sent":False}
