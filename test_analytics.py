import unittest,math
from unittest.mock import patch
from analytics import compute,FUNDS
from app import app
class AnalyticsTests(unittest.TestCase):
    def setUp(self):self.p=dict(fund1='40413765000178',fund2='28428077000186',end='2026-10-31',horizon=24,target=1000000)
    def test_monthly_compounding_and_capital(self):
        r=compute(self.p)
        for i,s in enumerate(r['stats']):
            self.assertAlmostEqual(math.prod(1+m['values'][i]/100 for m in r['monthly']),1+s['return_pct']/100,places=10)
            self.assertAlmostEqual(s['required_initial']*(1+s['return_pct']/100),1000000,places=6)
        self.assertEqual(r['start'],'2024-10-31');self.assertEqual(r['end'],'2026-10-30')
    def test_missing_daily_quota_disables_risk(self):
        from data_store import read
        import copy
        d=copy.deepcopy(read());d['funds'][self.p['fund1']].pop('2025-01-15')
        with patch('analytics.read',return_value=d):r=compute(self.p)
        self.assertFalse(r['risk_complete']);self.assertIsNone(r['stats'][0]['sharpe']);self.assertIsNone(r['stats'][0]['volatility'])
    def test_pdf_reuses_server_report(self):
        c=app.test_client();r=c.post('/api/compare',json=self.p);self.assertEqual(r.status_code,200)
        with patch('app.compute',side_effect=AssertionError('PDF must not recalculate')),patch('data_store.get',side_effect=AssertionError('PDF must not download')):
            pdf=c.post('/api/pdf',json={'report_id':r.json['report_id']});self.assertEqual(pdf.status_code,200);self.assertTrue(pdf.data.startswith(b'%PDF'))
        self.assertEqual(c.post('/api/pdf',json={'report_id':'missing'}).status_code,410)
    def test_invalid_and_insufficient_inputs(self):
        for update in [dict(fund2=self.p['fund1']),dict(target=float('nan')),dict(horizon=7),dict(end='2050-01-01'),dict(horizon=60)]:
            with self.assertRaises(ValueError):compute(self.p|update)
    def test_sharpe_against_independent_calculation(self):
        from data_store import read
        r=compute(self.p);s=read()['funds'][self.p['fund1']];dates=[x['date'] for x in r['curve']];cdi=read()['cdi'];excess=[s[b]/s[a]-1-cdi[b] for a,b in zip(dates,dates[1:])];mean=sum(excess)/len(excess);sd=(sum((x-mean)**2 for x in excess)/(len(excess)-1))**.5
        self.assertAlmostEqual(r['stats'][0]['sharpe'],mean/sd*252**.5)
if __name__=='__main__':unittest.main()
