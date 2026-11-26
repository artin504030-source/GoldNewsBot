from __future__ import annotations

import re
from datetime import datetime, timezone
from hashlib import sha256

# Event recognition is deliberately multi-label: one article can affect gold
# through several channels at once. No keyword-only result is treated as a trade signal.
EVENTS = {
    "سیاست پولی و نرخ بهره": ("fed", "federal reserve", "fomc", "central bank", "interest rate", "policy rate", "rate decision", "rate hike", "rate cut", "raises rates", "raising rates", "cuts rates", "higher for longer", "hawkish", "dovish", "monetary policy", "tightening", "easing"),
    "تورم و شاخص قیمت": ("cpi", "core cpi", "pce", "core pce", "inflation", "consumer prices", "producer prices", "ppi", "price pressures", "shelter", "oer"),
    "اشتغال و دستمزد": ("nonfarm", "non-farm", "payroll", "unemployment", "jobless claims", "employment", "wages", "labor market", "labour market", "jolts"),
    "رشد اقتصادی": ("gdp", "pmi", "ism", "retail sales", "industrial production", "recession", "economic growth", "economic activity"),
    "تعرفه و تجارت": ("tariff", "tariffs", "trade war", "trade restrictions", "export ban", "import restrictions", "trade sanctions", "export controls", "trade deal"),
    "ژئوپلیتیک و امنیت": ("war", "military strike", "airstrike", "missile", "invasion", "conflict", "geopolitical", "ceasefire", "peace talks", "sanctions", "attack", "escalation", "tanker", "shipping disruption"),
    "نفت و انرژی": ("oil", "crude", "opec", "natural gas", "energy supply", "strait of hormuz", "pipeline", "oil production", "oil exports", "oil imports"),
    "بانک‌ها و بازار مالی": ("bank", "banking crisis", "liquidity", "credit", "bond auction", "treasury", "yield curve", "default", "debt ceiling", "stock market", "equities"),
    "طلا و فلزات گران‌بها": ("gold", "bullion", "precious metals", "silver", "central bank gold", "gold reserves"),
}
HAWKISH = ("rate hike", "raise rates", "raising rates", "raises rates", "higher for longer", "hawkish", "tightening", "increase interest rates")
DOVISH = ("rate cut", "cut rates", "cuts rates", "lower rates", "dovish", "easing", "reduce interest rates")
ABOVE = ("above expectations", "higher than expected", "hotter than expected", "beats forecast", "beat expectations", "stronger than expected", "surprise increase")
BELOW = ("below expectations", "lower than expected", "cooler than expected", "misses forecast", "weaker than expected", "surprise decline")
RISK_OFF = ("war", "military strike", "airstrike", "missile", "invasion", "escalation", "banking crisis", "financial crisis", "default", "recession", "systemic risk", "geopolitical")
RISK_EASING = ("ceasefire", "peace deal", "peace agreement", "de-escalation", "tensions ease", "sanctions lifted")
SUPPLY_SHOCK = ("supply disruption", "supply shock", "oil embargo", "strait of hormuz", "pipeline disruption", "shipping attack", "production cut")
COMPANY_TERMS = ("earnings", "quarterly results", "shares", "stock", "company", "merger", "acquisition", "ceo", "revenue", "profit", "dividend")

def parse_time(value):
    if not value: return None
    try:
        dt = datetime.fromisoformat(str(value).replace("Z", "+00:00"))
        return dt.replace(tzinfo=timezone.utc) if dt.tzinfo is None else dt.astimezone(timezone.utc)
    except (ValueError, TypeError): return None

def fingerprint(item):
    raw = "|".join(str(item.get(k, "")) for k in ("link", "title", "published_utc"))
    return sha256(raw.encode("utf-8")).hexdigest()

def _contains(text, terms):
    return [term for term in terms if term in text]

def _event_labels(text):
    return [label for label, terms in EVENTS.items() if any(term in text for term in terms)]

def _market_context(snapshot):
    if not snapshot: return [], ["داده بین‌بازاری در این اجرا دریافت نشد"]
    lines, warnings = [], []
    for key in ("XAUUSD", "DXY", "US10Y_REAL", "US10Y", "USOIL"):
        item = snapshot.get(key)
        if not item:
            warnings.append(f"{key}: داده در دسترس نیست")
            continue
        value = item.get("value")
        status = item.get("status", "UNKNOWN")
        age = item.get("age_minutes")
        change = item.get("change_pct")
        detail = f"{key}={value} ({status}"
        if age is not None: detail += f"، عمر داده {age} دقیقه"
        if change is not None: detail += f"، تغییر حدود ۲۴ ساعت {change}%"
        detail += ")"
        lines.append(detail)
        if status not in ("LIVE", "DELAYED", "DAILY"): warnings.append(f"{key}: وضعیت داده {status}")
    return lines, warnings

def analyse(item, article_text="", market_snapshot=None):
    title = str(item.get("title", ""))
    summary = str(item.get("summary", ""))
    body = str(article_text or "")
    combined = (title + " " + summary + " " + body).lower()
    labels = _event_labels(combined)
    hawkish = bool(_contains(combined, HAWKISH))
    dovish = bool(_contains(combined, DOVISH))
    above = bool(_contains(combined, ABOVE))
    below = bool(_contains(combined, BELOW))
    risk_off = bool(_contains(combined, RISK_OFF))
    risk_easing = bool(_contains(combined, RISK_EASING))
    supply_shock = bool(_contains(combined, SUPPLY_SHOCK))
    inflation = "تورم و شاخص قیمت" in labels
    monetary = "سیاست پولی و نرخ بهره" in labels
    employment = "اشتغال و دستمزد" in labels
    growth = "رشد اقتصادی" in labels
    tariffs = "تعرفه و تجارت" in labels
    energy = "نفت و انرژی" in labels
    company = any(term in combined for term in COMPANY_TERMS) and not any((inflation, monetary, employment, growth, tariffs, energy, risk_off))
    drivers = []
    if hawkish and not dovish:
        drivers.append("لحن/انتظار انقباضی نرخ بهره می‌تواند بازده واقعی و دلار را بالا ببرد و برای طلا فشار ایجاد کند؛ باید با بازار تأیید شود.")
    elif dovish and not hawkish:
        drivers.append("انتظار کاهش نرخ یا سیاست انبساطی می‌تواند هزینه فرصت نگهداری طلا را کاهش دهد؛ واکنش دلار و بازده تعیین‌کننده است.")
    elif hawkish and dovish:
        drivers.append("در متن هم‌زمان نشانه‌های انقباضی و انبساطی وجود دارد؛ اثر خالص سیاست پولی نامشخص است.")
    if inflation:
        if above and not below:
            drivers.append("تورم بالاتر از انتظار می‌تواند انتظار نرخ‌های بالاتر را تقویت کند (فشار بالقوه بر طلا)، اما پوشش تورمی و ریسک بازار ممکن است اثر را خنثی کند.")
        elif below and not above:
            drivers.append("تورم پایین‌تر از انتظار می‌تواند انتظارات کاهش نرخ را تقویت کند (حمایت بالقوه از طلا)، مشروط به تأیید دلار و بازده.")
        else:
            drivers.append("خبر تورمی شناسایی شد، اما مقایسه معتبر با پیش‌بینی بازار در متن قابل استخراج نیست؛ خود عدد تورم به‌تنهایی جهت طلا را تعیین نمی‌کند.")
    if employment:
        if above and not below:
            drivers.append("اشتغال/دستمزد قوی‌تر از انتظار می‌تواند فضای کاهش نرخ را محدود کند و از مسیر دلار/بازده بر طلا فشار بیاورد.")
        elif below and not above:
            drivers.append("ضعف اشتغال می‌تواند انتظار کاهش نرخ را بالا ببرد و به طلا کمک کند؛ اگر نگرانی رکود غالب شود، تقاضای پناهگاه امن نیز مطرح است.")
        else:
            drivers.append("خبر اشتغال شناسایی شد، اما بدون رقم واقعی و پیش‌بینی بازار، جهت اثر روشن نیست.")
    if growth:
        drivers.append("داده رشد اقتصادی باید از دو مسیر جدا شود: اثر بر انتظارات نرخ بهره و اثر بر ریسک رکود/تقاضای پناهگاه امن.")
    if tariffs:
        drivers.append("تعرفه‌ها می‌توانند هزینه واردات و تورم را بالا ببرند، رشد و تجارت را تضعیف کنند و ریسک‌گریزی بسازند؛ اثر بر طلا دوطرفه و وابسته به واکنش دلار/بازده است.")
    if risk_off and not risk_easing:
        drivers.append("افزایش ریسک ژئوپلیتیک/مالی می‌تواند تقاضای پناهگاه امن را تقویت کند؛ دلار نیز ممکن است هم‌زمان رقیب طلا باشد.")
    if risk_easing:
        drivers.append("کاهش تنش می‌تواند بخشی از تقاضای پناهگاه امن طلا را کم کند؛ اثر نهایی به دلار و نرخ‌های واقعی بستگی دارد.")
    if energy or supply_shock:
        drivers.append("اختلال عرضه انرژی می‌تواند نفت و انتظارات تورمی را بالا ببرد، اما اگر بازده واقعی و دلار جهش کنند ممکن است برای طلا منفی شود.")
    if "بانک‌ها و بازار مالی" in labels:
        drivers.append("خبر بانکی/اوراق/اعتبار از مسیر نقدینگی، ریسک سیستمی و بازده اوراق بر طلا اثر می‌گذارد؛ جهت بدون جزئیات و واکنش بازار قطعی نیست.")
    if "طلا و فلزات گران‌بها" in labels:
        drivers.append("خبر مستقیم بازار طلا/فلزات باید با عرضه، تقاضا، جریان صندوق‌ها و خرید بانک‌های مرکزی سنجیده شود؛ خبر شرکتی الزاماً محرک XAUUSD نیست.")
    if company:
        drivers.append("این خبر عمدتاً شرکتی/سهامی به نظر می‌رسد؛ ارتباط مستقیم آن با XAUUSD ضعیف یا غیرمستقیم است مگر اثر روشن بر ریسک‌پذیری یا دلار نشان داده شود.")
    if not drivers:
        drivers.append("از عنوان و متن موجود محرک مشخص و قابل دفاعی برای طلا استخراج نشد؛ جهت‌سازی انجام نمی‌شود.")

    # Market observations temper the news-only hypothesis, never override missing data.
    market_lines, market_warnings = _market_context(market_snapshot)
    m = market_snapshot or {}
    dxy = m.get("DXY", {})
    real_yield = m.get("US10Y_REAL", {})
    nominal_yield = m.get("US10Y", {})
    yield_data = real_yield if real_yield.get("status") == "DAILY" else nominal_yield
    dollar_up = (dxy.get("change_pct") is not None and float(dxy["change_pct"]) > 0.15)
    dollar_down = (dxy.get("change_pct") is not None and float(dxy["change_pct"]) < -0.15)
    yield_up = (yield_data.get("change_pct") is not None and float(yield_data["change_pct"]) > 0.5)
    yield_down = (yield_data.get("change_pct") is not None and float(yield_data["change_pct"]) < -0.5)
    market_headwind = dollar_up or yield_up
    market_support = dollar_down or yield_down
    if market_headwind and market_support:
        market_reaction = "داده‌های بازار متناقض‌اند؛ واکنش خالص روشن نیست."
    elif market_headwind:
        market_reaction = "داده‌های موجود دلار/بازده را در سمت فشار بر طلا نشان می‌دهند."
    elif market_support:
        market_reaction = "داده‌های موجود دلار/بازده را در سمت حمایت از طلا نشان می‌دهند."
    else:
        market_reaction = "جهت قابل اتکای دلار/بازده از داده‌های موجود قابل تأیید نیست."
    if dollar_up or dollar_down or yield_up or yield_down:
        drivers.append(market_reaction)

    # A directional bias is issued only when more than one independent channel agrees.
    bullish_points = int(dovish and not hawkish) + int(below and inflation) + int(risk_off and not risk_easing) + int(market_support)
    bearish_points = int(hawkish and not dovish) + int(above and inflation) + int(market_headwind) + int(risk_easing)
    if bullish_points >= 2 and bearish_points == 0:
        direction = "تمایل حمایتی؛ نیازمند تأیید بیشتر"
    elif bearish_points >= 2 and bullish_points == 0:
        direction = "تمایل فشاری؛ نیازمند تأیید بیشتر"
    elif bullish_points and bearish_points:
        direction = "سیگنال‌های متعارض؛ خنثی"
    else:
        direction = "خنثی؛ شواهد کافی برای جهت‌دهی وجود ندارد"

    source_text_ok = len(body.strip()) >= 300
    confidence = "متوسط" if source_text_ok and labels and (market_headwind or market_support or (bullish_points + bearish_points >= 2)) else "پایین"
    if not source_text_ok: confidence = "پایین؛ متن کامل خبر در دسترس نیست"
    if company and not labels: confidence = "پایین"
    if hawkish and dovish: confidence = "پایین"
    scenarios = {
        "bull": "اگر دلار و بازده واقعی/اوراق تضعیف شوند یا ریسک امن‌خواهی افزایش یابد، طلا می‌تواند حمایت شود؛ شکست ساختار قیمت باید تأیید کند.",
        "bear": "اگر دلار و بازده واقعی/اوراق تقویت شوند و تقاضای پناهگاه امن کاهش یابد، طلا می‌تواند تحت فشار قرار گیرد؛ واکنش قیمت باید تأیید کند.",
        "neutral": "اگر خبر از قبل قیمت‌گذاری شده باشد یا دلار، بازده و ریسک سیگنال‌های متناقض بدهند، واکنش طلا می‌تواند محدود/نوسانی باشد.",
    }
    return {
        "direction": direction, "drivers": drivers, "confidence": confidence,
        "events": labels, "market_lines": market_lines, "market_warnings": market_warnings,
        "bull": scenarios["bull"], "bear": scenarios["bear"], "neutral": scenarios["neutral"],
        "horizon": "اثر اولیه: ساعت‌ها تا چند روز؛ اثر سیاستی/کلان: چند هفته تا چند ماه، بسته به نوع رویداد.",
        "invalidate": "با انتشار داده معتبر جدید، تغییر انتظارات نرخ بهره، چرخش دلار/بازده واقعی یا شکست ساختار قیمت، سناریو بازبینی شود.",
        "article_text_ok": source_text_ok,
    }

def eligible(item, now, max_age_hours=24, min_relevance=25):
    stamp = parse_time(item.get("published_utc"))
    if stamp is None or stamp > now or (now - stamp).total_seconds() > max_age_hours * 3600:
        return False
    try: score = int(item.get("relevance_score", 0))
    except (ValueError, TypeError): score = 0
    return score >= min_relevance and bool(item.get("title"))
