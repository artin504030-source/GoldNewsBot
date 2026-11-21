"""Persian Telegram news-post formatter."""
from datetime import timezone
from .models import NewsItem


def _date_label(value):
    if value is None:
        return "زمان نامشخص"
    if value.tzinfo is None:
        value = value.replace(tzinfo=timezone.utc)
    return value.astimezone(timezone.utc).strftime("%d %B %Y | %H:%M UTC")


def format_news_post(item: NewsItem, *, translated_title="", urgency="گزارش خبری", importance="نامشخص", tone="", confidence="", direct_impact="", indirect_impact="", signature="@silent0trader"):
    """Build the approved Persian news layout; performs no network or I/O."""
    title = (translated_title or item.title).strip()
    body = (item.translated_text or "").strip()
    analysis = (item.analysis or "").strip()
    instruments = "، ".join(item.impact_instruments) or "نماد مرتبط مشخص نیست"
    category = (item.category or "عمومی").strip()
    sections = [
        "🌍 GoldNewsBot | اخبار بازار", "", f"🔴 {urgency.strip()}",
        f"📰 {title}", "", "📰 ترجمه خبر:",
        body or "متن ترجمه‌شده خبر در دسترس نیست.", "",
        "📊 تحلیل تأثیر بر بازار:", analysis or "تحلیل تأثیر بازار هنوز آماده نشده است.",
        f"📌 نمادهای مرتبط: {instruments}",
    ]
    for label, value in (
        ("🔎 لحن و جهت احتمالی خبر", tone),
        ("🎚 میزان اطمینان تحلیل", confidence),
        ("🎯 اثر مستقیم احتمالی", direct_impact),
        ("🌐 اثرات غیرمستقیم", indirect_impact),
    ):
        if value.strip():
            sections.append(f"{label}: {value.strip()}")
    sections.extend([
        "", f"🏷 دسته‌بندی: {category}", f"⭐ اهمیت خبر: {importance.strip()}",
        f"🗞 منبع: {item.source.strip()}",
        f"📅 تاریخ خبر: {_date_label(item.published_at)}",
        f"🔗 لینک منبع: {item.url.strip()}", "", signature.strip(), "",
        "⚠️ این پیام ترجمه و تحلیل خبری است و توصیه خرید یا فروش نیست.",
    ])
    return "\n".join(sections)
