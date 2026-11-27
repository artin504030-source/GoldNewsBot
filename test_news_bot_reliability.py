import os, sys, unittest, types
from unittest.mock import Mock, patch
os.environ.setdefault('BOT_TOKEN','unit-test-token');os.environ.setdefault('CHANNEL_ID','unit-test-channel')
sys.path.insert(0,os.path.dirname(__file__))
if 'feedparser' not in sys.modules: sys.modules['feedparser']=types.SimpleNamespace(parse=lambda data:types.SimpleNamespace(entries=[]))
import news_bot
from gold_news_features import is_duplicate, canonical_url, classify_claim_status
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
  a=Mock(status_code=502);a.json.return_value={};b=Mock(status_code=200);b.json.return_value={'ok':True,'result':{'message_id':987}}
  with patch.object(news_bot.requests,'post',side_effect=[a,b]),patch.object(news_bot.time,'sleep'):
   result=news_bot.send_telegram('hello');self.assertEqual(result['message_id'],987)
 def test_send_retries_network_error(self):
  b=Mock(status_code=200);b.json.return_value={'ok':True,'result':{'message_id':654}}
  with patch.object(news_bot.requests,'post',side_effect=[news_bot.requests.ConnectionError('offline'),b]),patch.object(news_bot.time,'sleep'):
   result=news_bot.send_telegram('hello');self.assertEqual(result['message_id'],654)
 def test_limits_have_safe_minimum(self):self.assertGreaterEqual(news_bot.MAX_NEWS_PER_RUN,1);self.assertGreaterEqual(news_bot.MAX_AGE_HOURS,1)

 def test_geopolitical_and_energy_feeds_are_enabled(self):
  for name in ('Conflict and Security','Oil Trade and Supply','Energy Shipping Routes','Trade and Sanctions'):
   self.assertIn(name,news_bot.FEEDS);self.assertIn(name,news_bot.BREAKING_FEEDS)
 def test_oil_import_export_news_is_relevant(self):
  self.assertTrue(news_bot.is_relevant('OPEC+ cuts oil exports','Crude oil supply tightens'))
  self.assertTrue(news_bot.is_relevant('New sanctions restrict oil imports',''))
 def test_shipping_chokepoint_is_classified_as_energy_and_geopolitical(self):
  from cross_market_impact import analyze_cross_market_impact
  result=analyze_cross_market_impact('Attack on oil tankers in the Strait of Hormuz')
  self.assertIn('risk_geopolitical',result['categories']);self.assertIn('energy',result['categories'])
  self.assertIn('USOIL',result['symbols']);self.assertIn('XAUUSD',result['symbols'])
 def test_trade_sanctions_classification(self):
  from cross_market_impact import analyze_cross_market_impact
  result=analyze_cross_market_impact('New oil export ban and trade sanctions announced')
  self.assertIn('trade_sanctions',result['categories']);self.assertIn('UKOIL',result['symbols'])


 def test_canonical_url_ignores_tracking_and_www(self):
  self.assertEqual(canonical_url('https://www.example.com/story/?utm_source=x&gclid=abc'), 'https://example.com/story')

 def test_fuzzy_duplicate_requires_close_publication_time(self):
  old = {'title':'Federal Reserve holds interest rates steady','link':'https://one.example/a','published_utc':'2026-11-20T10:00:00+00:00'}
  self.assertTrue(is_duplicate(old['title'], 'https://two.example/b', [old], '2026-11-21T10:00:00+00:00'))
  self.assertFalse(is_duplicate(old['title'], 'https://two.example/b', [old], '2026-11-25T10:00:00+00:00'))

 def test_exact_canonical_url_deduplicates_even_when_updated(self):
  old = {'title':'Initial headline','link':'https://www.example.com/story?utm_campaign=x'}
  self.assertTrue(is_duplicate('Updated headline with new details', 'https://example.com/story', [old]))

 def test_uncertain_claim_language_is_flagged_without_claiming_fact_check(self):
  self.assertIn('تأییدنشده', classify_claim_status('Unconfirmed reports of an emergency rate cut'))
  self.assertIn('احراز نشده', classify_claim_status('Federal Reserve publishes minutes'))

if __name__=='__main__':unittest.main()
