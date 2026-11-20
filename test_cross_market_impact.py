import unittest
from cross_market_impact import classify_event, analyze_cross_market_impact
class ImpactTests(unittest.TestCase):
 def test_inflation(self):
  r=analyze_cross_market_impact('US Core CPI inflation report',country='US'); self.assertIn('XAUUSD',r['symbols']); self.assertIn('DXY',r['symbols']); self.assertIn('inflation',r['categories'])
 def test_oil_and_cad(self):
  r=analyze_cross_market_impact('OPEC cuts oil production',currency='CAD'); self.assertIn('USOIL',r['symbols']); self.assertIn('USDCAD',r['symbols'])
 def test_china(self):
  r=analyze_cross_market_impact('China growth and PBOC policy'); self.assertIn('china',r['categories']); self.assertIn('CNY',r['symbols'])
 def test_unknown(self):
  r=analyze_cross_market_impact('A company announces new office'); self.assertEqual(r['categories'],[]); self.assertEqual(r['direct_effect'],[])
 def test_crypto(self):
  r=analyze_cross_market_impact('Bitcoin and crypto markets'); self.assertIn('BTCUSD',r['symbols']); self.assertIn('crypto',r['categories'])
if __name__=='__main__': unittest.main()
