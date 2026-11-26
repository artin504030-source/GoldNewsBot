from __future__ import annotations

from datetime import datetime, timezone
from hashlib import sha256

# Event labels are selected from the headline/summary and the article lead.
# Mentions buried deep in an article are not enough to make it a main event.
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
HAWKISH = ("rate hike", "raise rates", "raising rates", "raises rates", "higher for longer", "hawkish", "tightening", "increase interest rates", "rising interest rate expectations", "higher interest rate expectations", "rate expectations rise")
DOVISH = ("rate cut", "cut rates", "cuts rates", "lower rates", "dovish", "easing", "reduce interest rates", "rate cuts expected", "rate expectations fall")
ABOVE = ("above expectations", "higher than expected", "hotter than expected", "beats forecast", "beat expectations", "stronger than expected", "surprise increase")
BELOW = ("below expectations", "lower than expected", "cooler than expected", "misses forecast", "weaker than expected", "surprise decline")
RISK_OFF = ("war", "military strike", "airstrike", "missile", "invasion", "escalation", "banking crisis", "financial crisis", "default", "recession", "systemic risk", "geopolitical", "mine strike", "strikes on tankers", "tanker attack", "tanker attacks")
RISK_EASING = ("ceasefire", "peace deal", "peace agreement", "de-escalation", "tensions ease", "sanctions lifted")
SUPPLY_SHOCK = ("supply disruption", "supply shock", "oil embargo", "strait of hormuz", "pipeline disruption", "shipping attack", "production cut")
COMPANY_TITLE_TERMS = ("appointed", "appoints", "named as ceo", "new ceo", "chief executive", "earnings", "quarterly results", "shares", "merger", "acquisition", "dividend", "company results")
GOLD_UP = ("gold rally", "gold rallies", "gold rises", "gold rose", "gold gains", "gold surges", "precious metals rally", "bullion rises")
GOLD_DOWN = ("gold falls", "gold fell", "gold drops", "gold slipped", "gold slides", "gold declines", "gold sell-off", "gold under pressure", "precious metals sell-off")

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

def _signal(headline, lead, terms):
    return bool(_contains(headline, terms)) or len(_contains(lead, terms)) >= 2

def _event_labels(headline, lead):
    labels = []
    for label, terms in EVENTS.items():
        if _signal(headline, lead, terms):
            labels.append(label)
    return labels

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

def _scenarios(labels, company):
    if company:
        return (
            "خبر شرکتی به‌تنهایی محرک مستقیمی برای XAUUSD نیست؛ فقط اگر بر ریسک عمومی یا جریان فلزات اثر قابل‌اندازه‌گیری بگذارد، سناریوی صعودی مطرح می‌شود.",
            "اگر خبر فقط به تغییر مدیریت/عملکرد یک شرکت محدود بماند، نباید از آن سیگنال نزولی برای طلای جهانی ساخت.",
            "سناریوی پایه خنثی است؛ برای اثرگذاری بر طلا باید واکنش گسترده‌تر بازار یا تغییر عرضه/تقاضای فلزات دیده شود.",
        )
    if "تعرفه و تجارت" in labels:
        return (
            "اگر تشدید تعرفه‌ها ریسک‌گریزی را بالا ببرد و بازده واقعی/دلار جهش نکند، تقاضای پناهگاه امن می‌تواند به طلا کمک کند.",
            "اگر بازار تعرفه‌ها را تورم‌زا بداند و دلار/بازده واقعی بالا بروند، فشار نرخ بهره می‌تواند بر اثر پناهگاه امن غلبه کند.",
            "اگر خبر از قبل قیمت‌گذاری شده باشد یا بازار بین تورم و رکود مردد بماند، واکنش طلا می‌تواند دوطرفه باشد.",
        )
    if "ژئوپلیتیک و امنیت" in labels or "نفت و انرژی" in labels:
        return (
            "اگر تنش/اختلال عرضه تشدید شود و دلار/بازده واقعی افزایش شدیدی نداشته باشند، تقاضای امن و ریسک انرژی می‌تواند از طلا حمایت کند.",
            "اگر دلار و بازده واقعی به‌عنوان پناهگاه/واکنش نرخ بهره قوی‌تر شوند یا تنش فروکش کند، طلا ممکن است تحت فشار قرار گیرد.",
            "اگر خبر تأیید نشود، دامنه تنش محدود بماند یا سیگنال‌های دلار و بازده متضاد باشند، جهت طلا نامشخص می‌ماند.",
        )
    if "تورم و شاخص قیمت" in labels or "سیاست پولی و نرخ بهره" in labels:
        return (
            "اگر تورم/سیاست پولی نرم‌تر از انتظار باشد و بازده واقعی و دلار پایین بیایند، هزینه فرصت طلا کاهش می‌یابد.",
            "اگر تورم داغ‌تر یا بانک مرکزی انقباضی‌تر از انتظار باشد و بازده واقعی/دلار بالا بروند، طلا می‌تواند تحت فشار قرار گیرد.",
            "اگر داده مطابق انتظار باشد یا واکنش دلار و بازده با خود خبر هم‌جهت نباشد، احتمال جذب خبر در قیمت و نوسان دوطرفه وجود دارد.",
        )
    if "اشتغال و دستمزد" in labels or "رشد اقتصادی" in labels:
        return (
            "اگر ضعف رشد/اشتغال انتظارات کاهش نرخ و افت بازده واقعی را تقویت کند، طلا می‌تواند حمایت شود.",
            "اگر داده‌های قوی‌تر انتظارات نرخ بهره را بالا ببرند و دلار/بازده تقویت شوند، طلا ممکن است تحت فشار قرار گیرد.",
            "اگر نگرانی رکود و انتظارات نرخ بهره در دو جهت مخالف حرکت کنند، اثر خالص بر طلا نامشخص است.",
        )
    if "بانک‌ها و بازار مالی" in labels:
        return (
            "اگر خبر به نگرانی نقدینگی/ریسک سیستمی منجر شود و تقاضای پناهگاه امن بالا برود، طلا می‌تواند حمایت شود.",
            "اگر تنش مالی فروکش کند و دلار/بازده واقعی بالا بروند، بخشی از تقاضای امن طلا ممکن است کاهش یابد.",
            "تا زمانی که اثر خبر بر نقدینگی، اوراق و دلار روشن نشود، نتیجه خنثی است.",
        )
    return (
        "اگر ضعف دلار/بازده یا افزایش تقاضای پناهگاه امن تأیید شود، طلا می‌تواند حمایت شود.",
        "اگر دلار/بازده واقعی تقویت شوند و تقاضای امن کاهش یابد، طلا می‌تواند تحت فشار قرار گیرد.",
        "اگر خبر از قبل قیمت‌گذاری شده باشد یا داده‌های بازار متناقض باشند، واکنش طلا می‌تواند محدود/نوسانی باشد.",
    )

def analyse(item, article_text="", market_snapshot=None):
    title = str(item.get("title", ""))
    summary = str(item.get("summary", ""))
    body = str(article_text or "")
    headline = (title + " " + summary).lower()
    lead = body[:1800].lower()
    combined = headline + " " + lead
    labels = _event_labels(headline, lead)
    hawkish = _signal(headline, lead, HAWKISH)
    dovish = _signal(headline, lead, DOVISH)
    above = _signal(headline, lead, ABOVE)
    below = _signal(headline, lead, BELOW)
    risk_off = _signal(headline, lead, RISK_OFF)
    risk_easing = _signal(headline, lead, RISK_EASING)
    supply_shock = _signal(headline, lead, SUPPLY_SHOCK)
    inflation = "تورم و شاخص قیمت" in labels
    monetary = "سیاست پولی و نرخ بهره" in labels
    employment = "اشتغال و دستمزد" in labels
    growth = "رشد اقتصادی" in labels
    tariffs = "تعرفه و تجارت" in labels
    energy = "نفت و انرژی" in labels
    company = bool(_contains(title.lower(), COMPANY_TITLE_TERMS)) and not any((monetary, inflation, employment, growth, tariffs, energy, risk_off))
    if company and "رویداد شرکتی" not in labels:
        labels.append("رویداد شرکتی")
    drivers = []
    if hawkish and not dovish:
        drivers.append("انتظار/لحن انقباضی نرخ بهره می‌تواند بازده واقعی و دلار را بالا ببرد و برای طلا فشار بسازد؛ واکنش بازار باید آن را تأیید کند.")
    elif dovish and not hawkish:
        drivers.append("انتظار کاهش نرخ یا سیاست انبساطی می‌تواند هزینه فرصت نگهداری طلا را کاهش دهد؛ واکنش دلار و بازده تعیین‌کننده است.")
    elif hawkish and dovish:
        drivers.append("در عنوان/ابتدای متن هم‌زمان نشانه‌های انقباضی و انبساطی وجود دارد؛ اثر خالص سیاست پولی نامشخص است.")
    if inflation:
        if above and not below:
            drivers.append("تورم بالاتر از انتظار می‌تواند انتظار نرخ‌های بالاتر را تقویت کند (فشار بالقوه بر طلا)، اما پوشش تورمی و ریسک بازار ممکن است اثر را خنثی کند.")
        elif below and not above:
            drivers.append("تورم پایین‌تر از انتظار می‌تواند انتظارات کاهش نرخ را تقویت کند (حمایت بالقوه از طلا)، مشروط به تأیید دلار و بازده.")
        else:
            drivers.append("خبر تورمی شناسایی شد، اما مقایسه معتبر با پیش‌بینی بازار در عنوان/ابتدای متن پیدا نشد؛ خود عدد تورم به‌تنهایی جهت طلا را تعیین نمی‌کند.")
    if employment:
        if above and not below:
            drivers.append("اشتغال/دستمزد قوی‌تر از انتظار می‌تواند فضای کاهش نرخ را محدود کند و از مسیر دلار/بازده بر طلا فشار بیاورد.")
        elif below and not above:
            drivers.append("ضعف اشتغال می‌تواند انتظار کاهش نرخ را بالا ببرد و به طلا کمک کند؛ اگر نگرانی رکود غالب شود، تقاضای پناهگاه امن نیز مطرح است.")
        else:
            drivers.append("خبر اشتغال شناسایی شد، اما بدون رقم واقعی و پیش‌بینی بازار، جهت اثر روشن نیست.")
    if growth:
        drivers.append("داده رشد اقتصادی از دو مسیر اثر می‌گذارد: انتظارات نرخ بهره و ریسک رکود/تقاضای پناهگاه امن؛ این دو مسیر می‌توانند متضاد باشند.")
    if tariffs:
        drivers.append("تعرفه‌ها می‌توانند هزینه واردات و تورم را بالا ببرند، رشد و تجارت را تضعیف کنند و ریسک‌گریزی بسازند؛ اثر بر طلا دوطرفه و وابسته به دلار/بازده است.")
    if risk_off and not risk_easing:
        drivers.append("افزایش ریسک ژئوپلیتیک/مالی می‌تواند تقاضای پناهگاه امن را تقویت کند؛ دلار نیز ممکن است هم‌زمان رقیب طلا باشد.")
    if risk_easing:
        drivers.append("کاهش تنش می‌تواند بخشی از تقاضای پناهگاه امن طلا را کم کند؛ اثر نهایی به دلار و نرخ‌های واقعی بستگی دارد.")
    if energy or supply_shock:
        drivers.append("اختلال عرضه انرژی می‌تواند نفت و انتظارات تورمی را بالا ببرد، اما اگر بازده واقعی و دلار جهش کنند ممکن است برای طلا منفی شود.")
    if "بانک‌ها و بازار مالی" in labels:
        drivers.append("خبر بانکی/اوراق/اعتبار از مسیر نقدینگی، ریسک سیستمی و بازده اوراق بر طلا اثر می‌گذارد؛ جهت بدون جزئیات و واکنش بازار قطعی نیست.")
    if "طلا و فلزات گران‌بها" in labels and not company:
        drivers.append("خبر مستقیم بازار طلا/فلزات باید با عرضه، تقاضا، جریان صندوق‌ها و خرید بانک‌های مرکزی سنجیده شود؛ هر خبر شرکتی در صنعت طلا الزاماً محرک XAUUSD نیست.")
    if company:
        drivers.append("این خبر عمدتاً شرکتی/مدیریتی است؛ ارتباط مستقیم آن با XAUUSD ضعیف است مگر اثر مشخصی بر عرضه، تقاضا یا ریسک بازار نشان داده شود.")
    gold_up = bool(_contains(headline, GOLD_UP))
    gold_down = bool(_contains(headline, GOLD_DOWN))
    if gold_up and not gold_down:
        drivers.append("تیتر گزارش از رشد اخیر قیمت طلا/فلزات می‌گوید؛ این حرکت گذشته است و به‌تنهایی پیش‌بینی ادامه رشد نیست.")
    elif gold_down and not gold_up:
        drivers.append("تیتر گزارش از افت اخیر قیمت طلا می‌گوید؛ این حرکت گذشته است و به‌تنهایی پیش‌بینی ادامه افت نیست.")
    if not drivers:
        drivers.append("از عنوان و ابتدای متن محرک مشخص و قابل دفاعی برای طلا استخراج نشد؛ جهت‌سازی انجام نمی‌شود.")

    market_lines, market_warnings = _market_context(market_snapshot)
    m = market_snapshot or {}
    dxy = m.get("DXY", {})
    real_yield = m.get("US10Y_REAL", {})
    nominal_yield = m.get("US10Y", {})
    yield_data = real_yield if real_yield.get("status") == "DAILY" else nominal_yield
    dollar_up = dxy.get("change_pct") is not None and float(dxy["change_pct"]) > 0.15
    dollar_down = dxy.get("change_pct") is not None and float(dxy["change_pct"]) < -0.15
    yield_up = yield_data.get("change_pct") is not None and float(yield_data["change_pct"]) > 0.5
    yield_down = yield_data.get("change_pct") is not None and float(yield_data["change_pct"]) < -0.5
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

    bullish_points = int(dovish and not hawkish) + int(below and inflation) + int(risk_off and not risk_easing) + int(market_support)
    bearish_points = int(hawkish and not dovish) + int(above and inflation) + int(market_headwind) + int(risk_easing)
    if company:
        direction = "خنثی؛ خبر شرکتی و فاقد محرک مستقیم طلا"
    elif bullish_points >= 2 and bearish_points == 0:
        direction = "تمایل حمایتی؛ نیازمند تأیید بیشتر"
    elif bearish_points >= 2 and bullish_points == 0:
        direction = "تمایل فشاری؛ نیازمند تأیید بیشتر"
    elif bullish_points and bearish_points:
        direction = "سیگنال‌های متعارض؛ خنثی"
    else:
        direction = "خنثی؛ شواهد کافی برای جهت‌دهی وجود ندارد"

    source_text_ok = len(body.strip()) >= 300
    macro_events = any(x in labels for x in ("سیاست پولی و نرخ بهره", "تورم و شاخص قیمت", "اشتغال و دستمزد", "رشد اقتصادی", "تعرفه و تجارت", "ژئوپلیتیک و امنیت", "نفت و انرژی", "بانک‌ها و بازار مالی"))
    confidence = "متوسط" if source_text_ok and macro_events and (market_headwind or market_support or bullish_points + bearish_points >= 2) else "پایین"
    if not source_text_ok: confidence = "پایین؛ متن کامل خبر در دسترس نیست"
    if company or (hawkish and dovish): confidence = "پایین"
    bull, bear, neutral = _scenarios(labels, company)
    return {
        "direction": direction, "drivers": drivers, "confidence": confidence,
        "events": labels, "market_lines": market_lines, "market_warnings": market_warnings,
        "bull": bull, "bear": bear, "neutral": neutral,
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
