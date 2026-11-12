import unittest
from unittest.mock import patch
from app import app
from report_pdf import options_for
class ReportOptionsTests(unittest.TestCase):
    def test_periods_and_sections_reach_export_without_changing_cached_report(self):
        c=app.test_client()
        result=c.post('/api/compare',json=dict(fund1='40413765000178',fund2='28428077000186',end='2026-11-06',horizon=24,target=1000000)).json
        choices=dict(windows=[12,24],chart=False,chart_cdi=False,capital=False,risk=True,monthly=False)
        with patch('app.build',return_value=b'%PDF-test') as build:
            self.assertEqual(c.post('/api/pdf',json=dict(report_id=result['report_id'],options=choices)).status_code,200)
            self.assertEqual(build.call_args.args[1],choices)
            self.assertEqual(len(build.call_args.args[0]['summary']),6)
    def test_invalid_options_rejected(self):
        for value in [[],dict(windows=[]),dict(windows=[7]),dict(windows=[True]),dict(chart='false'),dict(chart_cdi='false')]:
            with self.assertRaises(ValueError):options_for(value)
    def test_default_commercial_sections(self):
        o=options_for();self.assertTrue(o['chart']);self.assertTrue(o['chart_cdi']);self.assertTrue(o['capital']);self.assertFalse(o['risk']);self.assertFalse(o['monthly'])
