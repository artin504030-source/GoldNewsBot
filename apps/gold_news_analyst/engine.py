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
    """Match complete English words/phrases rather than incidental substrings."""
    import re
    haystack = str(text or "").lower()
    matches = []
    for term in terms:
        needle = str(term).lower().strip()
        if needle and re.search(r"(?<![a-z0-9])" + re.escape(needle) + r"(?![a-z0-9])", haystack):
            matches.append(term)
    return matches

def _signal(headline, lead, terms):
    return bool(_contains(headline, terms)) or len(_contains(lead, terms)) >= 2

def _event_labels(headline, lead):
    labels = []
    for label, terms in EVENTS.items():
        if _signal(headline, lead, terms):
            labels.append(label)
    return labels

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


# Exact tradable universe from Gold Prices Bot (16 instruments).
SYMBOL_UNIVERSE = (
    "XAUUSD", "XAGUSD", "XPTUSD", "XPDUSD",
    "EURUSD", "GBPUSD", "USDJPY", "AUDUSD", "USDCAD",
    "US30", "USTEC", "US500", "DE30",
    "USOIL", "UKOIL", "XNGUSD",
)
FX_PAIRS = {
    "EURUSD": ("EUR", "USD"), "GBPUSD": ("GBP", "USD"),
    "USDJPY": ("USD", "JPY"), "AUDUSD": ("AUD", "USD"),
    "USDCAD": ("USD", "CAD"),
}
CURRENCY_TERMS = {
    "USD": ("united states", "u.s.", "us ", "american", "federal reserve", "fed ", "fomc", "treasury", "dollar"),
    "EUR": ("eurozone", "euro area", "european central bank", "ecb", "euro ", "germany", "german"),
    "GBP": ("united kingdom", "britain", "british", "bank of england", "boe", "sterling", "pound"),
    "JPY": ("japan", "bank of japan", "boj", "yen"),
    "AUD": ("australia", "reserve bank of australia", "rba", "australian dollar"),
    "CAD": ("canada", "bank of canada", "boc", "canadian dollar"),
}

def _symbol_impacts(text, labels, hawkish, dovish, above, below, risk_off, risk_easing, supply_shock, company):
    """Classify the 16 instruments in Gold Prices Bot using news transmission channels."""
    currency_bias = {}
    mentioned = {ccy for ccy, terms in CURRENCY_TERMS.items() if any(term in text for term in terms)}
    macro_labels = {"سیاست پولی و نرخ بهره", "تورم و شاخص قیمت", "اشتغال و دستمزد", "رشد اقتصادی"}
    if labels and set(labels) & macro_labels and not mentioned:
        mentioned.add("USD")
    positive_surprise = above and bool(set(labels) & {"تورم و شاخص قیمت", "اشتغال و دستمزد", "رشد اقتصادی"})
    negative_surprise = below and bool(set(labels) & {"تورم و شاخص قیمت", "اشتغال و دستمزد", "رشد اقتصادی"})
    if hawkish or positive_surprise:
        bias = 1
    elif dovish or negative_surprise:
        bias = -1
    else:
        bias = 0
    for ccy in mentioned:
        currency_bias[ccy] = bias
    if risk_off and not risk_easing:
        for ccy, value in (("USD", 1), ("JPY", 1), ("AUD", -1)):
            currency_bias[ccy] = currency_bias.get(ccy, 0) + value
    if risk_easing:
        for ccy, value in (("USD", -1), ("JPY", -1), ("AUD", 1)):
            currency_bias[ccy] = currency_bias.get(ccy, 0) + value

    impacts = []
    def add(symbol, score, reason):
        if score > 0:
            label = "صعودی بالقوه"
        elif score < 0:
            label = "نزولی بالقوه"
        else:
            label = "خنثی/نامشخص"
        impacts.append({"symbol": symbol, "impact": label, "reason": reason})

    for symbol, (base, quote) in FX_PAIRS.items():
        if base in currency_bias or quote in currency_bias:
            score = currency_bias.get(base, 0) - currency_bias.get(quote, 0)
            add(symbol, score, f"اثر نسبی خبر بر {base} در برابر {quote}")

    macro_gold = bool(set(labels) & (macro_labels | {
        "تعرفه و تجارت", "ژئوپلیتیک و امنیت", "نفت و انرژی", "بانک‌ها و بازار مالی", "طلا و فلزات گران‌بها"
    }))
    if macro_gold and not company:
        gold_score = 0
        if risk_off and not risk_easing: gold_score += 1
        if risk_easing: gold_score -= 1
        if dovish and not hawkish: gold_score += 1
        if hawkish and not dovish: gold_score -= 1
        if positive_surprise and not dovish: gold_score -= 1
        if negative_surprise and not hawkish: gold_score += 1
        add("XAUUSD", gold_score, "کانال دلار، نرخ بهره و تقاضای پناهگاه امن")
        silver_score = gold_score + (1 if "رشد اقتصادی" in labels and positive_surprise else 0)
        add("XAGUSD", silver_score, "کانال فلزات گران‌بها و تقاضای صنعتی")
        add("XPTUSD", gold_score + (1 if "رشد اقتصادی" in labels and positive_surprise else 0),
            "تقاضای صنعتی و شرایط عمومی فلزات گران‌بها")
        add("XPDUSD", gold_score + (1 if "رشد اقتصادی" in labels and positive_surprise else 0),
            "تقاضای صنعتی و شرایط عرضه فلزات گران‌بها")

    energy_terms = ("oil", "crude", "opec", "natural gas", "lng", "gas pipeline", "energy supply",
                    "strait of hormuz", "pipeline", "tanker", "shipping disruption")
    if "نفت و انرژی" in labels or supply_shock:
        energy_score = 1 if supply_shock or (risk_off and not risk_easing) else -1 if risk_easing else 0
        add("USOIL", energy_score, "ریسک عرضه و تقاضای نفت خام WTI")
        add("UKOIL", energy_score, "ریسک عرضه و تقاضای نفت خام برنت")
        gas_score = energy_score if any(term in text for term in ("natural gas", "lng", "gas pipeline", "gas supply")) else 0
        add("XNGUSD", gas_score, "خبر عرضه/تقاضای گاز طبیعی؛ اثر مستقیم فقط در صورت ارتباط با گاز")

    index_relevant = bool(set(labels) & (macro_labels | {"ژئوپلیتیک و امنیت", "بانک‌ها و بازار مالی", "نفت و انرژی", "تعرفه و تجارت"}))
    if index_relevant:
        index_score = -1 if risk_off and not risk_easing else 1 if risk_easing else -1 if hawkish and not dovish else 1 if dovish and not hawkish else 0
        reason = "اثر احتمالی ریسک‌پذیری، رشد و انتظارات نرخ بهره بر شاخص سهام"
        for symbol in ("US30", "USTEC", "US500"):
            add(symbol, index_score, reason)
        if "EUR" in currency_bias or "ژئوپلیتیک و امنیت" in labels or "نفت و انرژی" in labels:
            add("DE30", index_score, "اثر احتمالی خبر بر ریسک‌پذیری و سهام آلمان")

    # Return only instruments from the active Gold Prices Bot catalogue.
    return [row for row in impacts if row["symbol"] in SYMBOL_UNIVERSE]

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

    # Market snapshots are intentionally not used: the report is news-only.
    market_lines, market_warnings = [], []
    market_headwind = market_support = False
    bullish_points = int(dovish and not hawkish) + int(below and inflation) + int(risk_off and not risk_easing)
    bearish_points = int(hawkish and not dovish) + int(above and inflation) + int(risk_easing)
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
    confidence = "متوسط" if source_text_ok and macro_events and bullish_points + bearish_points >= 1 else "پایین"
    if not source_text_ok: confidence = "پایین؛ متن کامل خبر در دسترس نیست"
    if company or (hawkish and dovish): confidence = "پایین"
    bull, bear, neutral = _scenarios(labels, company)
    symbol_impacts = _symbol_impacts(combined, labels, hawkish, dovish, above, below, risk_off, risk_easing, supply_shock, company)
    return {
        "direction": direction, "drivers": drivers, "confidence": confidence,
        "events": labels, "market_lines": [], "market_warnings": [], "symbol_impacts": symbol_impacts,
        "bull": bull, "bear": bear, "neutral": neutral,
        "horizon": "اثر اولیه: ساعت‌ها تا چند روز؛ اثر سیاستی/کلان: چند هفته تا چند ماه، بسته به نوع رویداد.",
        "invalidate": "با انتشار داده معتبر جدید، تغییر انتظارات نرخ بهره، چرخش دلار/بازده واقعی یا شکست ساختار قیمت، سناریو بازبینی شود.",
        "article_text_ok": source_text_ok,
    }

def eligible(item, now, max_age_hours=24, min_relevance=0):
    stamp = parse_time(item.get("published_utc"))
    if stamp is None or stamp > now or (now - stamp).total_seconds() > max_age_hours * 3600:
        return False
    try: score = int(item.get("relevance_score", 0))
    except (ValueError, TypeError): score = 0
    return score >= min_relevance and bool(item.get("title"))
