import copy
import json
import unittest
from unittest.mock import patch
from fastapi.testclient import TestClient
import app
from app import validate, nearest, distance_km, demo


class EnergyTests(unittest.TestCase):
    def setUp(self):
        self.data = demo()
        self.client = TestClient(app.app)

    def test_equatorial_degree(self):
        self.assertAlmostEqual(distance_km([0, 0], [1, 0]), 111.319490793, places=6)

    def test_identical_point(self):
        self.assertAlmostEqual(distance_km([-47, -23], [-47, -23]), 0, places=9)

    def test_symmetry(self):
        a, b = [-47, -23], [-60, -3]
        self.assertAlmostEqual(distance_km(a, b), distance_km(b, a), places=8)

    def test_duplicate_rejected(self):
        self.data['features'].append(copy.deepcopy(self.data['features'][0]))
        with self.assertRaises(ValueError): validate(self.data)

    def test_nan_rejected(self):
        self.data['features'][0]['geometry']['coordinates'][0] = float('nan')
        with self.assertRaises(ValueError): validate(self.data)

    def test_sp_rejects_other_state(self):
        self.data['features'][0]['properties']['state'] = 'MG'
        with self.assertRaises(ValueError): validate(self.data, 'SP')

    def test_import_requires_source(self):
        p = self.data['features'][0]['properties']
        p['data_status'], p['source'] = 'imported', 'Unknown'
        with self.assertRaises(ValueError): validate(self.data)

    def test_import_accepts_provenance(self):
        p = self.data['features'][0]['properties']
        p['data_status'], p['source'] = 'imported', 'https://example.org/test-fixture'
        self.assertEqual(validate(self.data)['features'][0]['properties']['data_status'], 'imported')

    def test_negative_capacity(self):
        self.data['features'][0]['properties']['capacity_mw'] = -1
        with self.assertRaises(ValueError): validate(self.data)

    def test_missing_capacity_stays_missing(self):
        self.data['features'][0]['properties'].pop('capacity_mw')
        self.assertIsNone(validate(self.data)['features'][0]['properties']['capacity_mw'])

    def test_unknown_plant(self):
        with self.assertRaises(ValueError): nearest(self.data, 'missing')

    def test_sorted_and_unverified(self):
        report = nearest(self.data, self.data['features'][0]['properties']['id'])
        ds = [r['distance_km'] for r in report['results']]
        self.assertEqual(ds, sorted(ds))
        self.assertEqual(len(ds), 5)
        self.assertTrue(all(r['connection_status'] == 'Not verified' for r in report['results']))
        self.assertEqual(len(report['dataset_sha256']), 64)

    def test_measurement_endpoints(self):
        report = nearest(self.data, self.data['features'][0]['properties']['id'])
        for row, feature in zip(report['results'], report['measurements']['features']):
            coords = feature['geometry']['coordinates']
            self.assertAlmostEqual(distance_km(coords[0], self.data['features'][0]['geometry']['coordinates']), 0, places=6)
            self.assertAlmostEqual(distance_km(coords[-1], row['coordinates']), 0, places=6)

    def test_empty_substations(self):
        self.data['features'] = [f for f in self.data['features'] if f['properties']['kind'] == 'plant']
        report = nearest(self.data, self.data['features'][0]['properties']['id'])
        self.assertEqual(report['results'], [])
        self.assertEqual(report['candidate_count'], 0)

    def test_connection_claim_discarded(self):
        self.data['features'][0]['properties']['connection_status'] = 'Verified'
        self.assertNotIn('connection_status', validate(self.data)['features'][0]['properties'])

    def test_date_format(self):
        self.data['features'][0]['properties']['source_date'] = '20261118'
        with self.assertRaises(ValueError): validate(self.data)

    def test_invalid_line(self):
        self.data['features'][2]['geometry']['coordinates'] = [[-47, -23]]
        with self.assertRaises(ValueError): validate(self.data)

    def test_deterministic_hash(self):
        pid = self.data['features'][0]['properties']['id']
        self.assertEqual(nearest(self.data,pid)['dataset_sha256'], nearest(copy.deepcopy(self.data),pid)['dataset_sha256'])

    def test_page_and_javascript(self):
        page = self.client.get('/')
        self.assertEqual(page.status_code, 200)
        self.assertIn('lang="en"', page.text)
        self.assertEqual(self.client.get('/app.js').status_code, 200)

    def test_api_demo_and_config(self):
        self.assertEqual(self.client.get('/api/demo').status_code, 200)
        self.assertEqual(self.client.get('/api/config').json()['port'], app.CONFIG['port'])

    def test_api_validate(self):
        response = self.client.post('/api/validate', json=self.data)
        self.assertEqual(response.status_code, 200)
        self.assertEqual(len(response.json()['features']), len(self.data['features']))

    def test_api_nearest(self):
        response = self.client.post('/api/nearest', json={'dataset':self.data,'plant_id':self.data['features'][0]['properties']['id']})
        self.assertEqual(response.status_code, 200)
        self.assertEqual(len(response.json()['results']), 5)

    def test_api_invalid_input(self):
        self.assertEqual(self.client.post('/api/validate', json=[]).status_code, 422)
        self.assertEqual(self.client.post('/api/nearest', json={}).status_code, 422)
        self.assertEqual(self.client.post('/api/validate', content='{', headers={'Content-Type':'application/json'}).status_code, 422)

    def test_api_content_type(self):
        self.assertEqual(self.client.post('/api/validate', content='{}').status_code, 415)

    def test_api_size_limit(self):
        with patch.object(app, 'MAX_BYTES', 4):
            self.assertEqual(self.client.post('/api/validate', json={'long':1}).status_code, 413)

    def test_brazil_cross_state_candidate(self):
        data = copy.deepcopy(self.data)
        plant, sub = data['features'][0], data['features'][1]
        sub['properties']['state'] = 'MG'
        sub['geometry']['coordinates'] = plant['geometry']['coordinates'][:]
        clean = validate(data, None)
        self.assertEqual(nearest(clean, plant['properties']['id'])['results'][0]['state'], 'MG')


if __name__ == '__main__':
    unittest.main(verbosity=2)
