import unittest
from datetime import datetime, timezone
from monitor_health import check_runs, compose_transition_messages
class MonitorTests(unittest.TestCase):
 def test_recent_success(self):
  now=datetime(2026,11,20,12,tzinfo=timezone.utc)
  self.assertEqual(check_runs([{"status":"completed","conclusion":"success","updated_at":"2026-11-20T11:50:00Z"}],now,40),[])
 def test_stale_success(self):
  now=datetime(2026,11,20,12,tzinfo=timezone.utc)
  self.assertTrue(check_runs([{"status":"completed","conclusion":"success","updated_at":"2026-11-20T11:00:00Z"}],now,40))
 def test_failure(self):
  now=datetime(2026,11,20,12,tzinfo=timezone.utc)
  runs=[{"status":"completed","conclusion":"failure","updated_at":"2026-11-20T11:50:00Z"},{"status":"completed","conclusion":"success","updated_at":"2026-11-20T11:45:00Z"}]
  self.assertTrue(check_runs(runs,now,40))
 def test_no_history(self):
  self.assertTrue(check_runs([],datetime(2026,11,20,12,tzinfo=timezone.utc),40))
 def test_alert_transition(self):
  report=[{"label":"News","healthy":False,"issues":["fail"]}]
  state,msg=compose_transition_messages(report,{})
  self.assertEqual(len(msg),1)
  self.assertEqual(compose_transition_messages(report,state)[1],[])
  self.assertIn("Recovery",compose_transition_messages([{"label":"News","healthy":True,"issues":[]}],state)[1][0])
if __name__=="__main__": unittest.main()
