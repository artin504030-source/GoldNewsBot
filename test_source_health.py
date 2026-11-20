import json
import tempfile
import unittest
from pathlib import Path
from source_health import record_source_check, summarize_source_health, format_source_health

class SourceHealthTests(unittest.TestCase):
    def test_success_then_failure_keeps_counters_and_latest_state(self):
        with tempfile.TemporaryDirectory() as d:
            path = Path(d) / "health.json"
            record_source_check("BLS", True, 4, path=path, checked_at="2026-11-20T10:00:00+00:00")
            record_source_check("BLS", False, error="timeout", path=path, checked_at="2026-11-20T10:15:00+00:00")
            summary = summarize_source_health(path)
            self.assertEqual(summary["healthy_count"], 0)
            self.assertEqual(summary["failed_count"], 1)
            item = summary["sources"]["BLS"]
            self.assertEqual(item["success_count"], 1)
            self.assertEqual(item["failure_count"], 1)
            self.assertEqual(item["last_error"], "timeout")
    def test_independent_sources_counted(self):
        with tempfile.TemporaryDirectory() as d:
            path = Path(d) / "health.json"
            record_source_check("Fed", True, 2, path=path)
            record_source_check("ECB", False, error="503", path=path)
            summary = summarize_source_health(path)
            self.assertEqual((summary["checked_count"], summary["healthy_count"], summary["failed_count"]), (2, 1, 1))
    def test_report_warns_about_old_unchecked_status(self):
        text = format_source_health({"healthy_count":1,"failed_count":0,"checked_count":1,"updated_at_utc":None,"sources":{"Fed":{"last_status":"success","last_entries_count":2}}})
        self.assertIn("آخرین تلاش ثبت‌شده", text)
        self.assertIn("Fed", text)

if __name__ == "__main__": unittest.main()
