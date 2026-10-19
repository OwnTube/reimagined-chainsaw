/* Self-contained so Playwright can serialize this function into the page. */
export function acceptOfficialPlayback({media,player,watchUrl,origin,videoId,localMediaResponse}) {
  const url=new URL(watchUrl);
  return !!media?.ok && url.origin===origin && url.pathname==='/watch' && url.searchParams.get('v')===videoId &&
    !!localMediaResponse && [1,0].includes(player?.state) && player.videoId===videoId &&
    player.playabilityStatus==='OK' && !player.errorVisible && !player.errorClass;
}

export async function probePlayback(video, {timeoutMs=8000, minTime=0.1, stableMs=0}={}) {
  const snapshot = () => ({
    readyState:video.readyState, networkState:video.networkState,
    paused:video.paused, ended:video.ended, currentTime:video.currentTime,
    duration:Number.isFinite(video.duration) ? video.duration : null,
    mediaError:video.error?.code ?? null,
    sourcePath:new URL(video.currentSrc || video.src || '', 'http://localhost').pathname.slice(0,200)
  });
  const deadline=performance.now()+timeoutMs;
  let timer;
  try {
    video.muted=true;
    await Promise.race([
      video.play(),
      new Promise((_,reject)=>{timer=setTimeout(()=>reject(new Error('Playback start timed out')),timeoutMs);})
    ]);
    while(video.currentTime<=minTime && performance.now()<deadline) {
      await new Promise(resolve=>setTimeout(resolve,Math.min(100,Math.max(1,deadline-performance.now()))));
    }
    if(video.currentTime<=minTime) throw new Error('Playback made no progress before deadline');
    if(stableMs>0) {
      const before=video.currentTime;
      await new Promise(resolve=>setTimeout(resolve,Math.min(stableMs,Math.max(0,deadline-performance.now()))));
      if(video.currentTime<=before && !video.ended) throw new Error('Playback stalled during stability check');
    }
    return {ok:true,...snapshot()};
  } catch(error) {
    video.pause();
    return {ok:false,reason:error.message,...snapshot()};
  } finally {
    clearTimeout(timer);
  }
}
