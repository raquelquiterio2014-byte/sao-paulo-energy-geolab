"""SQLite persistence for immutable dataset snapshots and analysis reports."""
from contextlib import contextmanager
from datetime import datetime, timezone
from pathlib import Path
import hashlib
import json
import sqlite3


def canonical(data):
    return json.dumps(data, sort_keys=True, ensure_ascii=False, allow_nan=False)


def now():
    return datetime.now(timezone.utc).isoformat(timespec='microseconds')


class Store:
    def __init__(self, path):
        self.path = Path(path)
        self.path.parent.mkdir(parents=True, exist_ok=True)
        with self.connect() as db:
            version = db.execute('PRAGMA user_version').fetchone()[0]
            if version not in (0, 1):
                raise sqlite3.DatabaseError('Unsupported database schema version')
            db.executescript('''
                CREATE TABLE IF NOT EXISTS datasets (
                    id INTEGER PRIMARY KEY,
                    name TEXT NOT NULL,
                    sha256 TEXT NOT NULL UNIQUE,
                    created_at TEXT NOT NULL,
                    feature_count INTEGER NOT NULL,
                    synthetic_count INTEGER NOT NULL,
                    geojson TEXT NOT NULL
                );
                CREATE TABLE IF NOT EXISTS analyses (
                    id INTEGER PRIMARY KEY,
                    dataset_id INTEGER NOT NULL REFERENCES datasets(id),
                    plant_id TEXT NOT NULL,
                    plant_name TEXT NOT NULL,
                    created_at TEXT NOT NULL,
                    report TEXT NOT NULL
                );
                CREATE TABLE IF NOT EXISTS settings (
                    id INTEGER PRIMARY KEY CHECK(id=1),
                    active_dataset_id INTEGER NOT NULL REFERENCES datasets(id)
                );
                CREATE INDEX IF NOT EXISTS analyses_dataset ON analyses(dataset_id);
                PRAGMA user_version=1;
            ''')

    @contextmanager
    def connect(self):
        db = sqlite3.connect(self.path, timeout=15)
        db.row_factory = sqlite3.Row
        db.execute('PRAGMA foreign_keys=ON')
        try:
            with db:
                yield db
        finally:
            db.close()

    def save_dataset(self, data, name, activate=True):
        encoded = canonical(data)
        digest = hashlib.sha256(encoded.encode('utf-8')).hexdigest()
        synthetic = sum(f['properties']['data_status'] == 'synthetic' for f in data['features'])
        with self.connect() as db:
            db.execute('''INSERT INTO datasets(name,sha256,created_at,feature_count,synthetic_count,geojson)
                          VALUES(?,?,?,?,?,?) ON CONFLICT(sha256) DO NOTHING''',
                       (name, digest, now(), len(data['features']), synthetic, encoded))
            row = db.execute('SELECT id FROM datasets WHERE sha256=?', (digest,)).fetchone()
            dataset_id = row['id']
            if activate:
                db.execute('''INSERT INTO settings(id,active_dataset_id) VALUES(1,?)
                              ON CONFLICT(id) DO UPDATE SET active_dataset_id=excluded.active_dataset_id''',
                           (dataset_id,))
        return self.dataset(dataset_id)

    def dataset(self, dataset_id):
        with self.connect() as db:
            row = db.execute('SELECT * FROM datasets WHERE id=?', (dataset_id,)).fetchone()
        if row is None:
            raise KeyError('Dataset not found')
        result = dict(row)
        result['dataset'] = json.loads(result.pop('geojson'))
        return result

    def activate(self, dataset_id):
        result = self.dataset(dataset_id)
        with self.connect() as db:
            db.execute('''INSERT INTO settings(id,active_dataset_id) VALUES(1,?)
                          ON CONFLICT(id) DO UPDATE SET active_dataset_id=excluded.active_dataset_id''',
                       (dataset_id,))
        return result

    def current(self):
        with self.connect() as db:
            row = db.execute('SELECT active_dataset_id FROM settings WHERE id=1').fetchone()
        return self.dataset(row[0]) if row else None

    def datasets(self):
        with self.connect() as db:
            return [dict(row) for row in db.execute('''SELECT id,name,sha256,created_at,
                    feature_count,synthetic_count FROM datasets ORDER BY id DESC''')]

    def save_analysis(self, dataset_id, report):
        snapshot = self.dataset(dataset_id)
        if snapshot['sha256'] != report['dataset_sha256']:
            raise ValueError('Report does not match the saved dataset')
        stamp = now()
        with self.connect() as db:
            cursor = db.execute('''INSERT INTO analyses(dataset_id,plant_id,plant_name,created_at,report)
                                   VALUES(?,?,?,?,?)''',
                                (dataset_id, report['plant']['id'], report['plant']['name'], stamp, canonical(report)))
            analysis_id = cursor.lastrowid
        return self.analysis(analysis_id)

    def analysis(self, analysis_id):
        with self.connect() as db:
            row = db.execute('SELECT * FROM analyses WHERE id=?', (analysis_id,)).fetchone()
        if row is None:
            raise KeyError('Analysis not found')
        result = dict(row)
        result['report'] = json.loads(result['report'])
        return result

    def history(self, limit=50, offset=0):
        with self.connect() as db:
            total = db.execute('SELECT COUNT(*) FROM analyses').fetchone()[0]
            rows = db.execute('''SELECT a.id,a.dataset_id,a.plant_name,a.created_at,d.name AS dataset_name,
                                d.synthetic_count,d.feature_count FROM analyses a
                                JOIN datasets d ON d.id=a.dataset_id
                                ORDER BY a.id DESC LIMIT ? OFFSET ?''', (limit, offset))
            return {'items': [dict(row) for row in rows], 'total': total, 'limit': limit, 'offset': offset}
