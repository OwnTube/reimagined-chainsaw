"""Prove our C++ entry point starts its packaged renderer, without Studio."""
import argparse
import hashlib
import json
from pathlib import Path
import socket
import signal
import subprocess
import sys
import time
import urllib.request

sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'rcc2013'))
from item_fixture import mesh,model,texture
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'hosting2013'))
from windows_join_probe import udp_binding

def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--exe',type=Path,required=True)
    parser.add_argument('--content',type=Path,required=True)
    parser.add_argument('--output',type=Path,required=True)
    args=parser.parse_args();out=args.output.resolve();out.mkdir(parents=True,exist_ok=False)
    with socket.socket() as s:s.bind(('127.0.0.1',0));http=s.getsockname()[1]
    with socket.socket(socket.AF_INET,socket.SOCK_DGRAM) as s:s.bind(('127.0.0.1',0));udp=s.getsockname()[1]
    base='http://127.0.0.1:'+str(http)
    def api(path,data=None):
        request=urllib.request.Request(base+path,data=data,method='POST' if data is not None else 'GET')
        with urllib.request.urlopen(request,timeout=10) as r:return json.load(r)
    report={'passed':False,'entry_point':'native C++ RCCService.exe','studio_launched':False,'jobs':[]}
    log=(out/'service.log').open('wb')
    process=subprocess.Popen([str(args.exe.resolve()),'-console','--port',str(udp),'--http-port',str(http),'--content',str(args.content.resolve()),'--data',str(out/'data'),'--output',str(out/'network'),'--duration','90'],stdout=log,stderr=subprocess.STDOUT,creationflags=subprocess.CREATE_NEW_PROCESS_GROUP)
    try:
        deadline=time.monotonic()+40
        while time.monotonic()<deadline and process.poll() is None:
            try:health=api('/health');break
            except (OSError,ValueError):time.sleep(.25)
        else:raise RuntimeError('Packaged renderer failed to start')
        report['health']=health
        if health.get('backend')!='custom_software' or health.get('studio_required') is not False:raise RuntimeError('Unexpected renderer backend')
        report['udp_owned_by_native_exe']=udp_binding(process.pid,udp)
        if not report['udp_owned_by_native_exe']:raise RuntimeError('Native entry point does not own the UDP port')
        with urllib.request.urlopen(base+'/logo.png') as r:
            report['console_logo_sha256']=hashlib.sha256(r.read()).hexdigest()
        m=api('/v1/assets?kind=mesh',mesh());t=api('/v1/assets?kind=texture',texture());item=api('/v1/assets?kind=model',model(m['id'],t['id']))
        jobs=[{'type':'headshot'},{'type':'full_body','size':{'width':450,'height':600}},
              {'type':'game_thumbnail','size':{'width':640,'height':360}}, {'type':'item','asset_id':item['id']}]
        for request in jobs:
            job=api('/v1/renders',json.dumps(request).encode())['id'];deadline=time.monotonic()+25
            while time.monotonic()<deadline:
                result=api('/v1/renders/'+job)
                if result['state'] not in ('queued','running'):break
                time.sleep(.1)
            report['jobs'].append(result)
            if result['state']!='succeeded' or not result['result'].get('custom_render_validated'):raise RuntimeError('Custom executable render failed: '+json.dumps(result))
            with urllib.request.urlopen(base+'/v1/renders/'+job+'/image') as r:data=r.read()
            if hashlib.sha256(data).hexdigest()!=result['result']['png_sha256']:raise RuntimeError('Delivered PNG mismatch')
            (out/(request['type']+'.png')).write_bytes(data)
        report['passed']=True
    except Exception as error:report['error']=str(error)
    finally:
        # Wait for the service's own bounded exit, which also closes its worker.
        if process.poll() is None:
            process.send_signal(signal.CTRL_BREAK_EVENT)
            try:process.wait(timeout=10)
            except subprocess.TimeoutExpired:
                process.kill();process.wait(timeout=5)
                report['passed']=False;report['cleanup_error']='Native service did not stop gracefully'
        # The test can be terminated externally: stop only its exact worker path
        # in the disposable runner during cleanup, never a user process.
        log.close();(out/'exe-render-result.json').write_text(json.dumps(report,indent=2)+'\n')
    print(json.dumps(report,indent=2));return 0 if report['passed'] else 1

if __name__=='__main__':raise SystemExit(main())
