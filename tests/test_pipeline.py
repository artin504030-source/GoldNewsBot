import unittest
from goldnewsbot.models import NewsItem
from goldnewsbot.pipeline import NewsPipeline

class FakeSource:
    def __init__(self, items): self.items = items
    def fetch(self): return self.items

class FakeRepository:
    def __init__(self): self.seen = set()
    def has_seen(self, key): return key in self.seen
    def mark_seen(self, key): self.seen.add(key)

class FakeSender:
    def __init__(self): self.messages = []
    def send(self, text): self.messages.append(text)

class PipelineTests(unittest.TestCase):
    def test_sends_once_and_skips_duplicate(self):
        item = NewsItem("عنوان خبر", "https://example.com/1", "منبع",
                        translated_text="ترجمه", analysis="تحلیل")
        repo, sender = FakeRepository(), FakeSender()
        pipeline = NewsPipeline(FakeSource([item, item]), repo, sender)
        result = pipeline.run_once()
        self.assertEqual((result.fetched, result.sent, result.duplicates, result.failed), (2, 1, 1, 0))
        self.assertEqual(len(sender.messages), 1)
        self.assertIn("ترجمه", sender.messages[0])

if __name__ == "__main__":
    unittest.main()
