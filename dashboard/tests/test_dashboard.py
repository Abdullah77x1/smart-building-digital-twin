"""Meaningful integration checks for data arithmetic, leakage and paired experiments."""
import json
import sys
import tempfile
import threading
import unittest
from datetime import date
from http.server import ThreadingHTTPServer
from pathlib import Path
from urllib.error import HTTPError
from urllib.request import Request, urlopen

import numpy as np
import pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from service import DashboardService, summary
from app import make_handler
from simulator.building_simulator import simulate


class DashboardTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.tmp = tempfile.TemporaryDirectory()
        cls.path = Path(cls.tmp.name) / 'history.csv'
        simulate(date(2025,7,14),date(2025,7,17),cls.path)
        cls.service = DashboardService(cls.path)

    @classmethod
    def tearDownClass(cls):
        cls.tmp.cleanup()

    def test_energy_reconciles_and_dates_are_inclusive(self):
        result = self.service.history('2025-07-15','2025-07-15')
        s=result['summary']
        self.assertEqual(s['rows'],288)
        self.assertAlmostEqual(s['total_energy_kwh'],s['hvac_energy_kwh']+s['lighting_energy_kwh']+s['plug_energy_kwh'],places=5)
        self.assertAlmostEqual(s['total_energy_kwh'],self.service.select('2025-07-15','2025-07-15').total_power_kw.sum()/12,places=5)
        self.assertEqual(len(pd.read_csv(__import__('io').StringIO(self.service.export('2025-07-15','2025-07-15')))),288)

    def test_unoccupied_comfort_is_not_reported_as_100_percent(self):
        frame=self.service.frame().copy()
        frame['occupancy_count']=0
        s=summary(frame,self.service.cfg)
        self.assertIsNone(s['comfort_compliance_pct'])
        self.assertIsNone(s['occupied_mean_temp_c'])

    def test_range_and_scenario_validation(self):
        for start,end in [('2025-07-16','2025-07-15'),('bad','2025-07-15'),('2020-01-01','2025-07-15')]:
            with self.assertRaises(ValueError):self.service.history(start,end)
        for shift in [float('nan'),float('inf'),4,'bad']:
            with self.assertRaises(ValueError):self.service.scenario('2025-07-15','2025-07-15',shift)
        with self.assertRaises(ValueError):self.service.scenario('2025-01-01','2025-03-01')
        with self.assertRaises(ValueError):self.service.scenario('2025-07-15','2025-07-15',0,'bad')

    def test_missing_data_and_gaps_rejected(self):
        with self.assertRaises(FileNotFoundError):DashboardService(Path(self.tmp.name)/'absent.csv').frame()
        bad=self.service.frame().drop(index=2)
        path=Path(self.tmp.name)/'gap.csv';bad.to_csv(path,index=False)
        with self.assertRaisesRegex(ValueError,'consecutive'):DashboardService(path).frame()
        bad=self.service.frame().copy();bad.loc[3,'hvac_power_kw']=float('nan');bad.to_csv(path,index=False)
        with self.assertRaisesRegex(ValueError,'non-finite'):DashboardService(path).frame()

    def test_forecast_has_twelve_outputs_and_exact_future_alignment(self):
        f=self.service.forecast('2025-07-15T09:00')
        self.assertEqual([p['minutes'] for p in f['forecasts']],[5,10,15,30])
        self.assertEqual(sum(len(p['predicted']) for p in f['forecasts']),12)
        self.assertEqual(f['input_features'],36)
        for p in f['forecasts']:
            row=self.service.frame().loc[self.service.frame().timestamp.eq(pd.Timestamp(p['timestamp']))].iloc[0]
            self.assertEqual(p['actual']['indoor_temp_c'],row.indoor_temp_c)
            self.assertTrue(all(np.isfinite(v) for v in p['predicted'].values()))

    def test_predictions_do_not_change_if_future_observations_change(self):
        original=self.service.forecast('2025-07-15 09:00')
        changed=DashboardService(self.path)
        changed._frame=self.service.frame().copy()
        future=changed._frame.timestamp>pd.Timestamp('2025-07-15 09:00')
        changed._frame.loc[future,'indoor_temp_c']+=9
        altered=changed.forecast('2025-07-15 09:00')
        for a,b in zip(original['forecasts'],altered['forecasts']):
            self.assertEqual(a['predicted'],b['predicted'])
            self.assertNotEqual(a['actual'],b['actual'])

    def test_forecast_requires_history_and_handles_missing_actuals(self):
        with self.assertRaisesRegex(ValueError,'60 minutes'):self.service.forecast('2025-07-14 00:00')
        with self.assertRaises(ValueError):self.service.forecast('2025-07-15 09:02')
        last=self.service.forecast('2025-07-16 23:55')
        self.assertTrue(all(p['actual'] is None for p in last['forecasts']))

    def test_identity_scenario_has_zero_difference(self):
        r=self.service.scenario('2025-07-15','2025-07-15',0,'scheduled')
        self.assertEqual(r['energy_saved_kwh'],0)
        self.assertEqual(r['baseline'],r['candidate'])

    def test_scenario_preserves_drivers_and_exposes_comfort_tradeoff(self):
        r=self.service.scenario('2025-07-14','2025-07-16',3,'occupancy')
        for a,b in zip(r['baseline']['points'],r['candidate']['points']):
            self.assertEqual(a['outdoor_temp_c'],b['outdoor_temp_c'])
            self.assertEqual(a['occupancy_count'],b['occupancy_count'])
            self.assertEqual(a['plug_power_kw'],b['plug_power_kw'])
        self.assertGreater(r['candidate']['summary']['comfort_violation_minutes'],0)
        self.assertFalse(r['comfort_pass'])
        self.assertNotEqual(r['energy_saved_kwh'],0)

    def test_http_routes_and_invalid_requests(self):
        server=ThreadingHTTPServer(('127.0.0.1',0),make_handler(self.service))
        thread=threading.Thread(target=server.serve_forever,daemon=True);thread.start()
        url=f'http://127.0.0.1:{server.server_port}'
        try:
            with urlopen(url+'/api/meta') as r:self.assertEqual(json.load(r)['rows'],864)
            with urlopen(url+'/') as r:self.assertIn(b'buildingtwin',r.read().replace(b'<span class="brand-light">',b'').replace(b'</span>',b''))
            for path in ['/api/history','/../requirements.txt','/service.py']:
                with self.assertRaises(HTTPError):urlopen(url+path)
            req=Request(url+'/api/scenario',data=b'{"start":"bad"}',headers={'Content-Type':'application/json'})
            with self.assertRaises(HTTPError) as e:urlopen(req)
            self.assertEqual(e.exception.code,400)
            req=Request(url+'/api/scenario',data=b'{}',headers={'Content-Type':'application/json','Origin':'https://example.com'})
            with self.assertRaises(HTTPError) as e:urlopen(req)
            self.assertEqual(e.exception.code,403)
        finally:
            server.shutdown();server.server_close();thread.join()

if __name__=='__main__':unittest.main(verbosity=2)
