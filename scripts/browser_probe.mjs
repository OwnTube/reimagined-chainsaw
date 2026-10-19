/* Run on a standard runner; screenshots and sanitized diagnostics only. */
import { chromium, request } from 'playwright';
import { mkdir, readFile, writeFile } from 'node:fs/promises';
import { randomBytes } from 'node:crypto';
import assert from 'node:assert/strict';
import {probePlayback,acceptOfficialPlayback,probeOfficialControls} from './playback_probe.mjs';
import {browserFailures} from './browser_acceptance.mjs';
import {execFile} from 'node:child_process';
import {promisify} from 'node:util';
import {gunzipSync} from 'node:zlib';

const runFile=promisify(execFile);

const origin = process.env.PUBLIC_ORIGIN || 'http://localhost:3000';
await mkdir('evidence', {recursive:true});
const diagnostics = {independentClient:{}, capturedClient:{status:'not-tested',errors:[],failedPaths:[],failedRequests:[]}};
async function checkpoint(stage) {
  diagnostics.lastStage=stage;
  await writeFile('evidence/browser.json',JSON.stringify(diagnostics,null,2));
}
async function bounded(promise,ms,label) {
  let timer;
  try {return await Promise.race([promise,new Promise((_,reject)=>{timer=setTimeout(()=>reject(new Error(label+' timed out')),ms);})]);}
  finally {clearTimeout(timer);}
}
await checkpoint('starting');
const watchdog=setTimeout(()=>{
  diagnostics.error='Browser probe exceeded its 240-second deadline';
  checkpoint(diagnostics.lastStage).finally(()=>process.exit(1));
},240000);
const context = await request.newContext({baseURL:origin,extraHTTPHeaders:{'X-MewTube':'1',Origin:origin}});
const username = 'probe_' + randomBytes(4).toString('hex');
const password = randomBytes(18).toString('hex');
let browser;
try {
  let result = await context.post('/api/register', {data:{username:'creator_'+randomBytes(4).toString('hex'),password:randomBytes(18).toString('hex')}});
  assert.equal(result.status(),200);
  result = await context.post('/api/upload', {data:await readFile('evidence/sample.mp4'), headers:{
    'Content-Type':'application/octet-stream','X-Video-Title':'Runner%20test%20video','X-Video-Description':'Generated%20test%20pattern'}});
  assert.equal(result.status(),202);
  const {id} = await result.json();
  let video;
  for(let i=0;i<60;i++){
    video=(await (await context.get('/api/videos/'+id)).json()).video;
    if(video.status!=='processing')break;
    await new Promise(resolve=>setTimeout(resolve,1000));
  }
  assert.equal(video.status,'ready');
  result = await context.post('/api/register', {data:{username:'decoy_'+randomBytes(4).toString('hex'),password:randomBytes(18).toString('hex')}});
  assert.equal(result.status(),200);
  result = await context.post('/api/upload', {data:await readFile('evidence/sample.mp4'),headers:{
    'Content-Type':'application/octet-stream','X-Video-Title':'Unsubscribed%20decoy'}});
  assert.equal(result.status(),202);
  const decoyId=(await result.json()).id;
  let decoy;
  for(let i=0;i<60;i++) {
    decoy=(await (await context.get('/api/videos/'+decoyId)).json()).video;
    if(decoy.status!=='processing')break;
    await new Promise(resolve=>setTimeout(resolve,1000));
  }
  assert.equal(decoy.status,'ready');
  result = await context.post('/api/register', {data:{username,password}});
  assert.equal(result.status(),200);
  browser=await chromium.launch({headless:true});
  const page=await browser.newPage({viewport:{width:1440,height:1000}});
  page.setDefaultTimeout(15000);
  page.setDefaultNavigationTimeout(20000);
  const state=await context.storageState();
  await page.context().addCookies(state.cookies);
  await page.goto(origin+'/?native=1');
  await page.getByRole('link',{name:'Runner test video',exact:true}).waitFor();
  await page.screenshot({path:'evidence/home.png',fullPage:true});
  await page.getByRole('link',{name:'Runner test video',exact:true}).click();
  await page.locator('video').waitFor();
  const nativePlayback=await bounded(page.locator('video').evaluate(probePlayback,{timeoutMs:8000}),10000,'Independent playback probe');
  assert.equal(nativePlayback.ok,true,JSON.stringify(nativePlayback));
  diagnostics.independentClient.playback=true;
  await checkpoint('independent-playback-passed');
  await page.locator('#like').click();
  await page.waitForFunction(()=>document.querySelector('#like')?.textContent.includes('♥'));
  await page.getByRole('textbox',{name:'Add a comment'}).fill('A real browser comment');
  await page.getByRole('button',{name:'Post',exact:true}).click();
  await page.getByText('A real browser comment',{exact:true}).waitFor();
  await page.screenshot({path:'evidence/watch.png',fullPage:true});
  await page.setViewportSize({width:390,height:844});
  await page.goto(origin);
  await page.getByRole('link',{name:'Runner test video',exact:true}).waitFor();
  assert.equal(await page.evaluate(()=>document.documentElement.scrollWidth<=innerWidth),true);
  await page.screenshot({path:'evidence/mobile.png',fullPage:true});
  diagnostics.independentClient.interactions=true;
  await checkpoint('independent-interactions-passed');
  await page.setViewportSize({width:1440,height:1000});
  page.on('pageerror', error=>{if(diagnostics.capturedClient.errors.length<30)diagnostics.capturedClient.errors.push((error.stack||error.message).slice(0,1200));});
  page.on('requestfailed', req=>{try{const url=new URL(req.url());diagnostics.capturedClient.failedPaths.push(url.pathname.slice(0,250));if(diagnostics.capturedClient.failedRequests.length<100)diagnostics.capturedClient.failedRequests.push({method:req.method(),origin:url.origin,path:url.pathname.slice(0,250),error:req.failure()?.errorText});}catch{}});
  page.on('response',response=>{try{const path=new URL(response.url()).pathname;if(path===`/media/${id}/video.mp4` && [200,206].includes(response.status()))diagnostics.capturedClient.localMediaResponse=true;if(response.status()>=400)diagnostics.capturedClient.failedPaths.push(`${response.status()} ${path.slice(0,200)}`);}catch{}});
  diagnostics.capturedClient.nativeApi=[];
  diagnostics.capturedClient.likedContinuationResponses=[];
  page.on('response',async response=>{
    const path=new URL(response.url()).pathname;
    if(path==='/youtubei/v1/browse') {
      try {
        let raw=response.request().postDataBuffer();
        if(raw && response.request().headers()['content-encoding']==='gzip')raw=gunzipSync(raw,{maxOutputLength:1024*1024});
        const body=JSON.parse(raw.toString());
        if(typeof body.continuation==='string' && body.continuation.startsWith('mewtube-liked-v1:'))
          diagnostics.capturedClient.likedContinuationResponses.push({status:response.status()});
      }catch{}
    }
    if(!['/youtubei/v1/like/like','/youtubei/v1/like/removelike','/youtubei/v1/subscription/subscribe','/youtubei/v1/subscription/unsubscribe','/youtubei/v1/comment/create_comment','/youtubei/v1/account/account_menu'].includes(path))return;
    const entry={path,status:response.status(),gzip:response.request().headers()['content-encoding']==='gzip'};
    diagnostics.capturedClient.nativeApi.push(entry);
    if(response.status()>=400)try{const data=await response.json();entry.error=typeof data.error==='string'?data.error.slice(0,120):null;}catch{}
  });
  const captured=await page.goto(origin+'/official');
  if(captured.status()===200){
    await page.waitForTimeout(15000);
    diagnostics.capturedClient.status='captured';
    diagnostics.capturedClient.customElementDefined=await page.evaluate(()=>!!customElements.get('ytd-app'));
    diagnostics.capturedClient.localTitleVisible=await page.getByText('Runner test video',{exact:true}).first().isVisible().catch(()=>false);
    diagnostics.capturedClient.sameOrigin=new URL(page.url()).origin===origin;
    diagnostics.capturedClient.status=diagnostics.capturedClient.localTitleVisible && diagnostics.capturedClient.customElementDefined && diagnostics.capturedClient.sameOrigin?'home-rendered':'boot-incomplete';
    await checkpoint('official-home-inspected');
    await page.screenshot({path:'evidence/official-experimental.png',fullPage:true,timeout:10000});
    if(diagnostics.capturedClient.status==='home-rendered'){
      try {
        await page.getByRole('button',{name:'MewTube @'+username,exact:true}).click({timeout:8000});
        const menu=page.locator('ytd-multi-page-menu-renderer:visible').first();
        await menu.getByText('@'+username,{exact:true}).waitFor({timeout:8000});
        diagnostics.capturedClient.nativeAccountMenu={opened:true,localIdentity:true};
        await page.screenshot({path:'evidence/official-account-menu.png',fullPage:true,timeout:10000});
        await menu.getByText('Your channel',{exact:true}).click({timeout:8000});
        const viewer=(await (await context.get('/api/me')).json()).user;
        await page.waitForURL(url=>url.pathname==='/channel/'+viewer.id,{timeout:8000});
        await page.locator('yt-page-header-view-model').getByText('@'+username,{exact:true}).waitFor({timeout:8000});
        diagnostics.capturedClient.nativeAccountMenu.ownChannel=true;
      }catch(error){diagnostics.capturedClient.nativeAccountMenu={...diagnostics.capturedClient.nativeAccountMenu,ok:false,error:error.message.slice(0,300)};}
      await page.goto(origin+'/official');
      await page.getByText('Runner test video',{exact:true}).first().waitFor({timeout:10000});
      await checkpoint('official-account-menu-inspected');
      try{
        await page.getByText('Runner test video',{exact:true}).first().click({timeout:10000});
        const officialVideo=page.locator('ytd-app #movie_player video').first();
        await officialVideo.waitFor({state:'attached',timeout:15000});
        await checkpoint('official-player-attached');
        await page.waitForFunction(()=>typeof document.querySelector('ytd-app #movie_player')?.playVideo==='function',null,{timeout:10000});
        await page.locator('ytd-app #movie_player').evaluate(root=>root.mute?.());
        const largePlay=page.locator('ytd-app #movie_player .ytp-large-play-button');
        if(await largePlay.isVisible()) {
          await largePlay.click({timeout:5000});
          diagnostics.capturedClient.startMethod='official-play-button';
        }else {
          await page.locator('ytd-app #movie_player').evaluate(root=>root.playVideo());
          diagnostics.capturedClient.startMethod='official-controller';
        }
        diagnostics.capturedClient.media=await bounded(officialVideo.evaluate(probePlayback,{timeoutMs:10000,stableMs:1200}),12000,'Official playback probe');
        diagnostics.capturedClient.player=await bounded(page.evaluate(()=>{
          const root=document.querySelector('ytd-app #movie_player');
          const error=Array.from(document.querySelectorAll('ytd-app .ytp-error,ytd-app #error-screen,ytd-app yt-playability-error-supported-renderers')).find(node=>
            getComputedStyle(node).display!=='none' && getComputedStyle(node).visibility!=='hidden' && node.getBoundingClientRect().height>0);
          const visible=!!error;
          let state=null,videoId=null,status=null,reason=null,responseKeys=[],playabilityKeys=[],errorCode=null,errorReason=null;
          try{state=root?.getPlayerState?.() ?? null;}catch{}
          try{videoId=root?.getVideoData?.()?.video_id ?? null;}catch{}
          try{
            const response=root?.getPlayerResponse?.();
            const playability=response?.playabilityStatus;
            responseKeys=Object.keys(response || {}).slice(0,40);
            playabilityKeys=Object.keys(playability || {}).slice(0,20);
            status=playability?.status ?? null;reason=playability?.reason?.slice(0,250) ?? null;
            const message=playability?.errorScreen?.playerErrorMessageRenderer;
            const plainText=value=>typeof value?.simpleText==='string'?value.simpleText:
              (value?.runs || []).map(run=>run.text || '').join('');
            errorReason=message?plainText(message.reason).slice(0,250):null;
            const code=response?.errorCode ?? playability?.errorCode;
            errorCode=typeof code==='number' || (typeof code==='string' && /^\d{1,12}$/.test(code))?code:null;
          }catch{}
          return {state,videoId,playabilityStatus:status,playabilityReason:reason,errorVisible:visible,errorText:visible?error.textContent.trim().slice(0,250):null,
            errorClass:root?.classList.contains('ytp-error') || root?.classList.contains('ytp-error-mode') || false,
            responseKeys,playabilityKeys,errorCode,errorReason};
        }),3000,'Official player state');
        const watchUrl=new URL(page.url());
        diagnostics.capturedClient.watchPath=watchUrl.pathname;
        diagnostics.capturedClient.watchBootstrap=await page.evaluate(()=>({
          local:window.ytInitialData?.mewtubeLocalBootstrap===true,
          present:!!window.ytInitialData,
          localAccount:JSON.stringify(window.ytInitialData?.topbar || {}).includes('MewTube')
        }));
        diagnostics.capturedClient.watchLocalTitleVisible=await page.locator('ytd-app h1').getByText('Runner test video',{exact:true}).first().isVisible().catch(()=>false);
        const player=diagnostics.capturedClient.player;
        diagnostics.capturedClient.playback=acceptOfficialPlayback({media:diagnostics.capturedClient.media,player,
          watchUrl:page.url(),origin,videoId:id,localMediaResponse:diagnostics.capturedClient.localMediaResponse,
          localTitleVisible:diagnostics.capturedClient.watchLocalTitleVisible});
        if(diagnostics.capturedClient.playback) {
          diagnostics.capturedClient.controls=await bounded(page.locator('ytd-app #movie_player').first()
            .evaluate(probeOfficialControls,{timeoutMs:2500}),8500,'Official player controls');
          if(!diagnostics.capturedClient.controls.ok) {
            diagnostics.capturedClient.playback=false;
            diagnostics.capturedClient.media.reason=diagnostics.capturedClient.controls.reason;
          }
        }
        if(!diagnostics.capturedClient.playback)diagnostics.capturedClient.watchError=diagnostics.capturedClient.media.reason ||
          (player.errorVisible ? player.errorText : 'Player state, watch identity or local media response did not pass');
      }catch(error){diagnostics.capturedClient.playback=false;diagnostics.capturedClient.watchError=error.message.slice(0,500);}
      await checkpoint('official-watch-inspected');
      await page.screenshot({path:'evidence/official-watch-experimental.png',fullPage:true,timeout:10000});
      // Keep mutation evidence independent from media/autoplay acceptance.
      if(diagnostics.capturedClient.player?.videoId===id && diagnostics.capturedClient.player.playabilityStatus==='OK') {
        try {
          diagnostics.capturedClient.nativeActionButtons=await page.locator('ytd-app button').evaluateAll(buttons=>buttons
            .filter(button=>/like/i.test(button.getAttribute('aria-label') || ''))
            .slice(0,10).map(button=>({label:button.getAttribute('aria-label'),pressed:button.getAttribute('aria-pressed')})));
          const nativeLike=()=>page.locator('ytd-app').getByRole('button',{name:/^(Like|Unlike) this video$/}).first();
          await nativeLike().click({timeout:8000});
          let current=(await (await context.get('/api/videos/'+id)).json()).video;
          for(let i=0;i<30 && current.liked;i++) {
            await page.waitForTimeout(100);
            current=(await (await context.get('/api/videos/'+id)).json()).video;
          }
          assert.equal(current.liked,false,'Native unlike must reach the local authenticated API');
          await page.reload();
          await nativeLike().click({timeout:8000});
          for(let i=0;i<30 && !current.liked;i++) {
            await page.waitForTimeout(100);
            current=(await (await context.get('/api/videos/'+id)).json()).video;
          }
          assert.equal(current.liked,true,'Native like must persist in the same local account');
          await page.reload();
          await nativeLike().waitFor({timeout:8000});
          assert.equal(await nativeLike().getAttribute('aria-pressed'),'true','Reloaded native button must reflect persisted like');
          diagnostics.capturedClient.localAccountVisible=await page.getByText('MewTube @'+username,{exact:true}).isVisible();
          diagnostics.capturedClient.nativeLikes={unlike:true,like:true,persisted:true};
          await page.waitForTimeout(800);
          await page.screenshot({path:'evidence/official-mutations.png',fullPage:true,timeout:10000});
        }catch(error){diagnostics.capturedClient.nativeLikes={ok:false,error:error.message.slice(0,300)};}
        await checkpoint('official-mutations-inspected');
        try {
          await page.mouse.wheel(0,900);
          await page.getByText('A real browser comment',{exact:true}).first().waitFor({timeout:8000});
          diagnostics.capturedClient.nativeComments={visible:true,
            localAuthor:await page.getByText('@'+username,{exact:true}).first().isVisible()};
          await page.getByText('Add a local comment…',{exact:true}).first().click({timeout:8000});
          await page.locator('ytd-commentbox [contenteditable="true"]').first().fill('Created through the captured client',{timeout:8000});
          await page.locator('ytd-commentbox').getByRole('button',{name:'Comment',exact:true}).first().click({timeout:8000});
          let created=false;
          for(let i=0;i<30 && !created;i++) {
            await page.waitForTimeout(100);
            created=(await (await context.get('/api/videos/'+id)).json()).comments.some(comment=>comment.text==='Created through the captured client');
          }
          assert.equal(created,true,'Native composer must persist a local-account comment');
          diagnostics.capturedClient.nativeComments.created=true;
          await page.getByText('Created through the captured client',{exact:true}).first().waitFor({timeout:5000});
          diagnostics.capturedClient.nativeComments.liveInsert=true;
          await page.reload();
          await page.mouse.wheel(0,900);
          await page.getByText('Created through the captured client',{exact:true}).first().waitFor({timeout:8000});
          diagnostics.capturedClient.nativeComments.persisted=true;
          await page.screenshot({path:'evidence/official-comments.png',fullPage:true,timeout:10000});
          await page.mouse.wheel(0,-900);
        }catch(error){diagnostics.capturedClient.nativeComments={...diagnostics.capturedClient.nativeComments,ok:false,error:error.message.slice(0,300)};}
        await checkpoint('official-comments-inspected');
        try {
          const subscribeButton=()=>page.locator('ytd-app').getByRole('button',{name:'Subscribe',exact:true}).first();
          await subscribeButton().click({timeout:8000});
          let subscribed=false;
          for(let i=0;i<30 && !subscribed;i++) {
            await page.waitForTimeout(100);
            subscribed=(await (await context.get('/api/videos/'+id)).json()).video.subscribed;
          }
          assert.equal(subscribed,true,'Native Subscribe must reach the authenticated local API');
          await page.reload();
          await page.locator('ytd-app').getByRole('button',{name:'Unsubscribe',exact:true}).first().waitFor({timeout:8000});
          diagnostics.capturedClient.nativeSubscriptions={subscribe:true,persisted:true};
          await page.getByRole('button',{name:'Guide',exact:true}).first().click({timeout:8000});
          await page.locator('ytd-guide-renderer').getByRole('link',{name:'Subscriptions',exact:true}).first().click({timeout:8000});
          await page.waitForURL(url=>url.pathname==='/feed/subscriptions',{timeout:8000});
          await page.getByText('Runner test video',{exact:true}).first().waitFor({timeout:10000});
          assert.equal(await page.getByText('Unsubscribed decoy',{exact:true}).first().isVisible(),false);
          assert.equal(await page.evaluate(()=>!!document.querySelector('ytd-app')),true);
          diagnostics.capturedClient.nativeSubscriptions.feed=true;
          diagnostics.capturedClient.nativeSubscriptions.guide=true;
          diagnostics.capturedClient.nativeSubscriptions.excludesUnfollowed=true;
          await page.screenshot({path:'evidence/official-subscriptions.png',fullPage:true,timeout:10000});
          await page.goto(origin+'/channel/'+video.owner);
          await page.getByText('Runner test video',{exact:true}).first().waitFor({timeout:10000});
          assert.equal(await page.getByText('Unsubscribed decoy',{exact:true}).first().isVisible(),false);
          diagnostics.capturedClient.nativeSubscriptions.channel=true;
          diagnostics.capturedClient.nativeSubscriptions.excludesOtherCreator=true;
          const header=page.locator('yt-page-header-view-model');
          await header.getByText(video.username,{exact:true}).first().waitFor({timeout:8000});
          await header.getByText('@'+video.username,{exact:true}).first().waitFor({timeout:8000});
          await header.getByText('1 subscriber',{exact:true}).first().waitFor({timeout:8000});
          await header.getByText('1 video',{exact:true}).first().waitFor({timeout:8000});
          diagnostics.capturedClient.nativeChannelHeader={title:true,handle:true,subscriberCount:true,readyVideoCount:true};
          await page.screenshot({path:'evidence/official-channel.png',fullPage:true,timeout:10000});
          await page.goto(origin+'/watch?v='+id);
          await page.locator('ytd-app').getByRole('button',{name:'Unsubscribe',exact:true}).first().click({timeout:8000});
          for(let i=0;i<30 && subscribed;i++) {
            await page.waitForTimeout(100);
            subscribed=(await (await context.get('/api/videos/'+id)).json()).video.subscribed;
          }
          assert.equal(subscribed,false,'Native Unsubscribe must remove the local relation');
          diagnostics.capturedClient.nativeSubscriptions.unsubscribe=true;
        }catch(error){diagnostics.capturedClient.nativeSubscriptions={...diagnostics.capturedClient.nativeSubscriptions,ok:false,error:error.message.slice(0,300)};}
        await checkpoint('official-subscriptions-inspected');
        const guestPage=await browser.newPage({viewport:{width:1440,height:1000}});
        diagnostics.capturedClient.guestFailedPaths=[];
        guestPage.on('response',response=>{if(response.status()>=400 && diagnostics.capturedClient.guestFailedPaths.length<30)
          diagnostics.capturedClient.guestFailedPaths.push(response.status()+' '+new URL(response.url()).pathname.slice(0,160));});
        try {
          await guestPage.goto(origin+'/watch?v='+id);
          const guestApp=guestPage.locator('ytd-app');
          const guestLike=guestApp.getByRole('button',{name:/^(Like|Unlike) this video$/})
            .or(guestApp.getByRole('link',{name:/^(Like|Unlike) this video$/})).first();
          await guestLike.waitFor({timeout:10000});
          await guestPage.waitForTimeout(800);
          await guestPage.screenshot({path:'evidence/official-guest-watch.png',fullPage:true,timeout:10000});
          await guestLike.click({timeout:10000});
          await guestPage.waitForURL(url=>url.origin===origin && url.searchParams.get('signin')==='1',{timeout:8000});
          await guestPage.locator('#auth[open]').waitFor({timeout:5000});
          diagnostics.capturedClient.guestLocalSignIn=true;
          await guestPage.locator('#auth-form [name=username]').fill(username);
          await guestPage.locator('#auth-form [name=password]').fill(password);
          await guestPage.locator('#auth-form .primary').click();
          await guestPage.waitForURL(url=>url.origin===origin && url.pathname==='/official' && url.searchParams.get('v')===id,{timeout:10000});
          await guestPage.getByText('MewTube @'+username,{exact:true}).waitFor({timeout:10000});
          diagnostics.capturedClient.localAccountHandoff=true;
        }catch(error){diagnostics.capturedClient.localAccountHandoff=false;diagnostics.capturedClient.guestSignInError=error.message.replaceAll(password,'[redacted]').split('\n')[0].slice(0,300);}
        finally{await guestPage.close();}
        await checkpoint('official-guest-signin-inspected');
        try {
          const search=page.locator('input[name="search_query"]:visible').first();
          await search.fill('Runner test',{timeout:8000});
          await search.press('Enter');
          await page.waitForURL(url=>url.pathname==='/results' && url.searchParams.get('search_query')==='Runner test',{timeout:8000});
          await page.locator('ytd-search').getByText('Runner test video',{exact:true}).first().waitFor({timeout:10000});
          assert.equal(await page.locator('ytd-search').getByText('Unsubscribed decoy',{exact:true}).first().isVisible(),false);
          diagnostics.capturedClient.nativeSearch={submitted:true,localResult:true,excludesNonmatch:true};
          await page.screenshot({path:'evidence/official-search.png',fullPage:true,timeout:10000});
          await page.reload();
          await page.locator('ytd-search').getByText('Runner test video',{exact:true}).first().waitFor({timeout:10000});
          assert.equal(await page.locator('ytd-search').getByText('Unsubscribed decoy',{exact:true}).first().isVisible(),false);
          diagnostics.capturedClient.nativeSearch.reload=true;
          await page.locator('ytd-search').getByText('Runner test video',{exact:true}).first().click({timeout:8000});
          await page.waitForURL(url=>url.pathname==='/watch' && url.searchParams.get('v')===id,{timeout:8000});
          await page.locator('ytd-app h1:visible').getByText('Runner test video',{exact:true}).first().waitFor({timeout:8000});
          diagnostics.capturedClient.nativeSearch.watchNavigation=true;
        }catch(error){
          diagnostics.capturedClient.nativeSearch={...diagnostics.capturedClient.nativeSearch,ok:false,error:error.message.slice(0,300)};
          await page.screenshot({path:'evidence/official-search.png',fullPage:true,timeout:10000}).catch(()=>{});
        }
        await checkpoint('official-search-inspected');
        let libraryFixture;
        try {
          const viewer=(await (await context.get('/api/me')).json()).user;
          const seeded=await runFile('python',['scripts/seed_browser_library.py','seed','--source',id,'--user',viewer.id],{timeout:15000});
          libraryFixture=JSON.parse(seeded.stdout);
          await page.getByRole('button',{name:'Guide',exact:true}).first().click({timeout:8000});
          await page.locator('ytd-guide-renderer').getByRole('link',{name:'Liked videos',exact:true}).first().click({timeout:8000});
          await page.waitForURL(url=>url.pathname==='/playlist' && url.searchParams.get('list')==='LL',{timeout:8000});
          const likedTitle=()=>page.locator('yt-lockup-view-model').getByText('Runner test video',{exact:true}).first();
          await likedTitle().waitFor({timeout:10000});
          assert.equal(await page.locator('yt-lockup-view-model').getByText('Unsubscribed decoy',{exact:true}).first().isVisible(),false);
          diagnostics.capturedClient.nativeLikedPlaylist={guide:true,localVideo:true,excludesUnliked:true};
          await page.waitForTimeout(800);
          await page.screenshot({path:'evidence/official-liked-playlist.png',timeout:10000});
          const finalTitle=page.locator('yt-lockup-view-model').getByText(libraryFixture.lastTitle,{exact:true}).first();
          for(let i=0;i<8 && !await finalTitle.isVisible();i++) {
            await page.locator('yt-lockup-view-model').last().scrollIntoViewIfNeeded({timeout:5000});
            await page.mouse.wheel(0,1200);
            await page.waitForTimeout(400);
          }
          await finalTitle.waitFor({timeout:8000});
          assert.ok(diagnostics.capturedClient.likedContinuationResponses.some(response=>response.status===200));
          diagnostics.capturedClient.nativeLikedPlaylist.pagination=true;
          diagnostics.capturedClient.nativeLikedPlaylist.renderedCards=await page.locator('yt-lockup-view-model').count();
          await page.screenshot({path:'evidence/official-liked-pagination.png',timeout:10000});
          await page.reload();
          await likedTitle().waitFor({timeout:10000});
          diagnostics.capturedClient.nativeLikedPlaylist.reload=true;
          await likedTitle().click({timeout:8000});
          await page.waitForURL(url=>url.pathname==='/watch' && url.searchParams.get('v')===id,{timeout:8000});
          diagnostics.capturedClient.nativeLikedPlaylist.watchNavigation=true;
          await runFile('python',['scripts/seed_browser_library.py','clean','--ids',...libraryFixture.ids],{timeout:15000});
          libraryFixture=null;
          await page.locator('ytd-app').getByRole('button',{name:'Unlike this video',exact:true}).first().click({timeout:8000});
          let liked=true;
          for(let i=0;i<30 && liked;i++) {
            await page.waitForTimeout(100);
            liked=(await (await context.get('/api/videos/'+id)).json()).video.liked;
          }
          assert.equal(liked,false);
          await page.goto(origin+'/playlist?list=LL');
          await page.getByText('Liked videos',{exact:true}).first().waitFor({timeout:8000});
          assert.equal(await page.locator('yt-lockup-view-model').count(),0);
          diagnostics.capturedClient.nativeLikedPlaylist.unlikeRemoves=true;
          await context.post('/youtubei/v1/like/like',{data:{target:{videoId:id}}});
        }catch(error){
          diagnostics.capturedClient.nativeLikedPlaylist={...diagnostics.capturedClient.nativeLikedPlaylist,ok:false,error:error.message.slice(0,300)};
          await page.screenshot({path:'evidence/official-liked-playlist.png',fullPage:true,timeout:10000}).catch(()=>{});
        }finally{
          if(libraryFixture)await runFile('python',['scripts/seed_browser_library.py','clean','--ids',...libraryFixture.ids],{timeout:15000}).catch(()=>{});
        }
        await checkpoint('official-liked-playlist-inspected');
      }
    }
  }else diagnostics.capturedClient.status='capture-unavailable';
}catch(error){diagnostics.error=error.message.replaceAll(password,'[redacted]').split('\n')[0].slice(0,300);process.exitCode=1;}
finally{
  diagnostics.capturedClient.failedPaths=[...new Set(diagnostics.capturedClient.failedPaths)].slice(0,100);
  diagnostics.acceptanceFailures=browserFailures(diagnostics);
  if(diagnostics.acceptanceFailures.length)process.exitCode=1;
  await checkpoint('finished');
  console.log(JSON.stringify(diagnostics,null,2));
  try {await bounded(browser?.close() || Promise.resolve(),5000,'Browser cleanup');await bounded(context.dispose(),5000,'API cleanup');}
  catch(error){console.error(error.message);process.exitCode=1;}
  clearTimeout(watchdog);
}
