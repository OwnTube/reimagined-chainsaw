import assert from 'node:assert/strict';
import {readFile} from 'node:fs/promises';
import vm from 'node:vm';

const calls=[];
const events={},navigations=[];
let captureClick;
const element=()=>({style:{},addEventListener(){},append(){}});
class XHR {open(){} send(){} setRequestHeader(){}}
const context=vm.createContext({
  Request,Headers,URL,ArrayBuffer,TypeError,
  window:{fetch:async (url,options)=>{calls.push({url,options});return {ok:true};}},
  navigator:{},XMLHttpRequest:XHR,addEventListener(name,callback){events[name]=callback;},
  document:{createElement:element,body:{append(){}},addEventListener(name,callback){if(name==='click')captureClick=callback;}},
  location:{href:'http://localhost:3000/official',origin:'http://localhost:3000',assign(url){navigations.push(url);}}
});
vm.runInContext(await readFile(new URL('../web/bridge.js',import.meta.url),'utf8'),context);
const payload=JSON.stringify({videoId:'abcdefghijk'});
const streaming=new Request('https://www.youtube.com/youtubei/v1/player',{
  method:'POST',duplex:'half',headers:{'Content-Type':'application/json','Authorization':'upstream-token'},
  body:new ReadableStream({start(controller){controller.enqueue(new TextEncoder().encode(payload));controller.close();}})
});
await context.window.fetch(streaming);
assert.equal(calls[0].url,'http://localhost:3000/youtubei/v1/player');
assert.ok(calls[0].options.body instanceof ArrayBuffer,'Upload must be buffered, never a streaming RequestInit body');
assert.equal(new TextDecoder().decode(calls[0].options.body),payload);
assert.equal(calls[0].options.headers.get('X-MewTube'),'1');
assert.equal(calls[0].options.headers.has('Authorization'),false);
assert.equal(calls[0].options.method,'POST');
await context.window.fetch('/youtubei/v1/search',{method:'POST',body:'{"query":"cats"}'});
assert.equal(new TextDecoder().decode(calls[1].options.body),'{"query":"cats"}');
await context.window.fetch('/app.js');
assert.equal(calls[2].options.body,undefined);
await assert.rejects(context.window.fetch('https://unrelated.example/api'),/External request blocked/);
assert.equal(calls.length,3);
events.DOMContentLoaded();
let prevented=false;
const click={button:0,target:{closest:()=>({href:'/watch?v=abcdefghijk'})},preventDefault(){prevented=true;},stopImmediatePropagation(){}};
captureClick(click);
assert.equal(prevented,true);
assert.deepEqual(navigations,['http://localhost:3000/watch?v=abcdefghijk']);
captureClick({...click,ctrlKey:true});
assert.equal(navigations.length,1,'Modified clicks must keep normal browser behavior');
console.log('Bridge request buffering, origin restrictions and captured-watch navigation regressions passed');
