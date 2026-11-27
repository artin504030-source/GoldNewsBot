from html import escape
from datetime import datetime
from urllib.parse import urlparse
from zoneinfo import ZoneInfo
import requests
from .engine import analyse, parse_time
from .us_macro import render_us_macro_section
from .regional_macro import render_regional_macro_section

KABUL = ZoneInfo("Asia/Kabul")


def translate_title_to_persian(title):
    """Translate a headline to Persian using Google's free public translation endpoint.
    Keep the original headline if translation is unavailable.
    """
    title = str(title or "").strip()
    if not title:
        return "ترجمه عنوان در دسترس نیست"
    try:
        response = requests.get(
            "https://translate.googleapis.com/translate_a/single",
            params={"client": "gtx", "sl": "auto", "tl": "fa", "dt": "t", "q": title[:500]},
            timeout=8,
        )
        response.raise_for_status()
        payload = response.json()
        translated = "".join(
            part[0] for part in payload[0]
            if isinstance(part, list) and part and isinstance(part[0], str)
        ).strip()
        return translated or "ترجمه عنوان در دسترس نیست"
    except (requests.RequestException, ValueError, TypeError, IndexError):
        return "ترجمه عنوان در دسترس نیست"


def _domain(url):
    try: return urlparse(url).netloc.lower().removeprefix("www.")[:100] or "نامشخص"
    except (TypeError, ValueError): return "نامشخص"


def render(item, article=None, market_snapshot=None):
    article = article or {}
    a = analyse(item, article.get("body", ""), market_snapshot)
    stamp = parse_time(item.get("published_utc"))
    local = stamp.astimezone(KABUL).strftime("%Y-%m-%d %H:%M کابل") if stamp else "زمان نامشخص"
    original_title = str(item.get("title", "بدون عنوان"))[:500]
    title = escape(original_title)
    persian_title = escape(translate_title_to_persian(original_title))
    registered_source = escape(str(item.get("source", "نامشخص"))[:120])
    original_url = article.get("final_url") or item.get("link", "")
    safe_link = escape(original_url, quote=True) if isinstance(original_url, str) and original_url.startswith(("https://", "http://")) else ""
    article_ok = bool(article.get("body") and len(article.get("body", "").strip()) >= 300)
    is_conference = item.get("content_type") == "economic_press_conference_transcript"
    lines = [
        "🧠 <b>تحلیلگر اخبار بازار | Gold News Analyst</b>",
        *([ "🏛 <b>تحلیل متن نشست خبری اقتصادی</b>",
             "این ارزیابی بر اساس متن منتشرشده نشست و اظهارات ثبت‌شده انجام شده است؛ برداشت‌ها و سناریوها قطعی نیستند." ]
          if is_conference else []),
        f"📰 <b>عنوان اصلی: {title}</b>",
        f"🇮🇷 <b>عنوان فارسی: {persian_title}</b>",
        f"منبع ثبت‌شده در آرشیو: {registered_source}",
        f"اعتبار منبع: {escape(str(item.get('source_status', 'وضعیت منبع ثبت نشده'))[:160])}",
        f"وضعیت ادعا: {escape(str(item.get('claim_status', 'تأیید مستقل در آرشیو احراز نشده'))[:180])}",
        f"ناشر/دامنه مقصد: {escape(_domain(original_url))}",
        f"زمان انتشار ثبت‌شده: {local}",
        f"امتیاز ارتباط با طلا در آرشیو: {escape(str(item.get('relevance_score', 'نامشخص')))} از ۱۰۰",
        f"وضعیت متن اصلی: {'متن مقاله دریافت شد' if article_ok else 'متن کامل دریافت نشد؛ تحلیل محدود به عنوان/خلاصه است'}",
        "",
        "<b>دسته‌ها و محرک‌های شناسایی‌شده</b>",
        escape("، ".join(a["events"]) if a["events"] else "دسته مشخصی با اطمینان شناسایی نشد"),
        "",
        "<b>اثر احتمالی بر طلا (در صورت ارتباط)</b>",
        f"ارزیابی اولیه: <b>{escape(a['direction'])}</b>",
        *["• " + escape(x) for x in a["drivers"]],
        "",
        "<b>سناریوهای بازار</b>",
        "🟢 صعودی: " + escape(a["bull"]),
        "🔴 نزولی: " + escape(a["bear"]),
        "⚪ خنثی: " + escape(a["neutral"]),
        "",
        f"افق بررسی: {escape(a['horizon'])}",
        f"اطمینان: {escape(a['confidence'])}",
        "شرط بازبینی: " + escape(a["invalidate"]),
    ]
    lines += render_us_macro_section(item, article.get("body", ""))
    lines += render_regional_macro_section(item, article.get("body", ""))
    lines += ["", "<b>نمادهای مرتبط و اثر احتمالی</b>"]
    if a.get("symbol_impacts"):
        for impact in a["symbol_impacts"]:
            lines.append("• <b>" + escape(impact["symbol"]) + "</b> — " + escape(impact["impact"]) + ": " + escape(impact["reason"]))
    else:
        lines.append("نماد مشخصی با ارتباط قابل‌دفاع از متن خبر شناسایی نشد؛ از حدس‌زدن اثر خودداری شد.")
    if article.get("error"):
        lines += ["وضعیت دریافت مقاله: " + escape(str(article["error"])[:220])]
    lines += [
        "",
        "⚠️ تعداد فیدهای ثبت‌شده، تأیید ناشران مستقل نیست. مگر آن‌که منبع اولیه و تأیید مستقل جداگانه بررسی شود، خبر را قطعی تلقی نکنید.",
        "این تحلیل قاعده‌محور و توضیحی است؛ اثرهای نمادها سناریویی‌اند و بدون تأیید قیمت/بازار، سیگنال قطعی محسوب نمی‌شوند.",
        "سیگنال ورود یا توصیه معامله نیست.",
    ]
    if safe_link:
        lines += ["", f'🔗 <a href="{safe_link}">بازکردن صفحه خبر / ناشر</a>']
    lines += ["", "<b>Gold Admin</b>", "<b>Analyst Admin</b>"]
    return "\n".join(lines)
