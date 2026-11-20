import unittest
from breaking_news_analysis import score_breaking_news, format_breaking_badge

class BreakingNewsScoringTests(unittest.TestCase):
 def test_emergency_rate_decision_scores_urgent(self):
  r=score_breaking_news("Emergency rate decision announced")
  self.assertGreaterEqual(r["score"],60); self.assertEqual(r["level"],"عاجل")
 def test_non_market_news_is_not_breaking(self):
  r=score_breaking_news("A company opens a new office")
  self.assertLess(r["score"],r["threshold"])
 def test_cpi_surprise_medium(self):
  r=score_breaking_news("CPI surprise impacts dollar")
  self.assertGreaterEqual(r["score"],r["threshold"])
 def test_badge(self):
  self.assertIn("/100",format_breaking_badge(score_breaking_news("bank collapse")))

if __name__ == "__main__": unittest.main()
