from __future__ import annotations

import re
from html import escape

# Regional macro coverage. Values are parsed only when explicitly labelled;
# an unlabelled number is never treated as an Actual, Forecast, or Previous.
REGIONS = {
    "🇪🇺 اروپا / منطقه یورو": {
        "terms": ("europe", "eurozone", "euro area", "european central bank", "ecb", "eurostat", "european union", "european economy"),
        "checks": [
            "EURUSD و EUR crosses: واکنش یورو را در برابر دلار و ارزهای دیگر بررسی کنید.",
            "بازده اوراق آلمان و سایر کشورهای اصلی منطقه یورو: آیا انتظارات نرخ تغییر کرده است؟",
            "DXY و XAUUSD: آیا حرکت یورو واقعاً به دلار و طلا منتقل شده است؟",
            "قیمت انرژی و ریسک سیاسی اروپا: آیا عامل بیرونی برداشت از داده را تغییر می‌دهد؟",
        ],
        "currency": "EUR",
    },
    "🇬🇧 بریتانیا": {
        "terms": ("united kingdom", " u.k.", "uk economy", "britain", "british", "bank of england", "boe", "ons uk"),
        "checks": [
            "GBPUSD و EURGBP: واکنش پوند را در برابر دلار و یورو بررسی کنید.",
            "بازده اوراق دولتی بریتانیا (Gilt): آیا انتظارات نرخ BoE تغییر کرده است؟",
            "DXY و XAUUSD: اثر غیرمستقیم حرکت پوند بر دلار و طلا را تأیید کنید.",
            "تورم خدمات، رشد دستمزد و بازار کار: برای سنجش پایداری تورم مهم‌اند.",
        ],
        "currency": "GBP",
    },
    "🇯🇵 ژاپن": {
        "terms": ("japan", "japanese", "bank of japan", "boj", "tokyo inflation", "tankan"),
        "checks": [
            "USDJPY و JPY crosses: جهت واکنش ین و احتمال مداخله ارزی را بررسی کنید.",
            "بازده اوراق دولتی ژاپن (JGB) و اختلاف بازده با آمریکا را بررسی کنید.",
            "DXY و XAUUSD: اثر حرکت ین بر دلار و طلا را جداگانه تأیید کنید.",
            "دستمزدها، تورم خدمات و نظرسنجی Tankan: برای مسیر سیاست BOJ مهم‌اند.",
        ],
        "currency": "JPY",
    },
    "🇨🇳 چین": {
        "terms": ("china", "chinese", "people's bank of china", "pboc", "national bureau of statistics of china", "nbs china", "yuan", "renminbi"),
        "checks": [
            "USDCNH و CNH: واکنش یوان و جهت fixing بانک مرکزی چین را بررسی کنید.",
            "سهام چین، شاخص‌های تولید و تقاضای کالاها: آیا بازار رشد را تأیید می‌کند؟",
            "AUDUSD و فلزات صنعتی: اثر داده چین بر ارزها و تقاضای مواد خام را بررسی کنید.",
            "XAUUSD: تقاضای فیزیکی چین، ریسک‌گریزی و حرکت دلار را از هم تفکیک کنید.",
        ],
        "currency": "CNY",
    },
}

INDICATORS = [
    ("HICP / Core HICP", ("hicp", "harmonised index of consumer prices", "euro area inflation", "eurozone inflation"), "inflation", False, "تورم مصرف‌کننده منطقه یورو"),
    ("ECB Rate / Policy", ("ecb rate", "ecb interest rate", "ecb deposit rate", "ecb rate decision", "ecb monetary policy"), "policy", False, "نرخ و سیاست پولی بانک مرکزی اروپا"),
    ("Eurozone GDP", ("euro area gdp", "eurozone gdp", "euro area gross domestic product"), "growth", False, "تولید ناخالص داخلی منطقه یورو"),
    ("Eurozone Unemployment", ("euro area unemployment", "eurozone unemployment"), "employment", True, "نرخ بیکاری منطقه یورو"),
    ("Eurozone Retail Sales", ("euro area retail sales", "eurozone retail sales"), "growth", False, "خرده‌فروشی منطقه یورو"),
    ("Eurozone PMI", ("eurozone pmi", "euro area pmi", "hcoB eurozone pmi"), "growth", False, "شاخص مدیران خرید منطقه یورو"),
    ("UK CPI / Core CPI", ("uk cpi", "u.k. cpi", "britain cpi", "british cpi", "uk consumer price", "uk inflation"), "inflation", False, "تورم مصرف‌کننده بریتانیا"),
    ("BoE Rate / MPC", ("bank of england rate", "boe rate", "bank rate", "monetary policy committee"), "policy", False, "نرخ و سیاست پولی بانک مرکزی انگلستان"),
    ("UK GDP", ("uk gdp", "u.k. gdp", "britain gdp", "uk gross domestic product"), "growth", False, "تولید ناخالص داخلی بریتانیا"),
    ("UK Unemployment", ("uk unemployment", "uk jobless rate", "unemployment rate uk"), "employment", True, "نرخ بیکاری بریتانیا"),
    ("UK Employment", ("uk employment", "uk payroll", "uk jobs report"), "employment", False, "اشتغال بریتانیا"),
    ("UK Wages", ("uk wages", "average earnings uk", "uk wage growth"), "employment", False, "رشد دستمزد بریتانیا"),
    ("UK Retail Sales", ("uk retail sales", "britain retail sales"), "growth", False, "خرده‌فروشی بریتانیا"),
    ("UK PMI", ("uk pmi", "britain pmi", "s&p global uk pmi"), "growth", False, "شاخص مدیران خرید بریتانیا"),
    ("Japan CPI / Core CPI", ("japan cpi", "japanese cpi", "tokyo cpi", "japan inflation"), "inflation", False, "تورم مصرف‌کننده ژاپن"),
    ("BOJ Rate / Policy", ("boj rate", "bank of japan rate", "boj monetary policy", "boj policy decision"), "policy", False, "نرخ و سیاست پولی بانک مرکزی ژاپن"),
    ("Japan GDP", ("japan gdp", "japanese gdp", "japan gross domestic product"), "growth", False, "تولید ناخالص داخلی ژاپن"),
    ("Japan Wages", ("japan wages", "japanese wages", "cash earnings japan", "real wages japan"), "employment", False, "دستمزدهای ژاپن"),
    ("Tankan Survey", ("tankan",), "growth", False, "نظرسنجی تانکان بانک مرکزی ژاپن"),
    ("China CPI / Core CPI", ("china cpi", "chinese cpi", "china consumer prices", "china inflation"), "inflation", False, "تورم مصرف‌کننده چین"),
    ("China PPI", ("china ppi", "chinese ppi", "china producer prices"), "inflation", False, "تورم تولیدکننده چین"),
    ("PBOC Rate / Policy", ("pboc rate", "pboc policy", "people's bank of china rate", "loan prime rate", "lpr rate"), "policy", False, "سیاست پولی بانک مرکزی چین"),
    ("China GDP", ("china gdp", "chinese gdp", "china gross domestic product"), "growth", False, "تولید ناخالص داخلی چین"),
    ("China PMI", ("china pmi", "chinese pmi", "official manufacturing pmi", "caixin pmi"), "growth", False, "شاخص مدیران خرید چین"),
    ("China Retail Sales", ("china retail sales", "chinese retail sales"), "growth", False, "خرده‌فروشی چین"),
    ("China Industrial Production", ("china industrial production", "chinese industrial output"), "growth", False, "تولید صنعتی چین"),
    ("China Trade Balance", ("china trade balance", "china exports", "china imports", "chinese exports", "chinese imports"), "growth", False, "تجارت خارجی چین"),
]

FIELD_PATTERNS = {
    "actual": r"(?:actual|reported|released|current)\s*[:：]?\s*([-+]?\d[\d,]*(?:\.\d+)?\s*%?)",
    "forecast": r"(?:forecast|consensus|expected|median estimate)\s*[:：]?\s*([-+]?\d[\d,]*(?:\.\d+)?\s*%?)",
    "previous": r"(?:previous|prior|previously)\s*[:：]?\s*([-+]?\d[\d,]*(?:\.\d+)?\s*%?)",
}


def _norm(value):
    return re.sub(r"\s+", " ", str(value or "").lower()).strip()


def _number(value):
    if not value:
        return None
    try:
        return float(value.replace(",", "").replace("%", "").strip())
    except ValueError:
        return None


def analyze_regional_macro(item: dict, article_text: str = ""):
    text = _norm(" ".join(str(item.get(key, "")) for key in ("title", "summary", "source")) + " " + str(article_text or "")[:12000])
    region_name = next((name for name, spec in REGIONS.items()
                        if any(term in text for term in spec["terms"])), None)
    if not region_name:
        return None

    indicator = None
    kind = None
    inverse = False
    indicator_fa = ""
    for name, terms, candidate_kind, candidate_inverse, fa in INDICATORS:
        if any(re.search(r"(?<![a-z0-9])" + re.escape(term) + r"(?![a-z0-9])", text) for term in terms):
            indicator, kind, inverse, indicator_fa = name, candidate_kind, candidate_inverse, fa
            break
    if not indicator:
        return None

    fields = {}
    for key, pattern in FIELD_PATTERNS.items():
        match = re.search(pattern, text, re.IGNORECASE)
        if match:
            fields[key] = match.group(1).strip()
    actual = _number(fields.get("actual"))
    forecast = _number(fields.get("forecast"))
    surprise = None
    if actual is not None and forecast is not None:
        delta = actual - forecast
        surprise = "مطابق انتظار" if abs(delta) < 1e-9 else (
            "قوی‌تر/بالاتر از انتظار" if (delta < 0 if inverse else delta > 0)
            else "ضعیف‌تر/پایین‌تر از انتظار"
        )

    if kind == "policy":
        hawkish = any(x in text for x in ("hawkish", "rate hike", "raise rates", "higher for longer", "tightening"))
        dovish = any(x in text for x in ("dovish", "rate cut", "cut rates", "easing", "lower rates"))
        policy = "انقباضی‌تر" if hawkish and not dovish else "انبساطی‌تر" if dovish and not hawkish else "از متن موجود قابل تعیین نیست"
    elif surprise == "قوی‌تر/بالاتر از انتظار":
        policy = "داده قوی‌تر می‌تواند انتظارات نرخ بالاتر/سیاست سخت‌گیرانه‌تر بانک مرکزی مربوط را تقویت کند."
    elif surprise == "ضعیف‌تر/پایین‌تر از انتظار":
        policy = "داده ضعیف‌تر می‌تواند فضای سیاست نرم‌تر یا کاهش نرخ را تقویت کند."
    elif surprise == "مطابق انتظار":
        policy = "غافلگیری محدود است؛ اجزای گزارش و راهنمای بانک مرکزی اهمیت بیشتری دارند."
    else:
        policy = "بدون Actual و Forecast معتبر، جهت غافلگیری و اثر سیاستی قابل تعیین نیست."

    region = REGIONS[region_name]
    if surprise == "قوی‌تر/بالاتر از انتظار":
        gold = "این داده به‌تنهایی سیگنال صعودی یا نزولی طلا نیست. ابتدا واکنش ارز منطقه، بازده اوراق و ریسک‌پذیری را بررسی کنید؛ اثر بر XAUUSD غیرمستقیم و وابسته به حرکت دلار و جریان‌های امن است."
    elif surprise == "ضعیف‌تر/پایین‌تر از انتظار":
        gold = "ضعف داده می‌تواند ارز منطقه را تضعیف و نگرانی رشد را افزایش دهد؛ اثر طلا ممکن است از مسیر تقویت دلار، تقاضای پناهگاه امن یا تغییر انتظارات نرخ متفاوت باشد. جهت قطعی بدون تأیید بازار تعیین نمی‌شود."
    elif surprise == "مطابق انتظار":
        gold = "اثر غافلگیری احتمالاً محدود است؛ جزئیات گزارش، راهنمای بانک مرکزی، ارز منطقه و واکنش بازده اوراق را بررسی کنید."
    else:
        gold = "فعلاً جهت قطعی برای XAUUSD تعیین نمی‌شود. ابتدا Actual و Forecast معتبر و سپس واکنش ارز منطقه، بازده اوراق، DXY و قیمت طلا را بررسی کنید."

    if indicator in ("HICP / Core HICP", "UK CPI / Core CPI", "Japan CPI / Core CPI", "China CPI / Core CPI", "China PPI"):
        caveat = "تورم کل و هسته را جدا کنید؛ خدمات، دستمزدها، مسکن/اجاره، انرژی و اثر پایه می‌توانند پیام متفاوتی داشته باشند."
    elif "PMI" in indicator:
        caveat = "مرز 50 را در نظر بگیرید؛ سفارش‌های جدید، اشتغال و مؤلفه قیمت‌ها را جداگانه بخوانید و نسخه مقدماتی را با نهایی اشتباه نگیرید."
    elif "GDP" in indicator:
        caveat = "برآورد اولیه را از بازنگری‌های بعدی تفکیک کنید و سهم مصرف، سرمایه‌گذاری، تجارت و موجودی انبار را بررسی کنید."
    elif "Labour" in indicator or "Wages" in indicator or "Unemployment" in indicator:
        caveat = "نرخ بیکاری را کنار مشارکت نیروی کار، رشد دستمزد و کیفیت اشتغال بسنجید؛ یک عدد منفرد کافی نیست."
    elif "Retail Sales" in indicator:
        caveat = "رشد اسمی را با تورم و اجزای اصلی فروش مقایسه کنید؛ افزایش فروش اسمی الزاماً رشد واقعی مصرف نیست."
    elif "Trade Balance" in indicator:
        caveat = "صادرات و واردات، قیمت کالاها، حجم واقعی تجارت و تقاضای شرکای تجاری را از هم جدا کنید."
    elif "Tankan" in indicator:
        caveat = "شاخص شرایط کسب‌وکار را همراه با برنامه سرمایه‌گذاری، استخدام و قیمت‌های مورد انتظار بررسی کنید."
    else:
        caveat = "تصمیم، بیانیه و راهنمای آینده بانک مرکزی را در کنار داده‌های تورم، رشد و دستمزد بررسی کنید."

    stage = "گزارش منتشرشده" if actual is not None or any(x in text for x in ("released", "reported", "published")) else (
        "پیش‌نمایش و انتظار بازار" if any(x in text for x in ("forecast", "expected", "expectations", "preview", "ahead of", "economists expect", "consensus")) else
        "خبر/اظهارنظر مرتبط؛ مرحله انتشار قطعی نیست"
    )
    confidence = "متوسط" if len(str(article_text or "").strip()) >= 300 else "پایین؛ متن کامل در دسترس نیست"
    if actual is not None and forecast is not None:
        confidence = "متوسط؛ Actual و Forecast برچسب‌دار استخراج شد، اما تطبیق با منبع رسمی لازم است"

    return {
        "region": region_name, "currency": region["currency"], "indicator": indicator,
        "indicator_fa": indicator_fa, "stage": stage,
        "actual": fields.get("actual"), "forecast": fields.get("forecast"),
        "previous": fields.get("previous"), "surprise": surprise,
        "policy": policy, "gold": gold, "caveat": caveat,
        "checks": region["checks"], "confidence": confidence,
    }


def render_regional_macro_section(item: dict, article_text: str = "") -> list[str]:
    data = analyze_regional_macro(item, article_text)
    if not data:
        return []
    lines = [
        "",
        "<b>" + escape(data["region"]) + " | تحلیل تخصصی گزارش اقتصادی</b>",
        "شاخص شناسایی‌شده: <b>" + escape(data["indicator"]) + " — " + escape(data["indicator_fa"]) + "</b>",
        "ارز اصلی منطقه: " + escape(data["currency"]),
        "مرحله خبر: " + escape(data["stage"]),
        "Actual: " + (escape(data["actual"]) if data["actual"] else "در متن قابل‌استخراج نیست")
        + " | Forecast: " + (escape(data["forecast"]) if data["forecast"] else "در متن قابل‌استخراج نیست")
        + " | Previous: " + (escape(data["previous"]) if data["previous"] else "در متن قابل‌استخراج نیست"),
        "غافلگیری نسبت به انتظار: <b>" + escape(data["surprise"] or "قابل محاسبه نیست؛ Actual و Forecast کامل نیست") + "</b>",
        "<b>برداشت برای سیاست پولی:</b> " + escape(data["policy"]),
        "<b>مسیر اثر بر طلا:</b> " + escape(data["gold"]),
        "<b>نکته تخصصی شاخص:</b> " + escape(data["caveat"]),
        "<b>مواردی که باید پس از انتشار کنترل شوند:</b>",
    ]
    lines.extend("• " + escape(value) for value in data["checks"])
    lines.append("اطمینان این بخش: " + escape(data["confidence"]))
    return lines
