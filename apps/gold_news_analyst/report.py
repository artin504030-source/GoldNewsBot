from html import escape
from datetime import datetime, timezone
from zoneinfo import ZoneInfo
from .engine import analyse, parse_time

KABUL = ZoneInfo("Asia/Kabul")

def render(item):
    a = analyse(item)
    stamp = parse_time(item.get("published_utc"))
    local = stamp.astimezone(KABUL).strftime("%Y-%m-%d %H:%M کابل") if stamp else "زمان نامشخص"
    title = escape(str(item.get("title", "بدون عنوان"))[:500])
    source = escape(str(item.get("source", "نامشخص"))[:120])
    link = str(item.get("link", ""))
    safe_link = escape(link, quote=True) if link.startswith(("https://", "http://")) else ""
    lines = ["🧠 <b>تحلیلگر اخبار طلا | Gold News Analyst</b>", f"📰 <b>{title}</b>", f"منبع ثبت‌شده: {source}", f"زمان انتشار: {local}", f"ارتباط با طلا در طبقه‌بندی خبر: {escape(str(item.get('relevance_score', 'نامشخص')))} از ۱۰۰", "", "<b>ارزیابی اثر احتمالی</b>", f"جهت اولیه: {escape(a['direction'])}", *["• " + escape(x) for x in a["drivers"]], "", "<b>سناریوها</b>", "🟢 صعودی: " + escape(a["bull"]), "🔴 نزولی: " + escape(a["bear"]), "⚪ خنثی: " + escape(a["neutral"]), "", f"افق بررسی: {escape(a['horizon'])}", f"اطمینان تحلیل: {escape(a['confidence'])}", "شرط بازبینی: " + escape(a["invalidate"]), ""]
    # Archive source_count is not proof of independent publishers.
    lines += ["⚠️ تعداد منابع ثبت‌شده در آرشیو، لزوماً تأیید ناشران مستقل نیست.", "این تحلیل قاعده‌محور و اولیه است؛ قیمت زنده، بازده اوراق و DXY در این پیام بررسی نشده‌اند.", "سیگنال ورود یا توصیه معامله نیست.", ""]
    if safe_link: lines.append(f'🔗 <a href="{safe_link}">لینک خبر</a>')
    lines += ["", "<b>Gold Admin</b>", "<b>Analyst Admin</b>"]
    return "\n".join(lines)
