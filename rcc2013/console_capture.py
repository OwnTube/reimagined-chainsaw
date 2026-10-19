"""Check the branded console against completed real engine jobs in Chrome."""
import argparse
from html.parser import HTMLParser
import json
import os
from pathlib import Path
import shutil
import socket
import subprocess
import sys
import tempfile
import time
import urllib.request
from PIL import Image


class ConsoleDOM(HTMLParser):
    def __init__(self):
        super().__init__()
        self.nodes = {}

    def handle_starttag(self, tag, attrs):
        attrs = dict(attrs)
        if 'id' in attrs:
            self.nodes[attrs['id']] = attrs


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--studio',required=True)
    parser.add_argument('--data',type=Path,required=True)
    parser.add_argument('--output',type=Path,required=True)
    args = parser.parse_args()
    output = args.output.resolve()
    chrome = shutil.which('chrome') or str(Path(os.environ.get('PROGRAMFILES','C:/Program Files'))/
                                         'Google/Chrome/Application/chrome.exe')
    if not Path(chrome).is_file():
        raise RuntimeError('Chrome is required for the console integration check')
    with socket.socket() as listener:
        listener.bind(('127.0.0.1',0));port=listener.getsockname()[1]
    with (output/'console-server.log').open('wb') as log:
        server = subprocess.Popen([sys.executable,'server.py','--studio',args.studio,
                                   '--data',str(args.data),'--port',str(port)],stdout=log,stderr=log)
        try:
            base = 'http://127.0.0.1:'+str(port)
            for attempt in range(30):
                if server.poll() is not None:raise RuntimeError('Console server exited before startup')
                try:
                    with urllib.request.urlopen(base+'/v1/renders',timeout=1) as response:
                        jobs=json.load(response)['jobs']
                    break
                except OSError:
                    if attempt==29:raise
                    time.sleep(0.2)
            avatar = next(j for j in jobs if j['state']=='succeeded' and j['result'].get('scene')=='avatar')
            with tempfile.TemporaryDirectory(prefix='rcc2013-chrome-') as profile:
                run=subprocess.run([chrome,'--headless=new','--no-first-run','--disable-background-networking',
                    '--hide-scrollbars','--window-size=1440,1000','--virtual-time-budget=7000',
                    '--user-data-dir='+profile,'--screenshot='+str(output/'console-preview.png'),
                    '--dump-dom',base+'/?job='+avatar['id']],capture_output=True,timeout=40)
            if run.returncode:raise RuntimeError('Chrome console capture failed: '+str(run.returncode))
            dom=ConsoleDOM();dom.feed(run.stdout.decode('utf-8',errors='replace'))
            if dom.nodes.get('state',{}).get('data-state')!='succeeded':
                raise RuntimeError('Console JavaScript did not display the completed native job')
            preview=dom.nodes.get('render-image',{})
            if 'hidden' in preview or preview.get('src')!='/v1/renders/'+avatar['id']+'/image':
                raise RuntimeError('Console did not select the actual avatar image endpoint')
            if Image.open(output/'console-preview.png').size!=(1440,1000):
                raise RuntimeError('Unexpected console screenshot dimensions')
            (output/'console-validation.json').write_text(json.dumps({
                'passed':True,'browser':'Chrome headless','job_id':avatar['id'],
                'native_png_sha256':avatar['result']['png_sha256'],
                'ui_selected_native_image':True,'image_size':[1440,1000]},indent=2)+'\n')
        finally:
            server.terminate()
            try:server.wait(timeout=10)
            except subprocess.TimeoutExpired:server.kill();server.wait(timeout=5)


if __name__=='__main__':main()
