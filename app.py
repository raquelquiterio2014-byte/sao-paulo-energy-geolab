"""Local educational energy atlas. No electrical connectivity is inferred."""
from pathlib import Path
from datetime import date
from urllib.parse import urlparse
import argparse
import hashlib
import json
import math

from fastapi import FastAPI, HTTPException, Request
from fastapi.responses import HTMLResponse, FileResponse
from fastapi.middleware.trustedhost import TrustedHostMiddleware
from geographiclib.geodesic import Geodesic

BASE = Path(__file__).resolve().parent
CONFIG = json.loads((BASE / 'config.json').read_text(encoding='utf-8'))
REGIONS = {
    **dict.fromkeys('AC AP AM PA RO RR TO'.split(), 'North'),
    **dict.fromkeys('AL BA CE MA PB PE PI RN SE'.split(), 'Northeast'),
    **dict.fromkeys('DF GO MT MS'.split(), 'Central-West'),
    **dict.fromkeys('ES MG RJ SP'.split(), 'Southeast'),
    **dict.fromkeys('PR RS SC'.split(), 'South'),
}
MAX_BYTES = 20 * 1024 * 1024
MAX_FEATURES = 20000


def require(condition, message):
    if not condition:
        raise ValueError(message)


def number(value):
    return (type(value) in (int, float) and math.isfinite(value))


def coordinate(value):
    require(isinstance(value, list) and len(value) == 2,
            'Use two-dimensional coordinates: [longitude, latitude].')
    lon, lat = value
    require(number(lon) and number(lat), 'Coordinates must be finite numbers.')
    require(-180 <= lon <= 180 and -90 <= lat <= 90,
            'Coordinates are outside WGS84 limits.')


def validate(data, scope=None):
    require(isinstance(data, dict), 'The dataset must be an object.')
    require(data.get('type') == 'FeatureCollection', 'Expected a GeoJSON FeatureCollection.')
    require('crs' not in data, 'Convert coordinates to WGS84 and remove crs.')
    features = data.get('features')
    require(isinstance(features, list), 'Missing features array.')
    require(0 < len(features) <= MAX_FEATURES,
            f'Provide between 1 and {MAX_FEATURES} features.')
    ids, normalized, vertices = set(), [], 0
    keys = ('id', 'name', 'kind', 'state', 'municipality',
            'source', 'source_date', 'data_status')
    for i, feature in enumerate(features, 1):
        prefix = f'Feature {i}: '
        require(isinstance(feature, dict), prefix + 'invalid object.')
        require(feature.get('type') == 'Feature', prefix + 'invalid type.')
        p, g = feature.get('properties'), feature.get('geometry')
        require(isinstance(p, dict) and isinstance(g, dict),
                prefix + 'properties and geometry are required.')
        for key in keys:
            require(isinstance(p.get(key), str) and 0 < len(p[key].strip()) <= 1000,
                    prefix + f'invalid or missing {key}.')
        require(p['id'] not in ids, prefix + 'duplicate id.')
        ids.add(p['id'])
        require(p['kind'] in ('plant', 'substation', 'line'), prefix + 'invalid kind.')
        require(p['state'] in REGIONS, prefix + 'invalid Brazilian state code.')
        if scope:
            require(p['state'] == scope, prefix + f'this edition accepts only {scope}.')
        require(p['data_status'] in ('synthetic', 'imported'), prefix + 'invalid data_status.')
        try:
            parsed_date = date.fromisoformat(p['source_date'])
            require(parsed_date.isoformat() == p['source_date'], 'Invalid date format.')
        except ValueError:
            raise ValueError(prefix + 'source_date must use YYYY-MM-DD.')
        if p['data_status'] == 'imported':
            source = urlparse(p['source'])
            require(source.scheme in ('http', 'https') and bool(source.netloc),
                    prefix + 'imported records require a source URL.')
        for key in ('capacity_mw', 'voltage_kv'):
            value = p.get(key)
            require(value is None or (number(value) and value >= 0),
                    prefix + f'{key} must be null or a nonnegative number.')
        if p['kind'] == 'line':
            require(g.get('type') == 'LineString', prefix + 'line must be LineString.')
            points = g.get('coordinates')
            require(isinstance(points, list) and len(points) >= 2,
                    prefix + 'a line needs at least two coordinates.')
            vertices += len(points)
            require(vertices <= 250000, 'Maximum of 250,000 vertices exceeded.')
            for point in points:
                coordinate(point)
        else:
            require(g.get('type') == 'Point', prefix + 'plant/substation must be Point.')
            coordinate(g.get('coordinates'))
            vertices += 1
        require(vertices <= 250000, 'Maximum of 250,000 vertices exceeded.')
        if p['kind'] == 'plant':
            require(isinstance(p.get('fuel'), str) and 0 < len(p['fuel'].strip()) <= 100,
                    prefix + 'plants require a fuel value.')
        clean = {key: p[key] for key in keys}
        clean.update(region=REGIONS[p['state']],
                     fuel=p['fuel'] if p['kind'] == 'plant' else '',
                     capacity_mw=p.get('capacity_mw'), voltage_kv=p.get('voltage_kv'))
        normalized.append({'type': 'Feature', 'properties': clean,
                           'geometry': {'type': g['type'], 'coordinates': g['coordinates']}})
    return {'type': 'FeatureCollection', 'features': normalized}


def distance_km(a, b):
    lon1, lat1 = a
    lon2, lat2 = b
    return Geodesic.WGS84.Inverse(lat1, lon1, lat2, lon2)['s12'] / 1000


def nearest(data, plant_id):
    plants = [f for f in data['features'] if f['properties']['kind'] == 'plant'
              and f['properties']['id'] == plant_id]
    require(len(plants) == 1, 'Select a valid plant.')
    plant = plants[0]
    origin = plant['geometry']['coordinates']
    candidates = []
    for f in data['features']:
        p = f['properties']
        if p['kind'] != 'substation':
            continue
        target = f['geometry']['coordinates']
        candidates.append({
            'plant_id': plant_id, 'substation_id': p['id'], 'name': p['name'],
            'state': p['state'], 'municipality': p['municipality'],
            'distance_km': distance_km(origin, target), 'source': p['source'],
            'source_date': p['source_date'], 'data_status': p['data_status'],
            'connection_status': 'Not verified', 'coordinates': target,
        })
    candidates.sort(key=lambda item: (item['distance_km'], item['substation_id']))
    results, paths = candidates[:5], []
    for result in results:
        lon1, lat1 = origin
        lon2, lat2 = result['coordinates']
        line = Geodesic.WGS84.InverseLine(lat1, lon1, lat2, lon2)
        points = []
        for step in range(33):
            position = line.Position(line.s13 * step / 32)
            points.append([position['lon2'], position['lat2']])
        paths.append({'type': 'Feature', 'properties': {
            'kind': 'measurement', 'label': 'Geodesic measurement, not a transmission line'},
            'geometry': {'type': 'LineString', 'coordinates': points}})
    canonical = json.dumps(data, sort_keys=True, ensure_ascii=False, allow_nan=False).encode('utf-8')
    return {
        'plant': plant['properties'], 'results': results,
        'measurements': {'type': 'FeatureCollection', 'features': paths},
        'dataset_sha256': hashlib.sha256(canonical).hexdigest(),
        'candidate_count': len(candidates),
        'method': 'WGS84 ellipsoidal geodesic / GeographicLib',
        'scope': 'All substations in the loaded dataset; map filters do not limit candidates.',
    }


app = FastAPI(title=CONFIG['title'])
app.add_middleware(TrustedHostMiddleware, allowed_hosts=['127.0.0.1', 'localhost', 'testserver'])


@app.get('/', response_class=HTMLResponse)
def home():
    return (BASE / 'index.html').read_text(encoding='utf-8')


@app.get('/api/config')
def config():
    return CONFIG


@app.get('/app.js')
def javascript():
    return FileResponse(BASE / 'app.js', media_type='application/javascript')


@app.get('/api/demo')
def demo():
    return validate(json.loads((BASE / 'demo.geojson').read_text(encoding='utf-8')), CONFIG['scope'])


async def body(request):
    if request.headers.get('content-type', '').split(';')[0].strip() != 'application/json':
        raise HTTPException(415, 'Use application/json.')
    raw = bytearray()
    async for chunk in request.stream():
        raw.extend(chunk)
        if len(raw) > MAX_BYTES:
            raise HTTPException(413, 'Maximum request size: 20 MiB.')
    try:
        return json.loads(raw)
    except (ValueError, UnicodeDecodeError, RecursionError):
        raise HTTPException(422, 'Invalid JSON.')


@app.post('/api/validate')
async def validate_api(request: Request):
    payload = await body(request)
    try:
        return validate(payload, CONFIG['scope'])
    except (ValueError, TypeError, KeyError, OverflowError) as error:
        raise HTTPException(422, str(error))


@app.post('/api/nearest')
async def nearest_api(request: Request):
    payload = await body(request)
    try:
        require(isinstance(payload, dict), 'Expected an object.')
        data = validate(payload.get('dataset'), CONFIG['scope'])
        return nearest(data, payload.get('plant_id'))
    except (ValueError, TypeError, KeyError, OverflowError) as error:
        raise HTTPException(422, str(error))


if __name__ == '__main__':
    import uvicorn
    parser = argparse.ArgumentParser()
    parser.add_argument('--port', type=int, default=CONFIG['port'])
    args = parser.parse_args()
    uvicorn.run(app, host='127.0.0.1', port=args.port)
