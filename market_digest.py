"""Daily multi-market digest helpers; keyword coverage is contextual, not a signal."""
from cross_market_impact import analyze_cross_market_impact

MARKET_BUCKETS = {
    "gold": ("طلا و فلزات", ("gold", "bullion", "xau", "precious metal")),
    "fx": ("ارزها", ("forex", "currency", "dollar", "usd", "euro", "eur", "pound", "gbp", "yen", "jpy", "aud", "cad", "chf", "yuan", "cny", "cpi", "inflation", "nfp", "payroll", "unemployment", "employment", "gdp", "pmi")),
    "indices": ("شاخص‌ها و سهام", ("stock", "equity", "dow", "nasdaq", "s&p", "sp500", "us30", "nas100", "dax", "ftse", "nikkei", "index", "indices")),
    "energy": ("انرژی", ("oil", "crude", "opec", "natural gas", "energy")),
    "crypto": ("رمزارزها", ("bitcoin", "btc", "ethereum", "eth", "crypto")),
    "rates": ("نرخ بهره و اوراق", ("yield", "treasury", "bond", "interest rate", "fed", "fomc", "central bank", "rate decision")),
    "geopolitics": ("ژئوپلیتیک", ("war", "conflict", "sanction", "tariff", "geopolitical", "military", "strike", "ceasefire")),
    "china": ("چین", ("china", "chinese", "pboc", "yuan", "beijing")),
}

def categorize_news(item):
    text = (str(item.get("title", "")) + " " + str(item.get("summary", ""))).lower()
    categories = [key for key, (_, terms) in MARKET_BUCKETS.items() if any(term in text for term in terms)]
    impact = analyze_cross_market_impact(item.get("title", ""), item.get("summary", ""), country=item.get("country"), currency=item.get("currency"))
    return {"categories": categories, "impact": impact}

def build_multi_market_digest(news, events, generated_at):
    categorized = []
    counts = {key: 0 for key in MARKET_BUCKETS}
    for item in news:
        analyzed = categorize_news(item)
        item_copy = dict(item)
        item_copy["market_categories"] = analyzed["categories"]
        item_copy["cross_market_impact"] = analyzed["impact"]
        categorized.append(item_copy)
        for category in analyzed["categories"]:
            counts[category] += 1
    lines = ["🌐 گزارش روزانه چندبازاری | Multi-Market Digest", f"🕒 {generated_at}", "", "مرور ۲۴ ساعت اخیر؛ این گزارش تحلیل احتمالی است و سیگنال معامله نیست.", "", "📌 پوشش بازارها:"]
    for key, (label, _) in MARKET_BUCKETS.items():
        lines.append(f"• {label}: {counts[key]} خبر")
    lines.extend(["", "📰 خبرهای مهم و ارتباط بازار:"])
    ranked = sorted(categorized, key=lambda x: (int(x.get("relevance_score", 0) or 0), x.get("importance", "") == "زیاد"), reverse=True)
    for item in ranked[:8]:
        title = item.get("title", "بدون عنوان")
        tags = [MARKET_BUCKETS[k][0] for k in item.get("market_categories", [])]
        impact = item.get("cross_market_impact", {})
        symbols = impact.get("symbols", [])[:8]
        lines.extend([f"• {title}", f"  بازارها: {', '.join(tags) if tags else 'نامشخص'} | نمادهای احتمالی: {', '.join(symbols) if symbols else 'نامشخص'}", f"  ارتباط: {item.get('relevance', 'نامشخص')} | اهمیت: {item.get('importance', 'نامشخص')} | منبع: {item.get('source', 'نامشخص')}", f"  {item.get('link', '')}"])
    if not categorized:
        lines.append("در بازه اخیر خبر آرشیوشده‌ای در دسترس نیست.")
    lines.extend(["", "📅 رویدادهای اقتصادی پیش‌رو (از فید):"])
    for event in events[:12]:
        symbols = event.get("related_symbols", [])[:6]
        lines.append(f"• {event.get('country','')} ({event.get('currency','نامشخص')}) | {event.get('title','')} | {event.get('date','')} {event.get('time','')} (منطقه زمانی نامشخص) | اهمیت: {event.get('impact_level', event.get('impact','نامشخص'))} | Forecast: {event.get('forecast') or '—'} | Previous: {event.get('previous') or '—'} | نمادها: {', '.join(symbols) if symbols else '—'}")
    if not events:
        lines.append("رویداد اقتصادی دریافت نشد.")
    lines.append("")
    lines.append("ℹ️ ارتباط‌ها و دسته‌بندی‌ها خودکار و مبتنی بر کلیدواژه‌اند؛ تأیید انسانی و بررسی منبع اصلی ضروری است.")
    return {"message": "\n".join(lines)[:3900], "news": categorized[:30], "market_counts": counts, "calendar_events": events[:12]}
