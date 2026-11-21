import os
import unittest
from unittest.mock import patch
from goldnewsbot.config import Settings

class ConfigTests(unittest.TestCase):
    def test_safe_defaults(self):
        with patch.dict(os.environ, {}, clear=True):
            settings = Settings.from_env()
        self.assertEqual(settings.app_env, "development")
        self.assertFalse(settings.telegram_ready)

    def test_invalid_environment_rejected(self):
        with patch.dict(os.environ, {"APP_ENV": "production-ish"}, clear=True):
            with self.assertRaises(ValueError):
                Settings.from_env()

    def test_credentials_not_required_for_dry_setup(self):
        with patch.dict(os.environ, {"APP_ENV": "test"}, clear=True):
            self.assertFalse(Settings.from_env().telegram_ready)

if __name__ == "__main__":
    unittest.main()
