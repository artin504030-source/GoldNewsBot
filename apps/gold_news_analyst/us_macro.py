from __future__ import annotations

import re
from html import escape

INDICATORS = {
    "CPI / Core CPI": {
        "terms": ("cpi", "consumer price index", "core cpi", "consumer prices", "shelter inflation"),
        "kind": "inflation", "inverse": False,
        "fa": "تورم مصرف‌کننده",
    },
    "PCE / Core PCE": {
        "terms": ("pce", "personal consumption expenditures", "core pce"),
        "kind": "inflation", "inverse": False, "fa": "تورم PCE مورد توجه فدرال رزرو",
    },
    "PPI": {
        "terms": ("ppi", "producer price index", "producer prices"),
        "kind": "inflation", "inverse": False, "fa": "تورم تولیدکننده",
    },
    "NFP / Payrolls": {
        "terms": ("nonfarm payroll", "non-farm payroll", "payrolls", "jobs report", "employment report"),
        "kind": "employment", "inverse": False, "fa": "اشتغال غیرکشاورزی",
    },
    "Unemployment Rate": {
        "terms": ("unemployment rate", "jobless rate"),
        "kind": "employment", "inverse": True, "fa": "نرخ بیکاری",
    },
    "Initial / Continuing Jobless Claims": {
        "terms": ("initial jobless claims", "continuing claims", "jobless claims", "unemployment claims"),
        "kind": "employment", "inverse": True, "fa": "درخواست بیمه بیکاری",
    },
    "Average Hourly Earnings": {
        "terms": ("average hourly earnings", "hourly earnings", "wage growth"),
        "kind": "employment", "inverse": False, "fa": "میانگین دستمزد ساعتی",
    },
    "GDP": {
        "terms": ("gdp", "gross domestic product"),
        "kind": "growth", "inverse": False, "fa": "تولید ناخالص داخلی",
    },
    "Retail Sales": {
        "terms": ("retail sales", "retail spending"),
        "kind": "growth", "inverse": False, "fa": "خرده‌فروشی",
    },
    "ISM / PMI": {
        "terms": ("ism manufacturing", "ism services", "pmi", "purchasing managers"),
        "kind": "growth", "inverse": False, "fa": "شاخص مدیران خرید",
    },
    "Fed Rate / FOMC": {
        "terms": ("federal funds rate", "fed funds rate", "fomc", "fed rate", "federal reserve rate"),
        "kind": "policy", "inverse": False, "fa": "نرخ بهره و تصمیم فدرال رزرو",
    },
    "JOLTS": {
        "terms": ("jolts", "job openings"),
        "kind": "employment", "inverse": False, "fa": "فرصت‌های شغلی JOLTS",
    },
}

# Parse only explicitly labelled Actual/Forecast/Previous fields. Never infer
# a value from an arbitrary number in an article paragraph.
FIELD_PATTERNS = {
    "actual": r"(?:actual|reported|released|current)\\s*[:：]?\\s*([-+]?\\d[\\d,]*(?:\\.\\d+)?\\s*%?)",
    "forecast": r"(?:forecast|consensus|expected|median estimate)\\s*[:：]?\\s*([-+]?\\d[\\d,]*(?:\\.\\d+)?\\s*%?)",
    "previous": r"(?:previous|prior|previously)\\s*[:：]?\\s*([-+]?\\d[\\d,]*(?:\\.\\d+)?\\s*%?)",
}


def _normal(value: str) -> str:
    return re.sub(r"\\s+", " ", str(value or "").lower()).strip()


def _first_indicator(text: str):
    for name, spec in INDICATORS.items():
        if any(re.search(r"(?<![a-z0-9])" + re.escape(term) + r"(?![a-z0-9])", text) for term in spec["terms"]):
            return name, spec
    return None, None


def _extract_fields(text: str):
    values = {}
    for field, pattern in FIELD_PATTERNS.items():
        match = re.search(pattern, text, re.IGNORECASE)
        if match:
            values[field] = match.group(1).strip()
    return values


def _number(value):
    if not value:
        return None
    cleaned = value.replace(",", "").replace("%", "").strip()
    try:
        return float(cleaned)
    except ValueError:
        return None


def analyze_us_macro(item: dict, article_text: str = ""):
    title = str(item.get("title", ""))
    summary = str(item.get("summary", ""))
    text = _normal(title + " " + summary + " " + str(article_text or "")[:12000])
    indicator, spec = _first_indicator(text)
    if not spec:
        return None

    fields = _extract_fields(text)
    actual = _number(fields.get("actual"))
    forecast = _number(fields.get("forecast"))
    previous = _number(fields.get("previous"))
    stage = "گزارش منتشرشده" if actual is not None or any(x in text for x in ("released", "reported", "came in", "公布")) else (
        "پیش‌نمایش و انتظار بازار" if any(x in text for x in ("forecast", "expected", "expectations", "preview", "ahead of", "economists expect", "consensus")) else
        "خبر/اظهارنظر مرتبط؛ زمان و مرحله انتشار قطعی نیست"
    )

    surprise = None
    if actual is not None and forecast is not None:
        delta = actual - forecast
        if abs(delta) < 1e-9:
            surprise = "مطابق انتظار"
        else:
            better = delta < 0 if spec["inverse"] else delta > 0
            surprise = "قوی‌تر/بالاتر از انتظار" if better else "ضعیف‌تر/پایین‌تر از انتظار"

    if spec["kind"] == "policy":
        hawkish = any(x in text for x in ("rate hike", "raise rates", "higher for longer", "hawkish", "hold rates", "kept rates unchanged"))
        dovish = any(x in text for x in ("rate cut", "cut rates", "lower rates", "dovish", "rate reduction"))
        bias = "انقباضی" if hawkish and not dovish else "انبساطی" if dovish and not hawkish else "نامشخص/وابسته به متن بیانیه"
    elif surprise == "قوی‌تر/بالاتر از انتظار":
        bias = "فشار بالقوه برای حفظ نرخ‌های بالا یا سیاست انقباضی‌تر"
    elif surprise == "ضعیف‌تر/پایین‌تر از انتظار":
        bias = "فضای بالقوه برای کاهش نرخ یا سیاست نرم‌تر"
    elif surprise == "مطابق انتظار":
        bias = "اثر غافلگیری محدود؛ جزئیات اجزا و راهنمای آینده مهم‌تر است"
    else:
        bias = "جهت سیاستی از اطلاعات موجود قابل تعیین نیست؛ Actual و Forecast معتبر لازم است"

    if spec["kind"] == "inflation":
        mechanism = "تورم بالاتر می‌تواند کاهش نرخ بهره را به تعویق بیندازد؛ مسیر اصلی اثر بر طلا از انتظارات نرخ فدرال رزرو، بازده واقعی اوراق و دلار می‌گذرد. تورم پایین‌تر معمولاً این فشار را کم می‌کند."
    elif spec["kind"] == "employment":
        mechanism = "اشتغال و دستمزد قوی می‌تواند نیاز به کاهش سریع نرخ را کم کند؛ ضعف اشتغال ممکن است انتظارات کاهش نرخ را بالا ببرد. اگر ضعف بازار کار ترس رکود ایجاد کند، تقاضای پناهگاه امن نیز می‌تواند هم‌زمان اثر بگذارد."
    elif spec["kind"] == "growth":
        mechanism = "رشد قوی می‌تواند دلار و بازده را از مسیر انتظارات نرخ تقویت کند؛ رشد ضعیف ممکن است نرخ‌های مورد انتظار را پایین بیاورد، اما نگرانی رکود و ریسک‌گریزی می‌تواند نتیجه را پیچیده کند."
    else:
        mechanism = "تصمیم و راهنمای فدرال رزرو مستقیماً انتظارات مسیر نرخ بهره را تغییر می‌دهد؛ متن بیانیه، رأی اعضا، پیش‌بینی‌ها و لحن کنفرانس مطبوعاتی از خود عدد نرخ مهم‌تر می‌تواند باشد."

    if surprise == "قوی‌تر/بالاتر از انتظار":
        gold = "در حالت معمول فشار نزولی بالقوه بر XAUUSD، به شرط رشد DXY و بازده واقعی؛ اگر بازار خبر را از قبل قیمت‌گذاری کرده باشد یا ریسک‌گریزی غالب شود، نتیجه می‌تواند متفاوت باشد."
    elif surprise == "ضعیف‌تر/پایین‌تر از انتظار":
        gold = "در حالت معمول حمایت بالقوه از XAUUSD، به شرط افت دلار و بازده واقعی؛ اگر داده ضعف شدید اقتصادی و فروش گسترده دارایی‌ها ایجاد کند، واکنش طلا ممکن است دوگانه باشد."
    elif surprise == "مطابق انتظار":
        gold = "اثر مستقیم غافلگیری احتمالاً محدود است؛ جزئیات داخلی گزارش، بازنگری عدد قبلی و واکنش اوراق/دلار می‌تواند جهت بعدی را تعیین کند."
    else:
        gold = "فعلاً جهت قطعی برای طلا تعیین نمی‌شود. صرفاً نام شاخص یا پیش‌بینی تحلیل‌گران کافی نیست؛ باید عدد واقعی با اجماع بازار مقایسه شود."

    if indicator in ("CPI / Core CPI", "PCE / Core PCE"):
        caveat = "برای CPI/PCE، Headline و Core را جدا بررسی کنید؛ خدمات، Shelter و اجزای چسبنده می‌توانند از عدد کل مهم‌تر باشند. اثر Base Effect را هم در مقایسه سالانه در نظر بگیرید."
    elif indicator == "NFP / Payrolls":
        caveat = "در NFP فقط تیتر اشتغال کافی نیست: بازنگری دو ماه قبل، نرخ بیکاری، مشارکت نیروی کار و Average Hourly Earnings را هم بخوانید."
    elif indicator == "GDP":
        caveat = "در GDP، برآورد اولیه/دوم/نهایی را تفکیک کنید و مصرف شخصی، سرمایه‌گذاری، موجودی انبار و شاخص قیمت PCE را جداگانه بسنجید."
    elif indicator == "ISM / PMI":
        caveat = "عدد بالای 50 معمولاً گسترش فعالیت و زیر 50 انقباض را نشان می‌دهد؛ اما قیمت‌های پرداختی، اشتغال و سفارش‌های جدید ممکن است پیام متفاوتی بدهند."
    elif indicator == "Retail Sales":
        caveat = "فروش خرده‌فروشی را همراه با گروه کنترل و داده‌های تعدیل‌شده از نظر تورم بررسی کنید؛ رشد اسمی الزاماً به معنی رشد واقعی مصرف نیست."
    elif indicator == "Unemployment Rate":
        caveat = "نرخ بیکاری را همراه با نرخ مشارکت و اشتغال خانوار بررسی کنید؛ افزایش نرخ بیکاری همیشه به‌تنهایی به معنی ضعف یکسان بازار کار نیست."
    else:
        caveat = "بازنگری داده‌های قبلی، اجزای داخلی گزارش و تفاوت داده اسمی/واقعی را پیش از نتیجه‌گیری بررسی کنید."

    checks = [
        "DXY: آیا دلار پس از خبر تقویت یا تضعیف شد؟",
        "US 2Y و US 10Y: آیا بازده اوراق هم‌جهت با برداشت اولیه حرکت کرد؟",
        "بازده واقعی اوراق (به‌ویژه TIPS): آیا هزینه فرصت نگهداری طلا تغییر کرد؟",
        "XAUUSD: آیا قیمت حرکت را حفظ کرد یا حرکت اولیه سریعاً برگشت؟",
        "انتظارات نرخ فدرال رزرو: آیا بازار احتمال/زمان کاهش یا افزایش نرخ را تغییر داد؟",
    ]

    confidence = "متوسط" if len(str(article_text or "").strip()) >= 300 else "پایین؛ متن کامل در دسترس نیست"
    if actual is not None and forecast is not None:
        confidence = "متوسط؛ مقادیر Actual و Forecast در متن شناسایی شد، اما باید با منبع رسمی تطبیق شود"
    if spec["kind"] == "policy" and not any(x in text for x in ("statement", "press conference", "minutes", "rate decision")):
        confidence = "پایین؛ صرف اشاره به فدرال رزرو برای تعیین موضع سیاستی کافی نیست"

    return {
        "indicator": indicator, "indicator_fa": spec["fa"], "stage": stage,
        "actual": fields.get("actual"), "forecast": fields.get("forecast"),
        "previous": fields.get("previous"), "surprise": surprise,
        "policy_bias": bias, "mechanism": mechanism, "gold": gold,
        "caveat": caveat, "checks": checks, "confidence": confidence,
    }


def render_us_macro_section(item: dict, article_text: str = "") -> list[str]:
    data = analyze_us_macro(item, article_text)
    if not data:
        return []
    lines = [
        "",
        "<b>🇺🇸 تحلیل تخصصی گزارش اقتصادی آمریکا</b>",
        "شاخص شناسایی‌شده: <b>" + escape(data["indicator"]) + " — " + escape(data["indicator_fa"]) + "</b>",
        "مرحله خبر: " + escape(data["stage"]),
    ]
    fields = []
    for label, key in (("Actual", "actual"), ("Forecast", "forecast"), ("Previous", "previous")):
        fields.append(label + ": " + (escape(str(data[key])) if data[key] is not None else "در متن قابل‌استخراج نیست"))
    lines.append(" | ".join(fields))
    lines.append("غافلگیری نسبت به انتظار: <b>" + escape(data["surprise"] or "قابل محاسبه نیست؛ Actual و Forecast کامل نیست") + "</b>")
    lines += [
        "برداشت اولیه برای سیاست پولی: " + escape(data["policy_bias"]),
        "<b>مسیر انتقال اثر به بازار:</b> " + escape(data["mechanism"]),
        "<b>اثر احتمالی بر طلا:</b> " + escape(data["gold"]),
        "<b>نکته تخصصی این شاخص:</b> " + escape(data["caveat"]),
        "<b>مواردی که باید بعد از انتشار کنترل شوند:</b>",
    ]
    lines.extend("• " + escape(x) for x in data["checks"])
    lines.append("اطمینان این بخش: " + escape(data["confidence"]))
    return lines
