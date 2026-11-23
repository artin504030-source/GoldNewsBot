import unittest
from unittest.mock import patch
from goldnewsbot.integration import fetch_and_classify_article
class IntegrationTests(unittest.TestCase):
 def test_safe_full_article_is_classified(self):
  body="OPEC crude oil supply disruption affects tanker exports and gold price. "+("Market report. "*40)
  with patch("goldnewsbot.integration.preview_article",return_value={"body":body,"categories":["oil_energy"],"related_markets":["XAUUSD","CRUDE_OIL"],"matched_terms":["crude oil"]}):
   r=fetch_and_classify_article("https://example.com/news","OPEC oil supply")
  self.assertTrue(r["full_article"]); self.assertIn("XAUUSD",r["related_markets"]); self.assertEqual(r["body"],body.strip()[:12000])
 def test_rss_fallback_on_fetch_error(self):
  with patch("goldnewsbot.integration.preview_article",side_effect=RuntimeError("network blocked")):
   r=fetch_and_classify_article("https://example.com/news","OPEC crude oil supply","OPEC crude oil supply disruption")
  self.assertFalse(r["full_article"]); self.assertIn("oil_energy",r["categories"]); self.assertEqual(r["body"],"OPEC crude oil supply disruption")
 def test_short_page_uses_fallback(self):
  with patch("goldnewsbot.integration.preview_article",return_value={"body":"short","categories":[],"related_markets":[],"matched_terms":[]}):
   r=fetch_and_classify_article("https://example.com/news","CPI","CPI inflation report")
  self.assertFalse(r["full_article"]); self.assertEqual(r["body"],"CPI inflation report")
if __name__=="__main__":unittest.main()
