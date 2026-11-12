import unittest,re,json,gzip
from pathlib import Path
from analytics import compute,FUNDS
class CatalogTests(unittest.TestCase):
    def test_all_funds_have_unique_valid_cnpj_and_history(self):
        root=Path(__file__).parent;items=json.loads((root/'funds.json').read_text())
        with gzip.open(root/'snapshot.json.gz','rt') as f:data=json.load(f)
        ids=[re.sub(r'\D','',x['cnpj']) for x in items];self.assertEqual(len(ids),len(set(ids)))
        for c in ids:
            with self.subTest(cnpj=c):
                self.assertEqual(len(c),14);self.assertTrue(data['funds'].get(c),'No quota history')
                for n,w in [(12,[5,4,3,2,9,8,7,6,5,4,3,2]),(13,[6,5,4,3,2,9,8,7,6,5,4,3,2])]:
                    v=sum(int(a)*b for a,b in zip(c[:n],w))%11;self.assertEqual(int(c[n]),0 if v<2 else 11-v)
    def test_safra_santander_same_period_capital(self):
        p=dict(fund1='37332819000166',fund2='18599388000154',end='2026-11-06',horizon=24,target=1000000)
        r=compute(p)
        for x in r['summary']:
            if None in x['returns']:continue
            for v,capital in zip(x['returns'],x['required_initial']):self.assertAlmostEqual(capital*(1+v/100),p['target'],places=6)
            self.assertLessEqual((x['returns'][0]-x['returns'][1])*(x['required_initial'][0]-x['required_initial'][1]),0)
        r36=compute(p|dict(horizon=36));x36=next(x for x in r['summary'] if x['months']==36)
        self.assertGreater(x36['returns'][1],x36['returns'][0]);self.assertLess(x36['required_initial'][1],x36['required_initial'][0])
        for s,v in zip(r36['stats'],x36['required_initial']):self.assertAlmostEqual(s['required_initial'],v)
