'use strict';
const el = id => document.getElementById(id);
const cameras = {
  classic:{position:[19,15,23],target:[0,2,0]},
  front:{position:[0,9,30],target:[0,2,0]},
  overhead:{position:[16,27,18],target:[0,0,0]}
};
let activeJob = null;
let pollTimer = null;

async function api(path, options) {
  const response = await fetch(path, options);
  const value = await response.json();
  if (!response.ok) throw new Error(value.error || 'The service could not complete this request.');
  return value;
}

function showError(message) {
  el('error').textContent = message;
  el('error').hidden = !message;
}

function displayJob(job) {
  const result = job.result || {};
  el('preview-title').textContent = ({headshot:'Player headshot',full_body:'Player · full body',game_thumbnail:'Game thumbnail'})[result.type] || 'Viewport';
  el('state').textContent = job.state.toUpperCase();
  el('state').dataset.state = job.state;
  el('job-info').textContent = 'Job ' + job.id.slice(0, 8);
  const ready = job.state === 'succeeded';
  el('render-image').hidden = !ready;
  el('placeholder').hidden = ready;
  el('download').hidden = !ready;
  el('details').hidden = false;
  el('evidence').textContent = JSON.stringify(result, null, 2);
  el('preview').dataset.transparent = String(result.transparent === true);
  if (ready) {
    const source = '/v1/renders/' + job.id + '/image';
    if (el('render-image').getAttribute('src') !== source) el('render-image').src = source;
    el('download').href = source;
    el('download').download = 'rcc2013-' + job.id.slice(0, 8) + '.png';
    el('image-info').textContent = result.image_size ? result.image_size.join(' × ') + ' · PNG' : 'PNG image';
  } else {
    el('image-info').textContent = job.state === 'failed' ? 'Render failed' : 'Rendering your scene';
    el('placeholder').querySelector('h3').textContent = job.state === 'failed' ? 'This frame needs another try.' : 'A little 2013 is loading.';
    el('placeholder').querySelector('p').textContent = job.state === 'failed' ? (result.error || 'The worker could not verify this render.') : 'The engine is preparing your scene. This can take a minute.';
  }
}

async function refreshHistory() {
  const {jobs} = await api('/v1/renders');
  el('job-count').textContent = jobs.length;
  const container = el('history');
  container.replaceChildren();
  if (!jobs.length) {
    const empty = document.createElement('p');
    empty.className = 'history-empty';
    empty.textContent = 'Your render history will appear here.';
    container.append(empty);
  }
  for (const job of jobs) {
    const button = document.createElement('button');
    button.className = 'history-job ' + job.state + (activeJob === job.id ? ' active' : '');
    const dot = document.createElement('span'); dot.className = 'dot';
    const label = document.createElement('span');
    label.textContent = (job.result.type || 'render').replaceAll('_',' ') + ' · ' + job.id.slice(0, 6);
    const state = document.createElement('small'); state.textContent = job.state;
    label.append(state); button.append(dot, label);
    button.addEventListener('click', () => watch(job.id));
    container.append(button);
  }
}

async function watch(id) {
  activeJob = id;
  clearTimeout(pollTimer);
  showError('');
  try {
    const job = await api('/v1/renders/' + id);
    if (activeJob !== id) return;
    displayJob(job);
    await refreshHistory();
    if (activeJob === id && (job.state === 'queued' || job.state === 'running')) {
      pollTimer = setTimeout(() => watch(id), 1500);
    }
  } catch (error) { if (activeJob === id) showError(error.message); }
}

function sourceChanged() {
  el('upload-box').hidden = el('scene').value !== 'upload';
  el('place').required = el('scene').value === 'upload';
}
el('scene').addEventListener('change', sourceChanged);
el('type').addEventListener('change', () => {
  const player = el('type').value !== 'game_thumbnail';
  el('scene').disabled = player;
  el('scene').value = player ? 'avatar' : 'default';
  el('scene').querySelector('option[value="avatar"]').disabled = !player;
  el('fov').value = el('type').value === 'headshot' ? 30 : player ? 35 : 50;
  el('angle').value = 'classic';
  el('output-help').textContent = player ? 'Transparent PNG · player only' : 'PNG image · game scene';
  sourceChanged();
});

el('render-form').addEventListener('submit', async event => {
  event.preventDefault();
  showError('');
  el('render-button').disabled = true;
  try {
    const request = {type:el('type').value,camera:{...cameras[el('angle').value], fov:Number(el('fov').value)}};
    if (el('scene').value === 'avatar') {
      request.scene = 'avatar';
      const views = {
        classic:{position:[7,5,-10],target:[0,2.6,0]},
        front:{position:[0,3,-12],target:[0,2.6,0]},
        overhead:{position:[7,12,-10],target:[0,2.6,0]}
      };
      if (request.type === 'headshot') {
        views.classic = {position:[3*Math.sin(Math.PI/16),4.5,-3*Math.cos(Math.PI/16)],target:[0,4.5,0.1]};
        views.front = {position:[0,4.5,-3],target:[0,4.5,0.1]};
        views.overhead = {position:[3*Math.sin(Math.PI/16),6,-3*Math.cos(Math.PI/16)],target:[0,4.5,0.1]};
      }
      request.camera = {...views[el('angle').value], fov:Number(el('fov').value)};
    }
    if (el('size').value !== 'native') {
      const [width,height] = el('size').value.split(',').map(Number);
      request.size = {width,height};
    }
    if (el('scene').value === 'upload') {
      const file = el('place').files[0];
      if (!file) throw new Error('Choose a local place file first.');
      if (file.size > 8 * 1024 * 1024) throw new Error('Choose a place file smaller than 8 MB.');
      const place = await api('/v1/places', {method:'POST', body:file});
      request.place_id = place.place_id;
    }
    const job = await api('/v1/renders', {method:'POST', headers:{'Content-Type':'application/json'}, body:JSON.stringify(request)});
    await watch(job.id);
  } catch (error) { showError(error.message); }
  finally { el('render-button').disabled = false; }
});

async function connect() {
  try {
    const health = await api('/health');
    el('connection').textContent = health.studio_present ? 'Worker available' : 'Studio deployment missing';
    el('connection-dot').className = health.studio_present ? 'online' : '';
    if (!health.studio_present) showError('Install the pinned Studio deployment with download.py before rendering.');
    await refreshHistory();
    const job = new URLSearchParams(location.search).get('job');
    if (job && /^[a-f0-9]{32}$/.test(job)) await watch(job);
  } catch (error) {
    el('connection').textContent = 'Service unavailable';
    el('connection-dot').className = '';
    showError(error.message);
  }
}
connect();
