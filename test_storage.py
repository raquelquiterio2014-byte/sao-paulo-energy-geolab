import copy
import json
import os
from pathlib import Path
import sqlite3
import subprocess
import sys
import tempfile
import unittest
from unittest.mock import patch
from fastapi.testclient import TestClient
import app
from storage import Store


class PersistenceTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.db = Path(self.tmp.name) / 'data' / 'test.sqlite3'
        self.patch = patch.object(app, 'DB_PATH', self.db)
        self.patch.start()
        self.client = TestClient(app.app)
        self.data = app.demo()

    def tearDown(self):
        self.client.close()
        self.patch.stop()
        self.tmp.cleanup()

    def post_dataset(self, name='Uploaded fixture'):
        return self.client.post('/api/datasets',json={'name':name,'dataset':self.data})

    def test_first_run_seeds_demo_once(self):
        first=self.client.get('/api/state').json()
        second=self.client.get('/api/state').json()
        self.assertEqual(first['id'],second['id'])
        self.assertEqual(len(self.client.get('/api/datasets').json()),1)

    def test_import_and_restart_process(self):
        self.data['features'][0]['properties']['name']='Persistent fixture'
        saved=self.post_dataset().json()
        env={**os.environ,'ENERGY_DB_PATH':str(self.db)}
        result=subprocess.check_output([sys.executable,'-c',
            "import json,app; print(json.dumps(app.saved_state()))"],cwd=app.BASE,env=env,text=True)
        restored=json.loads(result)
        self.assertEqual(restored['id'],saved['id'])
        self.assertEqual(restored['dataset'],saved['dataset'])

    def test_exact_reimport_reuses_snapshot(self):
        first=self.post_dataset('first').json()
        second=self.post_dataset('second').json()
        self.assertEqual(first['id'],second['id'])
        self.assertEqual(second['name'],'first')
        self.assertEqual(len(self.client.get('/api/datasets').json()),1)

    def test_changed_data_creates_snapshot(self):
        first=self.post_dataset().json()
        self.data['features'][0]['properties']['capacity_mw']=999
        second=self.post_dataset().json()
        self.assertNotEqual(first['id'],second['id'])
        self.assertNotEqual(first['sha256'],second['sha256'])
        self.assertEqual(Store(self.db).dataset(first['id'])['dataset']['features'][0]['properties']['capacity_mw'],30)

    def test_invalid_import_keeps_active_dataset(self):
        first=self.post_dataset().json()
        self.data['features'][0]['properties']['state']='MG'
        self.assertEqual(self.post_dataset().status_code,422)
        self.assertEqual(self.client.get('/api/state').json()['id'],first['id'])
        self.assertEqual(len(self.client.get('/api/datasets').json()),1)

    def test_saved_analysis_survives_process_restart(self):
        ds=self.post_dataset().json()
        saved=self.client.post('/api/analyses',json={'dataset_id':ds['id'],'plant_id':'DEMO-SP-01-plant'}).json()
        self.assertEqual(saved['report']['dataset_sha256'],ds['sha256'])
        env={**os.environ,'ENERGY_DB_PATH':str(self.db)}
        result=subprocess.check_output([sys.executable,'-c',
            f"import json,app; print(json.dumps(app.store().analysis({saved['id']})))"],cwd=app.BASE,env=env,text=True)
        self.assertEqual(json.loads(result),saved)
        self.assertEqual(self.client.get('/api/analyses').json()['total'],1)

    def test_history_keeps_original_snapshot(self):
        ds=self.post_dataset().json()
        report=self.client.post('/api/analyses',json={'dataset_id':ds['id'],'plant_id':'DEMO-SP-01-plant'}).json()
        self.data['features'][0]['geometry']['coordinates']=[-48,-24]
        self.post_dataset()
        old=self.client.get(f"/api/analyses/{report['id']}").json()
        self.assertEqual(old,report)
        loaded=self.client.post(f"/api/datasets/{ds['id']}/activate",json={}).json()
        self.assertEqual(loaded['dataset'],ds['dataset'])

    def test_demo_does_not_delete_import_or_history(self):
        self.data['features'][0]['properties']['name']='custom'
        ds=self.post_dataset().json()
        self.client.post('/api/analyses',json={'dataset_id':ds['id'],'plant_id':'DEMO-SP-01-plant'})
        demo=self.client.post('/api/demo/activate',json={})
        self.assertEqual(demo.status_code,200)
        self.assertEqual(len(self.client.get('/api/datasets').json()),2)
        self.assertEqual(self.client.get('/api/analyses').json()['total'],1)

    def test_unknown_ids(self):
        self.assertEqual(self.client.get('/api/analyses/999').status_code,404)
        self.assertEqual(self.client.post('/api/datasets/999/activate',json={}).status_code,404)
        self.assertEqual(self.client.post('/api/analyses',json={'dataset_id':999,'plant_id':'missing'}).status_code,404)

    def test_invalid_analysis_is_not_saved(self):
        ds=self.post_dataset().json()
        self.assertEqual(self.client.post('/api/analyses',json={'dataset_id':ds['id'],'plant_id':'missing'}).status_code,422)
        self.assertEqual(self.client.get('/api/analyses').json()['total'],0)

    def test_history_pagination(self):
        ds=self.post_dataset().json()
        for _ in range(3):
            self.client.post('/api/analyses',json={'dataset_id':ds['id'],'plant_id':'DEMO-SP-01-plant'})
        page=self.client.get('/api/analyses?limit=2&offset=0').json()
        last=self.client.get('/api/analyses?limit=2&offset=2').json()
        self.assertEqual(page['total'],3)
        self.assertEqual(len(page['items']),2)
        self.assertEqual(len(last['items']),1)
        self.assertGreater(page['items'][0]['id'],last['items'][0]['id'])
        self.assertEqual(self.client.get('/api/analyses?limit=101').status_code,422)

    def test_hash_mismatch_rejected(self):
        db=Store(self.db)
        saved=db.save_dataset(self.data,'demo')
        report=app.nearest(self.data,'DEMO-SP-01-plant')
        report['dataset_sha256']='incorrect'
        with self.assertRaises(ValueError): db.save_analysis(saved['id'],report)
        self.assertEqual(db.history()['total'],0)

    def test_sql_in_name_is_literal(self):
        name="dataset'); DROP TABLE datasets; --"
        ds=self.post_dataset(name).json()
        self.assertEqual(ds['name'],name)
        self.assertEqual(len(Store(self.db).datasets()),1)

    def test_database_failure_visible(self):
        self.db.parent.mkdir(parents=True)
        self.db.write_text('not a database')
        response=self.client.get('/api/state')
        self.assertEqual(response.status_code,503)
        self.assertIn('Database unavailable',response.json()['detail'])

    def test_foreign_key_and_rollback(self):
        db=Store(self.db)
        with self.assertRaises(sqlite3.IntegrityError):
            with db.connect() as con:
                con.execute("INSERT INTO settings VALUES(1,999)")
        self.assertIsNone(db.current())

    def test_cross_origin_write_denied(self):
        response=self.client.post('/api/datasets',json={'name':'x','dataset':self.data},headers={'Origin':'https://example.org'})
        self.assertEqual(response.status_code,403)
        self.assertEqual(self.post_dataset().status_code,200)


if __name__ == '__main__': unittest.main(verbosity=2)
