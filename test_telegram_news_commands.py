import unittest
from datetime import datetime, timezone
from telegram_news_commands import format_period_news, build_reply
NOW=datetime(2026,11,20,6,30,tzinfo=timezone.utc)
ITEMS=[{'title':'Gold rises on dollar weakness','category':'Gold','importance':'high','published_utc':'2026-11-20T06:00:00+00:00','link':'https://example.com/a'}, {'title':'Fed outlook moves yields','category':'Rates','importance':'medium','published_utc':'2026-11-15T06:00:00+00:00','link':'https://example.com/b'}, {'title':'Old headline','published_utc':'2026-11-01T06:00:00+00:00','link':'https://example.com/c'}]
class PeriodCommandTests(unittest.TestCase):
 def test_daily_filter(self):
  text=format_period_news('day',ITEMS,NOW); self.assertIn('Gold rises',text); self.assertNotIn('Fed outlook',text); self.assertNotIn('Old headline',text)
 def test_week_filter(self):
  text=format_period_news('week',ITEMS,NOW); self.assertIn('Gold rises',text); self.assertIn('Fed outlook',text); self.assertNotIn('Old headline',text)
 def test_month_filter(self): self.assertIn('Old headline',format_period_news('month',ITEMS,NOW))
 def test_alias_help(self):
  self.assertIn('اخبار روز',build_reply('/daily',ITEMS,NOW)); self.assertIn('اخبار روز',build_reply('/news_today',ITEMS,NOW)); self.assertIn('30 روز',build_reply('/month',ITEMS,NOW)); self.assertIn('دستورات',build_reply('/help',ITEMS,NOW))
 def test_response_under_telegram_limit(self):
  self.assertLessEqual(len(format_period_news('month',ITEMS*10,NOW)),4096)
 def test_html_escape(self):
  item=dict(ITEMS[0],title='A <B> risky'); self.assertIn('&lt;B&gt;',format_period_news('day',[item],NOW))
if __name__=='__main__': unittest.main()
