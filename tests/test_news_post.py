import unittest
from datetime import datetime, timezone
from goldnewsbot.models import NewsItem
from goldnewsbot.news_post import format_news_post


class NewsPostTests(unittest.TestCase):
    def make_item(self):
        return NewsItem(
            title="Global markets react to central bank decision",
            url="https://example.com/news/1", source="Example News",
            published_at=datetime(2026, 11, 21, 12, 30, tzinfo=timezone.utc),
            translated_text="بانک مرکزی تصمیم تازه‌ای درباره نرخ بهره اعلام کرد.",
            analysis="این تصمیم می‌تواند بر دلار و طلا اثر بگذارد.",
            category="اقتصاد کلان | بازارهای جهانی",
            impact_instruments=("XAUUSD", "DXY"),
        )

    def test_contains_approved_news_sections(self):
        post = format_news_post(self.make_item(), translated_title="واکنش بازارهای جهانی به تصمیم بانک مرکزی", urgency="خبر مهم", importance="زیاد", tone="فشار احتمالی بر طلا", confidence="متوسط", direct_impact="دلار آمریکا", indirect_impact="طلا و بازار سهام")
        for expected in ("🌍 GoldNewsBot | اخبار بازار", "واکنش بازارهای جهانی به تصمیم بانک مرکزی", "📰 ترجمه خبر:", "بانک مرکزی تصمیم تازه‌ای", "📊 تحلیل تأثیر بر بازار:", "این تصمیم می‌تواند بر دلار و طلا اثر بگذارد.", "XAUUSD، DXY", "📅 تاریخ خبر: 21 November 2026 | 12:30 UTC", "https://example.com/news/1", "Gold Admin", "توصیه خرید یا فروش نیست"):
            self.assertIn(expected, post)

    def test_missing_optional_analysis_fields_are_safe(self):
        post = format_news_post(self.make_item())
        self.assertIn("گزارش خبری", post)
        self.assertIn("تحلیل تأثیر بازار هنوز آماده نشده است.", post)
        self.assertNotIn("🔎 لحن و جهت احتمالی خبر:", post)

    def test_missing_body_and_symbols_have_fallbacks(self):
        item = NewsItem(title="Headline", url="https://example.com", source="Wire")
        post = format_news_post(item)
        self.assertIn("متن ترجمه‌شده خبر در دسترس نیست.", post)
        self.assertIn("نماد مرتبط مشخص نیست", post)


if __name__ == "__main__":
    unittest.main()
