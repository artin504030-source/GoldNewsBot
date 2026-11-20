import unittest
from unittest.mock import patch
from datetime import datetime, timezone, timedelta
import importlib.util
from pathlib import Path

MODULE = Path(__file__).with_name("monitor_health.py")
spec = importlib.util.spec_from_file_location("monitor_health", MODULE)
monitor = importlib.util.module_from_spec(spec)
spec.loader.exec_module(monitor)

class MonitorHealthTests(unittest.TestCase):
    def setUp(self):
        self.sent = []
        monitor.send_telegram = lambda message: self.sent.append(message)
        self.state = {"active_alerts": {}}
        self.now = datetime.now(timezone.utc)

    def run_record(self, run_id, conclusion="failure", minutes_ago=5, event="workflow_dispatch", branch="main"):
        return {"id": run_id, "event": event, "head_branch": branch, "status": "completed", "conclusion": conclusion,
                "created_at": (self.now - timedelta(minutes=minutes_ago)).isoformat(),
                "html_url": "https://github.com/example/run"}

    def test_three_consecutive_failures_alert_once(self):
        records = [self.run_record(i) for i in (3, 2, 1)]
        monitor.get_scheduled_runs = lambda _: records
        monitor.inspect_workflows(self.state, self.now)
        self.assertTrue(any("سه اجرای زمان‌بندی‌شده پیاپی ناموفق" in m for m in self.sent))
        n = len(self.sent)
        monitor.inspect_workflows(self.state, self.now)
        self.assertEqual(len(self.sent), n)

    def test_two_failures_do_not_escalate(self):
        records = [self.run_record(2), self.run_record(1), self.run_record(0, "success")]
        monitor.get_scheduled_runs = lambda _: records
        monitor.inspect_workflows(self.state, self.now)
        self.assertFalse(any("سه اجرای زمان‌بندی‌شده پیاپی ناموفق" in m for m in self.sent))

    def test_external_dispatch_runs_are_included_but_other_events_excluded(self):
        payload = {"workflow_runs": [
            self.run_record(3, "success", event="workflow_dispatch"),
            self.run_record(2, "success", event="schedule"),
            self.run_record(1, "success", event="push"),
            self.run_record(0, "success", event="workflow_dispatch", branch="feature/test"),
        ]}
        class Response:
            def raise_for_status(self):
                pass
            def json(self):
                return payload
        monitor.GITHUB_TOKEN = "test-token"
        with patch.object(monitor.requests, "get", return_value=Response()):
            runs = monitor.get_scheduled_runs("news.yml")
        self.assertEqual([r["id"] for r in runs], [3, 2])

    def test_recent_source_failure_alerts_and_recovers(self):
        import tempfile, json
        with tempfile.TemporaryDirectory() as folder:
            original = monitor.SOURCE_PATH
            monitor.SOURCE_PATH = Path(folder) / "source_health.json"
            data = {"sources": {"BLS": {"last_status": "failure", "last_checked_utc": self.now.isoformat(), "last_error": "timeout"}}}
            monitor.SOURCE_PATH.write_text(json.dumps(data), encoding="utf-8")
            monitor.inspect_sources(self.state, self.now)
            self.assertTrue(any("اختلال در منبع خبری" in m for m in self.sent))
            data["sources"]["BLS"]["last_status"] = "success"
            monitor.SOURCE_PATH.write_text(json.dumps(data), encoding="utf-8")
            monitor.inspect_sources(self.state, self.now)
            self.assertTrue(any("دوباره موفق ثبت شد" in m for m in self.sent))
            monitor.SOURCE_PATH = original

if __name__ == "__main__":
    unittest.main()
