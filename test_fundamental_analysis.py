import unittest
from fundamental_analysis import analyze_release, identify_indicator

class FundamentalTests(unittest.TestCase):
    def test_cpi_hot(self):
        r=analyze_release({"title":"US Core CPI","actual":3.4,"forecast":3.2,"previous":3.3,"country":"US"})
        self.assertEqual(r["indicator"],"inflation"); self.assertEqual(r["status"],"بالاتر"); self.assertIn("فشار",r["bias"])
        self.assertIn("USD",r["bias"])
    def test_nfp_below_expected_dovish(self):
        r=analyze_release("Nonfarm Payrolls", actual=120, forecast=180, currency="USD")
        self.assertIn("تضعیف",r["bias"])
    def test_unemployment_higher_dovish(self):
        r=analyze_release("Unemployment Rate", actual=4.2, forecast=4.0, currency="USD")
        self.assertEqual(r["status"],"بالاتر"); self.assertIn("تضعیف",r["bias"])
    def test_actual_missing_no_direction(self):
        r=analyze_release("US CPI", forecast=3.0, country="US")
        self.assertEqual(r["status"],"منتظر داده"); self.assertEqual(r["scenarios"],[])
    def test_unknown_indicator(self):
        r=analyze_release("Community Survey", actual=1, forecast=2)
        self.assertEqual(r["indicator"],"unknown"); self.assertEqual(r["scenarios"],[])
    def test_equal_actual_forecast(self):
        r=analyze_release("GDP Growth",actual=2.0,forecast=2.0)
        self.assertEqual(r["status"],"مطابق انتظار"); self.assertEqual(len(r["scenarios"]),1)
    def test_indicator_recognition(self):
        self.assertEqual(identify_indicator("Retail Sales"),"consumer")

if __name__ == "__main__": unittest.main()
