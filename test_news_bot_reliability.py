import os, sys, unittest, types
from unittest.mock import Mock, patch
os.environ.setdefault('BOT_TOKEN','unit-test-token');os.environ.setdefault('CHANNEL_ID','unit-test-channel')
sys.path.insert(0,os.path.dirname(__file__))
if 'feedparser' not in sys.modules: sys.modules['feedparser']=types.SimpleNamespace(parse=lambda data:types.SimpleNamespace(entries=[]))
import news_bot
class ReliabilityTests(unittest.TestCase):
 def test_feed_retries_503(self):
  a=Mock(status_code=503,headers={});b=Mock(status_code=200,content=b'rss')
  with patch.object(news_bot.requests,'get',side_effect=[a,b]),patch.object(news_bot.time,'sleep'):
   self.assertEqual(news_bot.get_entries('https://example.invalid'),[])
 def test_feed_retries_network_error(self):
  with patch.object(news_bot.requests,'get',side_effect=[news_bot.requests.Timeout('timeout'),Mock(status_code=200,content=b'feed')]),patch.object(news_bot.time,'sleep'):
   self.assertEqual(news_bot.get_entries('https://example.invalid'),[])
 def test_feed_respects_retry_after(self):
  a=Mock(status_code=429,headers={'Retry-After':'7'});b=Mock(status_code=200,content=b'rss')
  with patch.object(news_bot.requests,'get',side_effect=[a,b]),patch.object(news_bot.time,'sleep') as sl:
   news_bot.get_entries('https://example.invalid');sl.assert_called_once_with(7)
 def test_feed_attempts_three_times_then_raises(self):
  with patch.object(news_bot.requests,'get',side_effect=news_bot.requests.Timeout('timeout')) as req,patch.object(news_bot.time,'sleep'):
   with self.assertRaises(news_bot.requests.Timeout):news_bot.get_entries('https://example.invalid')
   self.assertEqual(req.call_count,3)
 def test_send_retries_5xx(self):
  a=Mock(status_code=502);a.json.return_value={};b=Mock(status_code=200);b.json.return_value={'ok':True}
  with patch.object(news_bot.requests,'post',side_effect=[a,b]),patch.object(news_bot.time,'sleep'):
   self.assertTrue(news_bot.send_telegram('hello'))
 def test_send_retries_network_error(self):
  b=Mock(status_code=200);b.json.return_value={'ok':True}
  with patch.object(news_bot.requests,'post',side_effect=[news_bot.requests.ConnectionError('offline'),b]),patch.object(news_bot.time,'sleep'):
   self.assertTrue(news_bot.send_telegram('hello'))
 def test_limits_have_safe_minimum(self):self.assertGreaterEqual(news_bot.MAX_NEWS_PER_RUN,1);self.assertGreaterEqual(news_bot.MAX_AGE_HOURS,1)
if __name__=='__main__':unittest.main()
