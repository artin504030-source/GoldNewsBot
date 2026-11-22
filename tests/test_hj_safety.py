import unittest
from unittest.mock import Mock
from goldnewsbot.safe_fetch import validate_url, fetch_public_page, FetchError
from goldnewsbot.classification import classify_news
from goldnewsbot.pipeline_preview import extract_text
def public_resolver(*a,**k): return [(None,None,None,None,("93.184.216.34",0))]
def private_resolver(*a,**k): return [(None,None,None,None,("127.0.0.1",0))]
class SafetyTests(unittest.TestCase):
 def test_http_public_host_allowed(self): self.assertTrue(validate_url("https://example.com/x",public_resolver).startswith("https://"))
 def test_non_http_rejected(self):
  with self.assertRaises(FetchError): validate_url("file:///etc/passwd",public_resolver)
 def test_private_dns_rejected(self):
  with self.assertRaises(FetchError): validate_url("https://internal.example",private_resolver)
 def test_credentials_and_custom_port_rejected(self):
  for u in ("https://user:pass@example.com","https://example.com:8443"):
   with self.subTest(u=u),self.assertRaises(FetchError): validate_url(u,public_resolver)
 def test_private_redirect_rejected(self):
  response=Mock(status_code=302,headers={"Location":"http://127.0.0.1/"})
  session=Mock(); session.get.return_value=response
  with self.assertRaises(FetchError): fetch_public_page("https://example.com",session=session,resolver=public_resolver)
 def test_non_html_rejected(self):
  response=Mock(status_code=200,headers={"Content-Type":"application/json"})
  session=Mock(); session.get.return_value=response
  with self.assertRaises(FetchError): fetch_public_page("https://example.com",session=session,resolver=public_resolver)
 def test_response_size_limited(self):
  response=Mock(status_code=200,headers={"Content-Type":"text/html"},encoding="utf-8"); response.iter_content.return_value=[b"12345"]
  session=Mock(); session.get.return_value=response
  with self.assertRaises(FetchError): fetch_public_page("https://example.com",session=session,resolver=public_resolver,max_bytes=4)
 def test_oil_and_gold_classification(self):
  r=classify_news("OPEC crude oil supply disruption")
  self.assertIn("oil_energy",r.categories); self.assertIn("XAUUSD",r.related_markets)
 def test_multiple_categories(self):
  r=classify_news("Fed rate decision amid war conflict")
  self.assertIn("central_banks",r.categories); self.assertIn("war_conflict",r.categories)
 def test_html_removes_script_and_navigation(self):
  t=extract_text("<nav>menu</nav><script>bad()</script><p>OPEC crude oil supply disruption.</p>",min_chars=10)
  self.assertNotIn("menu",t); self.assertNotIn("bad",t); self.assertIn("OPEC",t)
if __name__=="__main__": unittest.main()
