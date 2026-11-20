import re

# Lightweight, transparent rule-based cross-market news analysis. No trade signals.
SYMBOL_KEYWORDS = {
    "XAUUSD": ("gold", "bullion", "precious metal"), "XAGUSD": ("silver", "precious metals"),
    "EURUSD": ("euro", "ecb", "eurozone", "european central bank"), "GBPUSD": ("pound", "sterling", "bank of england", "boe", "uk inflation", "britain"),
    "USDJPY": ("yen", "japan", "bank of japan", "boj"), "USDCHF": ("swiss franc", "switzerland", "snb"),
    "USDCAD": ("canada", "canadian dollar", "bank of canada", "boc"), "AUDUSD": ("australia", "australian dollar", "rba"),
    "NZDUSD": ("new zealand", "kiwi", "rbnz"), "DXY": ("dollar index", "dxy", "us dollar", "dollar", "federal reserve", "fed rate", "fomc", "us inflation", "u.s. inflation"),
    "US30": ("dow jones", "dow", "wall street"), "NAS100": ("nasdaq", "technology stocks", "tech shares"),
    "US500": ("s&p 500", "sp500", "s&p", "stocks", "equities"), "VIX": ("vix", "volatility index", "market volatility"),
    "GER40": ("dax", "germany", "german economy"), "UK100": ("ftse", "british stocks"), "JP225": ("nikkei", "japanese stocks"),
    "USOIL": ("wti", "crude oil", "oil prices", "opec"), "UKOIL": ("brent", "brent crude"), "NATGAS": ("natural gas", "gas prices"),
    "BTCUSD": ("bitcoin", "btc", "crypto"), "ETHUSD": ("ethereum", "eth"),
}
POSITIVE_CUES = ("rises", "rose", "increase", "increased", "higher than expected", "beat expectations", "stronger than expected", "surge", "growth accelerates", "hawkish", "rate hike")
NEGATIVE_CUES = ("falls", "fell", "decline", "decreased", "lower than expected", "miss expectations", "weaker than expected", "slump", "contraction", "dovish", "rate cut")


def analyze_market_news(title, summary=""):
    text = (title + " " + summary).lower()
    matches = []
    for symbol, words in SYMBOL_KEYWORDS.items():
        if any(word in text for word in words):
            matches.append(symbol)
    positive = any(cue in text for cue in POSITIVE_CUES)
    negative = any(cue in text for cue in NEGATIVE_CUES)
    if positive and not negative:
        tone = "لحن/داده مثبت"
        confidence = "متوسط؛ فقط بر اساس کلمات خبر"
    elif negative and not positive:
        tone = "لحن/داده منفی"
        confidence = "متوسط؛ فقط بر اساس کلمات خبر"
    else:
        tone = "خنثی یا اثر نامشخص"
        confidence = "پایین؛ بدون جهت روشن در متن"
    if not matches:
        matches = ["ارتباط نماد مشخص نشد"]
    return {"symbols": matches, "potential_effect": tone, "confidence": confidence,
            "reason": "تحلیل خودکار مبتنی بر کلیدواژه‌ها؛ جهت اثر قطعی نیست و نیاز به بررسی متن کامل و زمینه بازار."}
