import tempfile
import unittest
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from scripts.foundation_preflight import inspect_project

class FoundationPreflightTests(unittest.TestCase):
    def test_reports_missing_required_files(self):
        with tempfile.TemporaryDirectory() as tmp:
            results = inspect_project(Path(tmp))
            self.assertTrue(any(status == "FAIL" for status, _, _ in results))

    def test_detects_invalid_archive_json(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            for rel in ("news_bot.py", "telegram_news_commands.py", "requirements.txt", "seen_news.json", ".github/workflows/news.yml"):
                path = root / rel
                path.parent.mkdir(parents=True, exist_ok=True)
                path.write_text("[]", encoding="utf-8")
            (root / "news_archive.json").write_text("{broken", encoding="utf-8")
            results = inspect_project(root)
            self.assertIn(("FAIL", "json-parse", "news_archive.json"), results)

    def test_accepts_valid_json_lists(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            for rel in ("news_bot.py", "telegram_news_commands.py", "requirements.txt", "news_archive.json", "seen_news.json", ".github/workflows/news.yml"):
                path = root / rel
                path.parent.mkdir(parents=True, exist_ok=True)
                path.write_text("[]", encoding="utf-8")
            results = inspect_project(root)
            self.assertIn(("PASS", "json-list", "news_archive.json"), results)
            self.assertIn(("PASS", "json-list", "seen_news.json"), results)

if __name__ == "__main__":
    unittest.main()
