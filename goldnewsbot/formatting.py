from html import escape
from .models import NewsItem

def format_news(item: NewsItem) -> str:
    title = escape(item.title)
    source = escape(item.source)
    body = escape(item.translated_text or "ترجمه خبر هنوز آماده نشده است.")
    analysis = escape(item.analysis or "تحلیل هنوز آماده نشده است.")
    category = escape(item.category)
    instruments = ", ".join(escape(x) for x in item.impact_instruments) or "نامشخص"
    return (
        f"<b>📰 {title}</b>\n"
        f"<b>منبع:</b> {source}\n"
        f"<b>دسته‌بندی:</b> {category}\n\n"
        f"<b>ترجمه خبر:</b>\n{body}\n\n"
        f"<b>تحلیل بازار:</b>\n{analysis}\n\n"
        f"<b>نمادهای مرتبط:</b> {instruments}\n"
        f"<a href=\"{escape(item.url, quote=True)}\">مشاهده منبع اصلی</a>"
    )
