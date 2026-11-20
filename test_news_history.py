import importlib.util, unittest
spec=importlib.util.spec_from_file_location('historymod','/mnt/files/mex/news_history.py'); mod=importlib.util.module_from_spec(spec); spec.loader.exec_module(mod)
from datetime import datetime, timezone, timedelta
class NewsHistoryTests(unittest.TestCase):
 def test_topic_counts_current_and_previous(self):
  now=datetime(2026,11,20,tzinfo=timezone.utc)
  rows=[{'title':'Gold price rises','archived_at_utc':(now-timedelta(days=1)).isoformat()},{'title':'Gold ETF news','archived_at_utc':(now-timedelta(days=2)).isoformat()},{'title':'Gold falls','archived_at_utc':(now-timedelta(days=9)).isoformat()}]
  s=mod.summarize_history(rows,now,7)
  self.assertEqual(s['current_count'],2); self.assertEqual(s['previous_count'],1); self.assertEqual(s['topic_trends'][0]['topic'],'طلا')
 def test_daily_counts(self):
  now=datetime(2026,11,20,tzinfo=timezone.utc)
  rows=[{'title':'Fed rate','archived_at_utc':(now-timedelta(days=1)).isoformat()},{'title':'Fed yields','archived_at_utc':(now-timedelta(days=1)+timedelta(hours=2)).isoformat()}]
  self.assertEqual(list(mod.summarize_history(rows,now,7)['daily_counts'].values()),[2])
 def test_repeated_titles(self):
  now=datetime(2026,11,20,tzinfo=timezone.utc); stamp=(now-timedelta(hours=2)).isoformat()
  s=mod.summarize_history([{'title':'Gold rally','archived_at_utc':stamp},{'title':'Gold rally','archived_at_utc':stamp}],now,7)
  self.assertEqual(s['repeated_headlines'][0]['count'],2)
 def test_undated_ignored(self):
  s=mod.summarize_history([{'title':'Gold news'}],datetime(2026,11,20,tzinfo=timezone.utc),7)
  self.assertEqual(s['current_count'],0)
if __name__=='__main__': unittest.main()
