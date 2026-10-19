import assert from 'node:assert/strict';
import {probePlayback,acceptOfficialPlayback,probeOfficialControls} from '../scripts/playback_probe.mjs';

const fixture=overrides=>({readyState:0,networkState:2,paused:true,ended:false,currentTime:0,
  duration:NaN,currentSrc:'http://localhost:3000/media/abcdefghijk/video.mp4?private=omit',
  pause(){this.paused=true;},...overrides});
const start=performance.now();
const pending=await probePlayback(fixture({play:()=>new Promise(()=>{})}),{timeoutMs:30});
assert.equal(pending.ok,false);
assert.match(pending.reason,/timed out/);
assert.ok(performance.now()-start<1000,'A pending HTMLMediaElement.play() must not stall the runner');
assert.equal(pending.sourcePath,'/media/abcdefghijk/video.mp4');
const played=await probePlayback(fixture({readyState:4,play(){this.currentTime=.2;this.paused=false;return Promise.resolve();}}),{timeoutMs:30});
assert.equal(played.ok,true);
const stalled=await probePlayback(fixture({play:()=>Promise.resolve()}),{timeoutMs:30});
assert.equal(stalled.ok,false);
assert.match(stalled.reason,/no progress/);
const shortBurst=await probePlayback(fixture({play(){this.currentTime=.2;return Promise.resolve();}}),{timeoutMs:60,stableMs:20});
assert.equal(shortBurst.ok,false,'A single advancing sample must not pass a stability check');
const rejected=await probePlayback(fixture({error:{code:4},play:()=>Promise.reject(new Error('Unsupported source'))}),{timeoutMs:30});
assert.equal(rejected.mediaError,4);
assert.equal(rejected.ok,false);
const official={media:{ok:true},player:{state:1,videoId:'abcdefghijk',playabilityStatus:'OK',errorVisible:false,errorClass:false},
  watchUrl:'http://localhost:3000/watch?v=abcdefghijk',origin:'http://localhost:3000',videoId:'abcdefghijk',localMediaResponse:true,localTitleVisible:true};
assert.equal(acceptOfficialPlayback(official),true);
assert.equal(acceptOfficialPlayback({...official,player:{...official.player,playabilityStatus:'ERROR'}}),false,
  'An advancing underlying video cannot override an ERROR player response');
assert.equal(acceptOfficialPlayback({...official,player:{...official.player,errorVisible:true}}),false);
assert.equal(acceptOfficialPlayback({...official,watchUrl:'http://localhost:3000/'}),false);
assert.equal(acceptOfficialPlayback({...official,localTitleVisible:false}),false,'Original sample metadata over local media must not pass');
let controlState=1;
const controlVideo={paused:false,currentTime:1};
const controller={querySelector:()=>controlVideo,getPlayerState:()=>controlState,
  pauseVideo(){controlVideo.paused=true;controlState=2;},seekTo(value){controlVideo.currentTime=value;},
  playVideo(){controlVideo.paused=false;controlVideo.currentTime=.3;controlState=1;}};
assert.deepEqual(await probeOfficialControls(controller,{timeoutMs:30}),{ok:true,pause:true,seek:true,resume:true});
const brokenControl=await probeOfficialControls({...controller,pauseVideo(){}},{timeoutMs:30});
assert.equal(brokenControl.ok,false);
assert.match(brokenControl.reason,/timed out/);
assert.equal((await probeOfficialControls({querySelector:()=>null},{timeoutMs:30})).ok,false);
console.log('Playback probe handles pending, stalled, rejected and progressing media without leaking URL queries');
