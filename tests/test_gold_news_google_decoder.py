import json
import unittest
from goldnewsbot.safe_fetch import FetchError
from apps.gold_news_analyst.google_news import resolve_article_url, GoogleNewsDecodeError

def public_resolver(*args, **kwargs):
    return [(None, None, None, None, ("93.184.216.34", 0))]

class FakeResponse:
    def __init__(self, text="", payload=None):
        self.text = text
        self.payload = payload
    def raise_for_status(self):
        return None
    def json(self):
        return self.payload

class FakeCookies:
    def set(self, *args, **kwargs):
        return None

class FakeSession:
    def __init__(self, post_text):
        self.cookies = FakeCookies()
        self.post_text = post_text
        self.get_calls = []
        self.post_calls = []
    def get(self, url, **kwargs):
        self.get_calls.append((url, kwargs))
        return FakeResponse('<div data-n-a-sg="sig-value" data-n-a-ts="1795680000"></div>')
    def post(self, url, **kwargs):
        self.post_calls.append((url, kwargs))
        return FakeResponse(self.post_text)

class GoogleNewsDecoderTests(unittest.TestCase):
    def test_resolves_current_google_news_link(self):
        nested = json.dumps(["garturlres", "https://publisher.example/story", 1])
        raw = ")]}'\n\n" + json.dumps([["wrb.fr", "Fbv4je", nested]])
        session = FakeSession(raw)
        result = resolve_article_url(
            "https://news.google.com/rss/articles/CBMiopaque-token?oc=5",
            session=session,
            resolver=public_resolver,
        )
        self.assertEqual(result, "https://publisher.example/story")
        self.assertEqual(len(session.get_calls), 1)
        self.assertEqual(len(session.post_calls), 1)
        outer = json.loads(session.post_calls[0][1]["data"]["f.req"])
        inner = json.loads(outer[0][0][1])
        self.assertEqual(inner[0], "garturlreq")
        self.assertEqual(inner[2], "CBMiopaque-token")
        self.assertEqual(inner[3], 1795680000)

    def test_rejects_unresolved_google_news_link(self):
        raw = ")]}'\n\n" + json.dumps([["wrb.fr", "Fbv4je", None]])
        session = FakeSession(raw)
        with self.assertRaises(GoogleNewsDecodeError):
            resolve_article_url(
                "https://news.google.com/rss/articles/CBMiopaque-token",
                session=session,
                resolver=public_resolver,
            )

    def test_non_google_url_is_validated_and_returned(self):
        result = resolve_article_url("https://publisher.example/story", resolver=public_resolver)
        self.assertEqual(result, "https://publisher.example/story")

if __name__ == "__main__":
    unittest.main()
