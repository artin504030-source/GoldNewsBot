"""Summarize archived news themes over a configurable lookback window."""
from collections import Counter
from datetime import datetime, timedelta, timezone

TOPIC_TERMS = {
    "طلا": ("gold", "bullion", "xau", "precious metal"),
    "دلار و نرخ بهره": ("fed", "fomc", "dollar", "dxy", "interest rate", "yield", "treasury"),
    "تورم و داده‌های اقتصادی": ("cpi", "inflation", "pce", "payroll", "nfp", "unemployment", "gdp", "pmi"),
    "ژئوپلیتیک": ("war", "conflict", "sanction", "strike", "tariff", "ceasefire", "iran", "israel", "ukraine"),
    "نفت و انرژی": ("oil", "crude", "opec", "energy", "natural gas"),
    "چین و رشد جهانی": ("china", "chinese", "pboc", "global growth", "recession"),
    "سهام و ریسک بازار": ("stock", "equity", "nasdaq", "dow", "s&p", "risk-off", "risk-on", "vix"),
}

def _parse_date(item):
    raw = item.get("archived_at_utc") or item.get("published_utc") or item.get("published") or ""
    try:
        dt = datetime.fromisoformat(str(raw).replace("Z", "+00:00"))
        if dt.tzinfo is None: dt = dt.replace(tzinfo=timezone.utc)
        return dt.astimezone(timezone.utc)
    except (ValueError, TypeError):
        return None

def summarize_history(items, now=None, days=7):
    """Return topic counts, day buckets, recurrent headlines, and period comparison."""
    now = now or datetime.now(timezone.utc)
    if now.tzinfo is None: now = now.replace(tzinfo=timezone.utc)
    now = now.astimezone(timezone.utc)
    cutoff = now - timedelta(days=max(1, int(days)))
    prior_cutoff = cutoff - timedelta(days=max(1, int(days)))
    current, previous = [], []
    for item in items or []:
        stamp = _parse_date(item)
        if not stamp: continue
        if cutoff <= stamp <= now: current.append(item)
        elif prior_cutoff <= stamp < cutoff: previous.append(item)
    def counts(rows):
        c=Counter();
        for item in rows:
            text=(str(item.get("title", ""))+" "+str(item.get("summary", ""))).lower()
            for topic, terms in TOPIC_TERMS.items():
                if any(term in text for term in terms): c[topic]+=1
        return c
    curr, prev=counts(current), counts(previous)
    daily=Counter()
    for item in current:
        stamp=_parse_date(item)
        if stamp: daily[stamp.strftime("%Y-%m-%d")]+=1
    trend=[]
    for topic,count in curr.most_common():
        old=prev.get(topic,0)
        change=count-old
        status="افزایش" if change>0 else "کاهش" if change<0 else "ثابت"
        trend.append({"topic":topic,"current_count":count,"previous_count":old,"change":change,"trend":status})
    recurrent=Counter(str(x.get("title", "")).strip() for x in current if x.get("title"))
    repeat_titles=[{"title":title,"count":count} for title,count in recurrent.most_common(5) if count>1]
    return {"window_days":max(1,int(days)),"current_count":len(current),"previous_count":len(previous),"topic_trends":trend,"daily_counts":dict(sorted(daily.items())),"repeated_headlines":repeat_titles,"note":"تعداد خبرها نماینده میزان پوشش خبری است، نه شدت یا جهت حرکت قیمت."}

def format_history_summary(summary):
    days=summary.get("window_days",7)
    lines=[f"🧠 حافظه خبری و روند موضوعات | {days} روز اخیر",f"خبرهای بازه: {summary.get('current_count',0)} | بازه قبلی: {summary.get('previous_count',0)}"]
    trends=summary.get("topic_trends",[])
    if trends:
        lines.append("📈 تغییر تکرار موضوعات نسبت به بازه قبلی:")
        for t in trends[:5]: lines.append(f"• {t['topic']}: {t['current_count']} خبر (قبلی {t['previous_count']}; {t['trend']})")
    daily=summary.get("daily_counts",{})
    if daily: lines.append("📅 تعداد خبر روزانه: "+" | ".join(f"{d}: {n}" for d,n in list(daily.items())[-7:]))
    repeats=summary.get("repeated_headlines",[])
    if repeats:
        lines.append("🔁 تیترهای تکرارشونده:")
        for r in repeats: lines.append(f"• {r['title']} ({r['count']} بار)")
    lines.append("ℹ️ مقایسه بر اساس آرشیو موجود؛ تعداد خبر، شاخص شدت بازار نیست.")
    return "\n".join(lines)
