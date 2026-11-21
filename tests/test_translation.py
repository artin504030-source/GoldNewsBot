import unittest
from goldnewsbot.models import NewsItem
from goldnewsbot.translation import TranslationError, translate_news_item


class FakeTranslator:
    def __init__(self, responses=None):
        self.calls = []
        self.responses = responses or {}
    def translate(self, text, *, target_language="fa"):
        self.calls.append((text, target_language))
        return self.responses.get(text, "ترجمه: " + text)


class TranslationTests(unittest.TestCase):
    def make_item(self):
        return NewsItem(title="Market headline", url="https://example.com/1", source="Wire", translated_text="Full article text")

    def test_translates_headline_and_full_body_separately(self):
        item = self.make_item()
        translator = FakeTranslator()
        translated = translate_news_item(item, translator)
        self.assertEqual(translated.translated_title, "ترجمه: Market headline")
        self.assertEqual(translated.translated_text, "ترجمه: Full article text")
        self.assertEqual(len(translator.calls), 2)
        self.assertEqual(item.translated_title, "")
        self.assertEqual(item.translated_text, "Full article text")

    def test_empty_translation_fails_closed(self):
        translator = FakeTranslator({"Market headline": "  "})
        with self.assertRaises(TranslationError):
            translate_news_item(self.make_item(), translator)

    def test_empty_article_is_rejected(self):
        item = NewsItem(title="Market headline", url="https://example.com/1", source="Wire")
        with self.assertRaises(TranslationError):
            translate_news_item(item, FakeTranslator())


if __name__ == "__main__":
    unittest.main()
