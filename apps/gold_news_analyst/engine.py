from __future__ import annotations
from datetime import datetime, timezone
from hashlib import sha256

DOLLAR_UP = ("dollar rises", "dollar strengthens", "dxy rises", "higher treasury yields", "yields rise", "bond yields rise", "hawkish", "rate hike", "raises rates")
DOLLAR_DOWN = ("dollar falls", "dollar weakens", "dxy falls", "yields fall", "bond yields fall", "dovish", "rate cut", "cuts rates")
GEO_RISK = ("war", "airstrike", "military strike", "missile", "invasion", "escalation", "sanctions", "ceasefire", "geopolitical")
OIL = ("oil", "crude", "opec", "strait of hormuz", "energy supply")
INFLATION = ("cpi", "inflation", "pce", "producer prices")


def parse_time(value):
    if not value: return None
    try:
        dt = datetime.fromisoformat(str(value).replace("Z", "+00:00"))
        return dt.replace(tzinfo=timezone.utc) if dt.tzinfo is None else dt.astimezone(timezone.utc)
    except (ValueError, TypeError): return None


def fingerprint(item):
    raw = "|".join(str(item.get(k, "")) for k in ("link", "title", "published_utc"))
    return sha256(raw.encode("utf-8")).hexdigest()


def analyse(item):
    text = (str(item.get("title", "")) + " " + str(item.get("summary", ""))).lower()
    up = any(x in text for x in DOLLAR_UP)
    down = any(x in text for x in DOLLAR_DOWN)
    geo = any(x in text for x in GEO_RISK)
    oil = any(x in text for x in OIL)
    inflation = any(x in text for x in INFLATION)
    drivers = []
    if up and not down:
        drivers.append("نشانه تقویت دلار/بازده؛ معمولاً فشار بر طلا")
    elif down and not up:
        drivers.append("نشانه تضعیف دلار/بازده؛ معمولاً حمایت از طلا")
    elif up and down:
        drivers.append("سیگنال‌های متضاد دلار/بازده؛ جهت اثر روشن نیست")
    if geo: drivers.append("افزایش ریسک ژئوپلیتیک می‌تواند تقاضای پناهگاه امن را بالا ببرد؛ شدت اثر وابسته به واکنش بازار است")
    if oil: drivers.append("نفت/عرضه انرژی ممکن است انتظارات تورمی و ریسک را تغییر دهد؛ اثر بر طلا دوطرفه است")
    if inflation: drivers.append("خبر تورمی به‌تنهایی جهت طلا را تعیین نمی‌کند؛ انتظارات نرخ بهره و بازده واقعی مهم‌اند")
    if not drivers: drivers.append("از متن آرشیوشده مسیر اثر قابل اتکایی استخراج نشد؛ داده تکمیلی لازم است")

    bullish = (down and not up) or geo
    bearish = up and not down and not geo
    if bullish and bearish: direction = "متعارض / خنثی"
    elif bullish: direction = "تمایل حمایتی برای طلا"
    elif bearish: direction = "تمایل فشاری برای طلا"
    else: direction = "خنثی؛ جهت قطعی مشخص نیست"

    signals = sum((up or down, geo, oil, inflation))
    confidence = "پایین" if signals <= 1 or (up and down) else "متوسط"
    return {
      "direction": direction, "drivers": drivers, "confidence": confidence,
      "bull": "تداوم ضعف دلار/بازده یا تشدید تقاضای پناهگاه امن؛ نیازمند تأیید در داده بازار.",
      "bear": "تقویت دلار/بازده و کاهش تقاضای پناهگاه امن؛ نیازمند تأیید در داده بازار.",
      "neutral": "خبر در قیمت جذب شود یا داده‌های دلار، بازده و ریسک سیگنال متناقض بدهند.",
      "invalidate": "با تغییر واکنش دلار و بازده واقعی، کاهش/افزایش تنش یا انتشار داده معتبر جدید، ارزیابی باید بازبینی شود.",
      "horizon": "کوتاه‌مدت تا میان‌مدت؛ زمان دقیق از متن خبر به‌تنهایی قابل تعیین نیست.",
    }


def eligible(item, now, max_age_hours=24, min_relevance=25):
    stamp = parse_time(item.get("published_utc"))
    if stamp is None or stamp > now or (now - stamp).total_seconds() > max_age_hours * 3600:
        return False
    try: score = int(item.get("relevance_score", 0))
    except (ValueError, TypeError): score = 0
    return score >= min_relevance and bool(item.get("title"))
