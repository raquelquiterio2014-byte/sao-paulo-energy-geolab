'use strict';
const $ = id => document.getElementById(id);
const empty = () => ({type:'FeatureCollection', features:[]});
let dataset = empty(), visible = [], analysis = null, map = null, ready = false;
let currentMeasurements = empty(), config = null, revision = 0;
let savedDatasetId = null, historyOffset = 0, historyTotal = 0;
async function api(path, payload) {
  const options = payload === undefined ? {} : {method:'POST', headers:{'Content-Type':'application/json'}, body:JSON.stringify(payload)};
  const response = await fetch(path, options);
  const result = await response.json();
  if (!response.ok) throw Error(typeof result.detail === 'string' ? result.detail : JSON.stringify(result.detail));
  return result;
}
function fail(error) {$('error').textContent = error.message || String(error);}
function options(id, values) {
  const select = $(id), previous = select.value;
  select.replaceChildren(new Option('All', ''));
  [...new Set(values)].filter(Boolean).sort().forEach(x => select.add(new Option(x,x)));
  if([...select.options].some(o => o.value === previous)) select.value = previous;
}
function clearAnalysis() {
  revision++; analysis = null; currentMeasurements = empty(); $('results').replaceChildren();
  $('analysisnote').textContent = 'Select a plant to calculate WGS84 geodesic distances.';
  if(ready) map.getSource('measurements').setData(currentMeasurements);
}
function setDataset(data) {
  dataset = data;
  ['region','state','city','fuel'].forEach(id => $(id).replaceChildren());
  options('region', data.features.map(f => f.properties.region));
  options('state', data.features.map(f => f.properties.state));
  options('fuel', data.features.filter(f => f.properties.kind === 'plant').map(f => f.properties.fuel));
  updateCities(); clearAnalysis();
  $('details').textContent = 'No asset selected.'; $('error').textContent = '';
  const synthetic = data.features.filter(f => f.properties.data_status === 'synthetic').length;
  $('notice').textContent = synthetic === data.features.length
    ? 'SYNTHETIC DEMO — fictional installations and routes, not the real electricity grid.'
    : synthetic ? 'MIXED DATASET — includes synthetic and imported records. Not independently verified.'
    : 'IMPORTED DATASET — user-supplied records; coverage and accuracy are not verified.';
  const dates = data.features.map(f => f.properties.source_date).sort();
  $('quality').textContent = `${data.features.length} records; ${synthetic} synthetic; ${data.features.length-synthetic} imported. Source dates: ${dates[0]} to ${dates.at(-1)}.`;
  refresh(); fit();
}
function updateCities() {
  const subset = dataset.features.filter(f => (!$('state').value || f.properties.state === $('state').value) && (!$('region').value || f.properties.region === $('region').value));
  options('city', subset.map(f => f.properties.municipality));
}
function refresh() {
  visible = dataset.features.filter(f => {
    const p = f.properties;
    return (!$('region').value || p.region === $('region').value)
      && (!$('state').value || p.state === $('state').value)
      && (!$('city').value || p.municipality === $('city').value)
      && (p.kind !== 'plant' || !$('fuel').value || p.fuel === $('fuel').value)
      && (p.kind !== 'plant' || $('plants').checked)
      && (p.kind !== 'substation' || $('subs').checked)
      && (p.kind !== 'line' || $('lines').checked);
  });
  const previous = $('plant').value; $('plant').replaceChildren();
  visible.filter(f => f.properties.kind === 'plant').forEach(f => $('plant').add(new Option(`${f.properties.name} (${f.properties.state})`, f.properties.id)));
  if([...$('plant').options].some(o => o.value === previous)) $('plant').value = previous;
  const count = kind => visible.filter(f => f.properties.kind === kind).length;
  $('stats').textContent = `${count('plant')} plants · ${count('substation')} substations · ${count('line')} line records`;
  if(ready) map.getSource('assets').setData({type:'FeatureCollection', features:visible});
  $('summary').replaceChildren(); const groups = {};
  visible.forEach(f => {
    const p = f.properties;
    const g = groups[p.state] ||= {plant:0, substation:0, line:0, mw:0, missing:0}; g[p.kind]++;
    if(p.kind === 'plant') {if(p.capacity_mw === null) g.missing++; else g.mw += p.capacity_mw;}
  });
  Object.keys(groups).sort().forEach(state => {
    const g = groups[state]; appendRow('summary',[state,g.plant,g.substation,g.line,g.mw.toFixed(2),g.missing]);
  });
}
function appendRow(id, values) {
  const tr = document.createElement('tr');
  values.forEach(value => {const td = document.createElement('td'); td.textContent=value; tr.append(td);});
  $(id).append(tr);
}
function fit() {
  if(!ready || !visible.length) return;
  const bounds = new maplibregl.LngLatBounds();
  visible.forEach(f => {
    const points = f.geometry.type === 'Point' ? [f.geometry.coordinates] : f.geometry.coordinates;
    points.forEach(point => bounds.extend(point));
  });
  map.fitBounds(bounds, {padding:45, maxZoom:11, duration:500});
}
function download(name, text, type) {
  const url = URL.createObjectURL(new Blob([text], {type}));
  const link = document.createElement('a'); link.href=url; link.download=name;
  document.body.append(link); link.click(); link.remove(); setTimeout(() => URL.revokeObjectURL(url), 1000);
}
function csvCell(value) {
  let text = String(value ?? ''); if(/^[\s]*[=+\-@]/.test(text)) text = "'" + text;
  return '"' + text.replaceAll('"','""') + '"';
}
['region','state','city','fuel','plants','subs','lines'].forEach(id => {
  $(id).onchange = () => {
    if(id === 'region') options('state', dataset.features.filter(f => !$(id).value || f.properties.region === $(id).value).map(f => f.properties.state));
    if(id === 'region' || id === 'state') updateCities();
    clearAnalysis(); refresh();
  };
});
$('plant').onchange = clearAnalysis; $('fit').onclick = fit;
$('download').onclick = () => download('dataset.geojson', JSON.stringify(dataset,null,2), 'application/geo+json');
async function busy(action) {
  const controls = [...document.querySelectorAll('button,select,input')];
  controls.forEach(e => e.disabled=true); $('error').textContent='';
  try {await action();} catch(e) {fail(e);} finally {controls.forEach(e => e.disabled=false);}
}
function acceptSaved(saved) {
  savedDatasetId = saved.id;
  setDataset(saved.dataset);
  $('savedStatus').textContent=`Saved dataset #${saved.id}: ${saved.name}. Stored in local SQLite.`;
}
async function refreshDatasets() {
  const rows = await api('/api/datasets'); $('savedDataset').replaceChildren();
  rows.forEach(row => $('savedDataset').add(new Option(`#${row.id} ${row.name} — ${row.feature_count} records (${row.synthetic_count} synthetic)`,row.id)));
  $('savedDataset').value=String(savedDatasetId);
}
async function refreshHistory() {
  const data = await api(`/api/analyses?limit=50&offset=${historyOffset}`);
  historyTotal=data.total; $('history').replaceChildren();
  data.items.forEach(row => $('history').add(new Option(
    `#${row.id} · ${new Date(row.created_at).toLocaleString()} · ${row.plant_name} · ${row.dataset_name} (${row.synthetic_count}/${row.feature_count} synthetic)`,row.id)));
  $('historyCount').textContent=data.total ? `${historyOffset+1}–${historyOffset+data.items.length} of ${data.total} saved analyses.` : 'No saved analyses yet.';
}
function displayReport(saved) {
  const result = saved.report;
  analysis = {...result, saved_analysis_id:saved.id, saved_dataset_id:saved.dataset_id, saved_at:saved.created_at};
  currentMeasurements = result.measurements;
  if(ready) map.getSource('measurements').setData(currentMeasurements);
  $('results').replaceChildren();
  result.results.forEach(r => appendRow('results',[r.name,r.state,r.distance_km.toFixed(3),r.connection_status]));
  $('analysisnote').textContent = `${result.plant.name}: ${result.results.length} nearest of ${result.candidate_count} loaded substations. Saved analysis #${saved.id} · ${new Date(saved.created_at).toLocaleString()}. Distances do not prove connections.`;
}
$('demo').onclick = () => busy(async () => {
  acceptSaved(await api('/api/demo/activate',{})); await refreshDatasets();
});
$('openDataset').onclick = () => busy(async () => {
  if(!$('savedDataset').value) throw Error('No saved dataset selected.');
  acceptSaved(await api(`/api/datasets/${$('savedDataset').value}/activate`,{}));
});
$('upload').onchange = event => {
  const file=event.target.files[0];
  if(!file) return;
  busy(async () => {
    if(file.size > 20*1024*1024) throw Error('Maximum file size: 20 MiB.');
    const data=JSON.parse(await file.text());
    const saved=await api('/api/datasets',{name:file.name.slice(0,200),dataset:data});
    acceptSaved(saved); await refreshDatasets();
  }).finally(() => {event.target.value='';});
};
$('analyze').onclick = () => busy(async () => {
  const selected=$('plant').value;
  if(!selected || savedDatasetId === null) throw Error('Select a plant from a saved dataset.');
  clearAnalysis();
  displayReport(await api('/api/analyses',{dataset_id:savedDatasetId,plant_id:selected}));
  historyOffset=0; await refreshHistory();
});
$('openHistory').onclick = () => busy(async () => {
  if(!$('history').value) throw Error('No saved analysis selected.');
  const saved=await api(`/api/analyses/${$('history').value}`);
  acceptSaved(await api(`/api/datasets/${saved.dataset_id}/activate`,{}));
  // A historic plant may be hidden by the current layer toggles. Restore all layers.
  ['plants','subs','lines'].forEach(id => $(id).checked=true);
  refresh(); $('plant').value=saved.plant_id; displayReport(saved);
  await refreshDatasets(); fit();
});
$('refreshHistory').onclick = () => busy(async () => {historyOffset=0;await refreshHistory();});
$('previousHistory').onclick = () => busy(async () => {historyOffset=Math.max(0,historyOffset-50);await refreshHistory();});
$('nextHistory').onclick = () => busy(async () => {if(historyOffset+50<historyTotal) historyOffset+=50;await refreshHistory();});
$('csv').onclick = () => {
  if(!analysis) return fail(Error('Run an analysis first.'));
  const columns = ['plant_id','substation_id','name','state','municipality','distance_km','connection_status','data_status','source','source_date'];
  const rows = [columns, ...analysis.results.map(r => columns.map(c => r[c]))];
  download('nearest_substations.csv', '\ufeff'+rows.map(row => row.map(csvCell).join(',')).join('\r\n'),'text/csv;charset=utf-8');
};
$('report').onclick = () => {
  if(!analysis) return fail(Error('Run an analysis first.'));
  download('analysis.json', JSON.stringify(analysis,null,2), 'application/json');
};
async function start() {
  config = await api('/api/config'); $('title').textContent=config.title; document.title=config.title;
  $('scope').textContent='Searches all substations in the loaded dataset, regardless of map filters. '+(config.scope ? 'SP records only; cross-border candidates require the Brazil edition.' : 'Candidates may cross state boundaries.');
  acceptSaved(await api('/api/state'));
  await refreshDatasets(); await refreshHistory();
  try {
    if(!window.maplibregl) throw Error('MapLibre could not load.');
    map = new maplibregl.Map({container:'map',center:config.center,zoom:config.zoom,
      style:{version:8,sources:{base:{type:'raster',tileSize:256,tiles:['https://tile.openstreetmap.org/{z}/{x}/{y}.png'],attribution:'© OpenStreetMap contributors'}},layers:[{id:'base',type:'raster',source:'base'}]}});
    map.addControl(new maplibregl.NavigationControl());
    map.on('error',() => {$('mapstatus').textContent='A map resource failed to load. Check internet/WebGL; tables and analysis remain available.';});
    map.on('load',() => {
      map.addSource('assets',{type:'geojson',data:empty()});
      map.addSource('measurements',{type:'geojson',data:currentMeasurements});
      map.addLayer({id:'routes',type:'line',source:'assets',filter:['==',['geometry-type'],'LineString'],paint:{'line-color':'#8b6bdf','line-width':3}});
      map.addLayer({id:'points',type:'circle',source:'assets',filter:['==',['geometry-type'],'Point'],paint:{'circle-radius':7,'circle-color':['match',['get','kind'],'plant','#0ca99f','#e69a18'],'circle-stroke-color':'#fff','circle-stroke-width':1}});
      map.addLayer({id:'measurements',type:'line',source:'measurements',paint:{'line-color':'#27374b','line-width':3,'line-dasharray':[2,2]}});
      ['points','routes'].forEach(layer => map.on('click',layer,event => {$('details').textContent=JSON.stringify(event.features[0].properties,null,2);}));
      ready=true; refresh(); fit();
    });
  } catch(e) {$('mapstatus').textContent='Map unavailable: '+e.message+' Tables and analysis still work.';}
}
busy(start);
