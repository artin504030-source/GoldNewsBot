import unittest
from datetime import datetime, timezone
from telegram_news_commands import format_period_news, build_reply, period_bounds
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
 def test_current_week_filter_monday_start(self):
  items=[dict(ITEMS[0]),dict(ITEMS[1]),dict(ITEMS[2]),{'title':'Monday','published_utc':'2026-11-16T00:00:00Z'}]
  text=format_period_news('current_week',items,NOW); self.assertIn('Gold rises',text); self.assertNotIn('Fed outlook',text); self.assertNotIn('Old headline',text); self.assertIn('2026-11-16',text)
 def test_current_month_filter(self):
  text=format_period_news('current_month',ITEMS,NOW); self.assertIn('Old headline',text); self.assertIn('2026-11-01',text)
 def test_last_week_exact_calendar_week(self):
  items=[{'title':'Last Monday','published_utc':'2026-11-09T00:00:00Z'},{'title':'Last Sunday','published_utc':'2026-11-15T23:59:00Z'},{'title':'Current Monday','published_utc':'2026-11-16T00:00:00Z'}]
  text=format_period_news('last_week',items,NOW); self.assertIn('Last Monday',text); self.assertIn('Last Sunday',text); self.assertNotIn('Current Monday',text)
 def test_last_month(self):
  items=[{'title':'Oct 1','published_utc':'2026-10-01T00:00:00Z'},{'title':'Oct 31','published_utc':'2026-10-31T23:59:00Z'},{'title':'Nov 1','published_utc':'2026-11-01T00:00:00Z'},{'title':'Sep 30','published_utc':'2026-09-30T23:59:00Z'}]
  text=format_period_news('last_month',items,NOW); self.assertIn('Oct 1',text); self.assertIn('Oct 31',text); self.assertNotIn('Nov 1',text); self.assertNotIn('Sep 30',text)
 def test_new_aliases(self):
  self.assertIn('اخبار هفته جاری',build_reply('/this_week',ITEMS,NOW)); self.assertIn('اخبار ماه جاری',build_reply('/current_month',ITEMS,NOW)); self.assertIn('اخبار هفته گذشته',build_reply('/last_week',ITEMS,NOW)); self.assertIn('اخبار ماه گذشته',build_reply('/last_month',ITEMS,NOW)); self.assertIn('/last_month',build_reply('/help',ITEMS,NOW))
 def test_response_under_telegram_limit(self):
  self.assertLessEqual(len(format_period_news('month',ITEMS*10,NOW)),4096)
 def test_html_escape(self):
  item=dict(ITEMS[0],title='A <B> risky'); self.assertIn('&lt;B&gt;',format_period_news('day',[item],NOW))
if __name__=='__main__': unittest.main()
