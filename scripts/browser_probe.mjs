/* Run on a standard runner; screenshots and sanitized diagnostics only. */
import { chromium, request } from 'playwright';
import { mkdir, readFile, writeFile } from 'node:fs/promises';
import { randomBytes } from 'node:crypto';
import assert from 'node:assert/strict';

const origin = process.env.PUBLIC_ORIGIN || 'http://localhost:3000';
await mkdir('evidence', {recursive:true});
const diagnostics = {independentClient:{}, capturedClient:{status:'not-tested',errors:[],failedPaths:[]}};
const context = await request.newContext({baseURL:origin,extraHTTPHeaders:{'X-MewTube':'1',Origin:origin}});
const username = 'probe_' + randomBytes(4).toString('hex');
const password = randomBytes(18).toString('hex');
let browser;
try {
  let result = await context.post('/api/register', {data:{username,password}});
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
  browser=await chromium.launch({headless:true});
  const page=await browser.newPage({viewport:{width:1440,height:1000}});
  const state=await context.storageState();
  await page.context().addCookies(state.cookies);
  await page.goto(origin);
  await page.getByRole('link',{name:'Runner test video',exact:true}).waitFor();
  await page.screenshot({path:'evidence/home.png',fullPage:true});
  await page.getByRole('link',{name:'Runner test video',exact:true}).click();
  await page.locator('video').waitFor();
  await page.locator('video').evaluate(async video=>{video.muted=true;await video.play();});
  await page.waitForFunction(()=>document.querySelector('video')?.currentTime>0.1);
  diagnostics.independentClient.playback=true;
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
  await page.setViewportSize({width:1440,height:1000});
  page.on('pageerror', error=>diagnostics.capturedClient.errors.push(error.message.slice(0,300)));
  page.on('requestfailed', req=>{try{diagnostics.capturedClient.failedPaths.push(new URL(req.url()).pathname.slice(0,250));}catch{}});
  page.on('response',response=>{if(response.status()>=400){try{diagnostics.capturedClient.failedPaths.push(`${response.status()} ${new URL(response.url()).pathname.slice(0,200)}`);}catch{}}});
  const captured=await page.goto(origin+'/official');
  if(captured.status()===200){
    await page.waitForTimeout(15000);
    diagnostics.capturedClient.status='captured';
    diagnostics.capturedClient.customElementDefined=await page.evaluate(()=>!!customElements.get('ytd-app'));
    diagnostics.capturedClient.localTitleVisible=await page.getByText('Runner test video',{exact:true}).first().isVisible().catch(()=>false);
    diagnostics.capturedClient.status=diagnostics.capturedClient.localTitleVisible?'home-rendered':'boot-incomplete';
    await page.screenshot({path:'evidence/official-experimental.png',fullPage:true});
  }else diagnostics.capturedClient.status='capture-unavailable';
}catch(error){diagnostics.error=error.message;process.exitCode=1;}
finally{
  diagnostics.capturedClient.failedPaths=[...new Set(diagnostics.capturedClient.failedPaths)].slice(0,100);
  await writeFile('evidence/browser.json',JSON.stringify(diagnostics,null,2));
  console.log(JSON.stringify(diagnostics,null,2));
  await browser?.close();await context.dispose();
}
