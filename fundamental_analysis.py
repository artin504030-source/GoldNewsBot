"""Rule-based fundamental release analysis. Scenario context only, not trade signals."""
from dataclasses import dataclass
from typing import Optional

INDICATOR_RULES = [
    ("inflation", ("cpi", "core cpi", "pce", "inflation", "price index"), "higher", "تورم بالاتر از انتظار", "فشار برای سیاست پولی سخت‌گیرانه‌تر"),
    ("employment", ("nfp", "nonfarm", "non-farm", "payroll", "employment change", "jobs report"), "higher", "اشتغال قوی‌تر از انتظار", "تقویت احتمال سیاست سخت‌گیرانه‌تر"),
    ("unemployment", ("unemployment rate", "jobless rate", "unemployment"), "lower", "بیکاری کمتر از انتظار", "نشانه قدرت بازار کار"),
    ("growth", ("gdp", "gross domestic product", "economic growth"), "higher", "رشد اقتصادی بالاتر از انتظار", "نشانه قدرت اقتصاد"),
    ("pmi", ("pmi", "purchasing managers", "ism"), "higher", "فعالیت اقتصادی قوی‌تر", "نشانه گسترش فعالیت"),
    ("rates", ("interest rate", "policy rate", "rate decision", "fed funds", "cash rate"), "higher", "نرخ/راهنمایی سیاستی بالاتر", "سیاست انقباضی‌تر"),
    ("consumer", ("retail sales", "consumer spending", "consumer confidence"), "higher", "مصرف قوی‌تر", "نشانه تقاضای بیشتر"),
]
CURRENCY_BY_COUNTRY = {"US":"USD","USA":"USD","UNITED STATES":"USD","EU":"EUR","EUROZONE":"EUR","EURO AREA":"EUR","UK":"GBP","UNITED KINGDOM":"GBP","JAPAN":"JPY","CANADA":"CAD","AUSTRALIA":"AUD","NEW ZEALAND":"NZD","SWITZERLAND":"CHF","CHINA":"CNY"}

def _number(value):
    if value is None or str(value).strip() in ("", "-", "N/A", "n/a"):
        return None
    try:
        return float(str(value).replace(",", "").replace("%", "").strip())
    except (ValueError, TypeError):
        return None

def identify_indicator(name):
    text = (name or "").lower()
    for key, terms, _, _, _ in INDICATOR_RULES:
        if any(term in text for term in terms):
            return key
    return "unknown"

def analyze_release(event, actual=None, forecast=None, previous=None, country=None, currency=None):
    """Accept event dict or explicit args. Actual-vs-forecast is primary; output cautious macro scenarios."""
    if isinstance(event, dict):
        name = str(event.get("title") or event.get("event") or event.get("name") or "Economic release")
        actual = event.get("actual", actual); forecast = event.get("forecast", forecast); previous = event.get("previous", previous)
        country = event.get("country", country); currency = event.get("currency", currency)
    else:
        name = str(event or "Economic release")
    kind = identify_indicator(name)
    actual_n, forecast_n = _number(actual), _number(forecast)
    curr = (currency or CURRENCY_BY_COUNTRY.get(str(country or "").strip().upper(), "" )).upper()
    if kind == "unknown":
        return {"event":name,"indicator":kind,"currency":curr or None,"status":"نامشخص","surprise":None,"bias":"خنثی","summary":"نوع شاخص شناسایی نشد؛ مقایسه و جهت‌گیری انجام نشد.","scenarios":[],"confidence":"پایین"}
    if actual_n is None or forecast_n is None:
        return {"event":name,"indicator":kind,"currency":curr or None,"status":"منتظر داده","surprise":None,"bias":"خنثی","summary":"Actual و Forecast هر دو لازم‌اند؛ هنوز جهت‌گیری ساخته نشده.","scenarios":[],"confidence":"پایین"}
    diff = actual_n - forecast_n
    if diff == 0: surprise = "مطابق انتظار"; macro_bias = "neutral"
    else:
        higher = diff > 0
        favorable = higher if next(rule[2] == "higher" for rule in INDICATOR_RULES if rule[0] == kind) else not higher
        surprise = "بالاتر" if higher else "پایین‌تر"
        macro_bias = "hawkish" if favorable else "dovish"
    if macro_bias == "hawkish":
        bias = f"{curr or 'ارز مربوط'} بالقوه تقویت؛ طلا و دارایی‌های حساس به نرخ ممکن است تحت فشار باشند"
        scenarios = ["بازده اوراق/دلار افزایش یابد: فشار احتمالی بر طلا", "بازار انتظار نرخ بالاتر یا کاهش دیرتر نرخ را قیمت‌گذاری کند"]
    elif macro_bias == "dovish":
        bias = f"{curr or 'ارز مربوط'} بالقوه تضعیف؛ طلا ممکن است حمایت شود"
        scenarios = ["بازده اوراق/دلار کاهش یابد: حمایت احتمالی از طلا", "بازار انتظار سیاست نرم‌تر یا کاهش زودتر نرخ را قیمت‌گذاری کند"]
    else:
        bias = "جهت روشن از اختلاف Actual و Forecast به دست نیامد"
        scenarios = ["واکنش به جزئیات، بازنگری Previous و سخنان مقام‌ها بستگی دارد"]
    return {"event":name,"indicator":kind,"currency":curr or None,"actual":actual,"forecast":forecast,"previous":previous,"status":surprise,"surprise":round(diff,6),"bias":bias,"summary":f"نتیجه {surprise} نسبت به Forecast؛ تفسیر به‌صورت سناریوی احتمالی، نه پیش‌بینی قطعی.","scenarios":scenarios,"confidence":"متوسط؛ فقط اختلاف Actual/Forecast و قواعد ساده، بدون بررسی بازنگری یا قیمت بازار"}
