'use strict';
const $ = selector => document.querySelector(selector);
let me = null, signingUp = false, studioTimer;
const escapeHTML = value => String(value ?? '').replace(/[&<>"']/g, ch => ({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}[ch]));
const fmt = n => new Intl.NumberFormat().format(n);
const time = seconds => `${Math.floor(seconds / 60)}:${String(Math.floor(seconds % 60)).padStart(2, '0')}`;
const ago = date => {const days = Math.floor((Date.now() / 1000 - date) / 86400); return days ? `${days}d ago` : 'Today';};
function toast(message) { $('#toast').textContent = message; $('#toast').style.display = 'block'; clearTimeout(toast.timer); toast.timer = setTimeout(() => $('#toast').style.display = 'none', 4500); }
async function api(path, body) {
  const response = await fetch(path, body === undefined ? {} : {method:'POST', headers:{'Content-Type':'application/json','X-MewTube':'1'}, body:JSON.stringify(body)});
  const data = await response.json();
  if (!response.ok) { if (response.status === 401) auth(); throw new Error(data.error || 'Request failed'); }
  return data;
}
function auth() { if (!$('#auth').open) $('#auth').showModal(); }
function signedIn() { if (me) return true; auth(); return false; }
function updateAccount() { $('#account').textContent = me ? '@' + me.username : 'Sign in'; }
function card(v) { return `<article class="card"><a class="thumb" href="/watch?v=${v.id}"><img src="/media/${v.id}/thumb.jpg" loading="lazy" alt=""><span class="duration">${time(v.duration)}</span></a><div class="card-info"><a class="avatar" href="/channel?id=${v.owner}" aria-label="${escapeHTML(v.username)} channel">${escapeHTML(v.username[0].toUpperCase())}</a><div><h3><a href="/watch?v=${v.id}">${escapeHTML(v.title)}</a></h3><p><a href="/channel?id=${v.owner}">${escapeHTML(v.username)}</a></p><p>${fmt(v.views)} views · ${ago(v.created)}</p></div></div></article>`; }
function empty(title, detail, create = false) {return `<div class="empty"><div class="empty-icon">▷</div><h2>${title}</h2><p>${detail}</p>${create ? '<a class="button primary" href="/studio">Upload your first video</a>' : '<a class="button" href="/">Explore home</a>'}</div>`;}
function heading(title, detail, eyebrow='YOUR OWN LITTLE INTERNET') {return `<div class="intro"><div><p class="eyebrow">${eyebrow}</p><h1>${escapeHTML(title)}</h1><p class="muted">${escapeHTML(detail)}</p></div><span class="pill"><span class="dot">●</span> Independent & self-hosted</span></div>`;}
async function feed(path, query) {
  let endpoint = '/api/videos', title = 'Good videos. Your people.', detail = 'A home for the things you make and the people you follow.';
  if (path === '/results') {const q = query.get('search_query') || ''; title = `Results for “${q}”`; detail = 'From this instance, with love.'; endpoint += '?q=' + encodeURIComponent(q); $('#search input').value = q;}
  if (path === '/subscriptions') {title = 'From your people.'; detail = 'The latest from channels you subscribe to.'; if (!me) {$('#main').innerHTML=heading(title,detail)+empty('Make yourself at home','Sign in to follow your favorite channels.'); auth(); return;} endpoint+='?feed=subscriptions';}
  if (path === '/channel') {title = 'Channel videos'; detail = 'Everything this creator has shared.'; endpoint += '?channel='+encodeURIComponent(query.get('id') || '');}
  const {videos} = await api(endpoint);
  if (path === '/channel' && videos.length) title = '@' + videos[0].username;
  $('#main').innerHTML = heading(title, detail) + `<div class="section-title"><h2>${path === '/' ? 'Fresh from the community' : 'Videos'}</h2><span>${videos.length} ${videos.length === 1 ? 'video' : 'videos'}</span></div>` + (videos.length ? `<div class="grid">${videos.map(card).join('')}</div>` : empty(path === '/' ? 'Your story starts here.' : 'Nothing here yet.',path === '/' ? 'This instance is ready for its first upload. Make it yours.' : 'New videos will appear here as they are shared.', path === '/'));
}
async function watch(query) {
  const id = query.get('v');
  if (!id) throw new Error('Choose a video to watch');
  const [{video:v,comments}, related] = await Promise.all([api('/api/videos/' + encodeURIComponent(id)), api('/api/videos')]);
  if (v.status !== 'ready') {$('#main').innerHTML = heading(v.title, v.status === 'failed' ? v.error : 'Your video is processing. Check your studio for updates.');return;}
  $('#main').innerHTML = `<div class="watch-layout"><section class="watch"><video controls playsinline preload="metadata" poster="/media/${v.id}/thumb.jpg" src="/media/${v.id}/video.mp4"></video><h1>${escapeHTML(v.title)}</h1><div class="watch-meta"><a class="avatar" href="/channel?id=${v.owner}">${escapeHTML(v.username[0].toUpperCase())}</a><div class="grow"><a href="/channel?id=${v.owner}"><strong>${escapeHTML(v.username)}</strong></a><div class="muted">${fmt(v.views)} views · ${ago(v.created)}</div></div><button id="subscribe" class="${v.subscribed ? '' : 'primary'}">${v.subscribed ? 'Subscribed' : 'Subscribe'}</button><button id="like">${v.liked ? '♥' : '♡'} ${fmt(v.likes)}</button><button id="report">Report</button></div><div class="description">${escapeHTML(v.description || 'No description yet.')}</div><section class="comments"><h2>${comments.length} comments</h2><form class="comment-form"><input name="text" aria-label="Add a comment" placeholder="Join the conversation…" maxlength="2000" required><button>Post</button></form>${comments.map(co => `<article class="comment"><strong>@${escapeHTML(co.username)}</strong><p>${escapeHTML(co.text)}</p></article>`).join('')}</section></section><section class="recommendations"><h2>Keep exploring</h2><div class="grid">${related.videos.filter(x=>x.id!==id).slice(0,8).map(card).join('')}</div></section></div>`;
  let viewed = false;
  $('video').addEventListener('play', () => {if (me && !viewed) {viewed=true;api(`/api/videos/${id}/view`,{}).catch(()=>{});}});
  $('#like').onclick = async () => {if(!signedIn())return; await api(`/api/videos/${id}/like`, {enabled:!v.liked}); await watch(query);};
  $('#subscribe').onclick = async () => {if(!signedIn())return; await api('/api/subscribe',{channelId:v.owner,enabled:!v.subscribed}); v.subscribed=!v.subscribed; $('#subscribe').textContent=v.subscribed?'Subscribed':'Subscribe';};
  $('#report').onclick = async () => {if(!signedIn())return;const reason=prompt('Why are you reporting this video?');if(reason?.trim()){await api(`/api/videos/${id}/report`,{reason});toast('Report sent to the instance operator.');}};
  $('.comment-form').onsubmit = async event => {event.preventDefault();if(!signedIn())return;const text=new FormData(event.target).get('text');await api(`/api/videos/${id}/comment`,{text});await watch(query);};
}
async function studio() {
  if(!me){$('#main').innerHTML=heading('Your creative corner.','Upload something worth sharing.')+empty('Let’s get you signed in.','Create a local account to share your own videos.');auth();return;}
  const {videos}=await api('/api/studio');
  $('#main').innerHTML=heading('Your creative corner.','From an idea to someone’s next favorite video.','CREATOR STUDIO')+`<form id="upload" class="panel"><h2>Share a video</h2><div class="upload-area"><p>Originals, experiments, tiny masterpieces.</p><label for="file">Choose a video · MP4, WebM, MOV and more</label><input id="file" type="file" accept="video/*" required></div><label>Title<input name="title" maxlength="200" placeholder="Give it a good name" required></label><label>Description<textarea name="description" rows="3" maxlength="5000" placeholder="Tell us a little about it"></textarea></label><p class="muted">Up to 500 MB · 60 minutes · Converted locally for playback.</p><button class="primary" type="submit">Upload video ↗</button><p class="upload-progress" role="status"></p><progress max="100" value="0" hidden></progress></form><h2>Your uploads</h2><div id="uploads">${videos.length?videos.map(v=>`<div class="studio-row"><div><a href="/watch?v=${v.id}">${escapeHTML(v.title)}</a><small>${escapeHTML(v.status)} · ${ago(v.created)}</small>${v.error?`<p class="error">${escapeHTML(v.error)}</p>`:''}</div>${!['uploading','processing'].includes(v.status)?`<button class="danger" data-delete="${v.id}">Delete</button>`:''}</div>`).join(''):'<p class="muted">Your uploads will appear here.</p>'}</div>${me.admin?'<p><a class="button" href="/admin">Operator dashboard</a></p>':''}`;
  $('#upload').onsubmit=async event=>{
    event.preventDefault();const form=event.target, file=$('#file').files[0];
    if(!file)return;const data=new FormData(form), title=data.get('title'), description=data.get('description');
    form.querySelector('button').disabled=true;
    try{
      const result=await new Promise((resolve,reject)=>{const xhr=new XMLHttpRequest();xhr.open('POST','/api/upload');xhr.setRequestHeader('X-MewTube','1');xhr.setRequestHeader('Content-Type','application/octet-stream');xhr.setRequestHeader('X-Video-Title',encodeURIComponent(title));xhr.setRequestHeader('X-Video-Description',encodeURIComponent(description));xhr.upload.onprogress=e=>{if(e.lengthComputable){$('progress').hidden=false;$('progress').value=e.loaded/e.total*100;$('.upload-progress').textContent=`Uploading… ${Math.round(e.loaded/e.total*100)}%`;}};xhr.onerror=()=>reject(new Error('Upload connection failed'));xhr.onload=()=>{let value;try{value=JSON.parse(xhr.responseText);}catch{return reject(new Error('Invalid upload response'));}xhr.status<300?resolve(value):reject(new Error(value.error));};xhr.send(file);});
      toast('Upload received. Processing your video…');await studio();
    }catch(error){toast(error.message);form.querySelector('button').disabled=false;}
  };
  for(const button of document.querySelectorAll('[data-delete]')) button.onclick=async()=>{if(confirm('Delete this video permanently?')){await api(`/api/videos/${button.dataset.delete}/delete`,{});await studio();}};
  if(videos.some(v=>['uploading','processing'].includes(v.status))) studioTimer=setTimeout(()=>studio().catch(e=>toast(e.message)),2500);
}
async function admin(){const data=await api('/api/admin');$('#main').innerHTML=heading('Keep your community healthy.','Reports and captured-client compatibility diagnostics.','INSTANCE OPERATOR')+`<h2>Reports</h2>${data.reports.map(r=>`<div class="admin-report"><a href="/watch?v=${r.video_id}">${r.video_id}</a><p>${escapeHTML(r.reason)}</p><button data-moderate="${r.video_id}" class="danger">Remove video</button></div>`).join('')||'<p class="muted">No reports.</p>'}<h2>Unsupported client calls</h2><pre>${escapeHTML(JSON.stringify(data.unknown,null,2))}</pre>`;for(const b of document.querySelectorAll('[data-moderate]'))b.onclick=async()=>{if(confirm('Remove this video?')){await api(`/api/videos/${b.dataset.moderate}/delete`,{});await admin();}};}
async function route(){clearTimeout(studioTimer);const path=location.pathname,query=new URLSearchParams(location.search);document.querySelectorAll('nav a').forEach(a=>a.classList.toggle('active',a.getAttribute('href')===path));$('#main').innerHTML='<p class="loading">Loading…</p>';try{if(path==='/watch')await watch(query);else if(path==='/studio')await studio();else if(path==='/admin')await admin();else await feed(path,query);}catch(error){$('#main').innerHTML=empty('We couldn’t open that.',escapeHTML(error.message));}$('#main').focus({preventScroll:true});}
document.addEventListener('click',event=>{const a=event.target.closest('a');if(!a||event.ctrlKey||event.metaKey||event.shiftKey||event.button!==0||a.target||a.origin!==location.origin||a.pathname==='/official')return;event.preventDefault();history.pushState({},'',a.href);route();window.scrollTo(0,0);});
document.addEventListener('unhandledrejection',event=>{toast(event.reason?.message||'Something went wrong');event.preventDefault();});
addEventListener('popstate',route);
$('#search').onsubmit=event=>{event.preventDefault();history.pushState({},'','/results?search_query='+encodeURIComponent(new FormData(event.target).get('q')));route();};
$('#account').onclick=async()=>{if(!me)return auth();if(confirm(`Sign out of @${me.username}?`)){await api('/api/logout',{});me=null;updateAccount();route();}};
$('.close').onclick=()=>$('#auth').close();
$('#auth-switch').onclick=()=>{signingUp=!signingUp;$('#auth-title').textContent=signingUp?'Find your people':'Welcome back';$('#auth-form .primary').textContent=signingUp?'Create account':'Sign in';$('#auth-switch').textContent=signingUp?'Already here? Sign in':'New here? Create an account';$('#auth-form [name=password]').autocomplete=signingUp?'new-password':'current-password';$('#auth-error').textContent='';};
$('#auth-form').onsubmit=async event=>{event.preventDefault();const button=event.target.querySelector('.primary');button.disabled=true;try{const data=await api(signingUp?'/api/register':'/api/login',Object.fromEntries(new FormData(event.target)));me=data.user;updateAccount();$('#auth').close();event.target.reset();await route();}catch(error){$('#auth-error').textContent=error.message;}finally{button.disabled=false;}};
(async()=>{try{me=(await api('/api/me')).user;updateAccount();await route();if(!me&&new URLSearchParams(location.search).get('signin')==='1')auth();}catch(error){toast(error.message);}})();
