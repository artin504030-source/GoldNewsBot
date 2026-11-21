import os
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from app.core.config import Settings
from app.platform.health import health_report
from goldnewsbot.storage import SQLiteNewsRepository


class InfrastructureTests(unittest.TestCase):
    def test_sqlite_round_trip_and_integrity(self):
        with tempfile.TemporaryDirectory() as directory:
            repo = SQLiteNewsRepository(Path(directory) / "state" / "news.sqlite3")
            self.assertTrue(repo.check())
            self.assertFalse(repo.has_seen("abc"))
            repo.mark_seen("abc")
            self.assertTrue(repo.has_seen("abc"))

    def test_health_report_does_not_expose_secrets(self):
        with tempfile.TemporaryDirectory() as directory:
            env = {
                "APP_ENV": "test",
                "DATABASE_PATH": str(Path(directory) / "health.sqlite3"),
                "TELEGRAM_BOT_TOKEN": "super-secret-token",
                "TELEGRAM_CHAT_ID": "private-chat",
            }
            with patch.dict(os.environ, env, clear=True):
                report = health_report(Settings.from_env())
            rendered = repr(report)
            self.assertEqual(report["status"], "ok")
            self.assertEqual(report["checks"]["database"], "ok")
            self.assertNotIn("super-secret-token", rendered)
            self.assertNotIn("private-chat", rendered)


if __name__ == "__main__":
    unittest.main()
