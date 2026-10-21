"""Publish only our tested EXEs, their hashes and open-source runtime notices.

Runs on GitHub Actions after native tests pass. The workflow token is read only
from the environment, never logged or saved. No Roblox executable/data is used.
"""
import base64
import hashlib
import importlib.metadata
import json
import os
from pathlib import Path
import sys
import urllib.request

REPOSITORY='vibecodeforever/reimagined-chainsaw'
BRANCH='rcc2013-ci'

def main():
    if os.environ.get('GITHUB_REPOSITORY')!=REPOSITORY or os.environ.get('GITHUB_REF')!='refs/heads/'+BRANCH:
        raise RuntimeError('Binary publication is restricted to the owned isolated branch')
    token=os.environ['GITHUB_TOKEN'];source=os.environ['GITHUB_SHA']
    def api(method,path,body=None):
        request=urllib.request.Request('https://api.github.com/repos/'+REPOSITORY+path,
            data=json.dumps(body).encode() if body is not None else None,method=method,
            headers={'Authorization':'Bearer '+token,'Accept':'application/vnd.github+json',
                     'X-GitHub-Api-Version':'2022-11-28','Content-Type':'application/json'})
        with urllib.request.urlopen(request,timeout=120) as response:return json.load(response)
    parent=api('GET','/git/ref/heads/'+BRANCH)['object']['sha']
    if parent!=source:raise RuntimeError('Branch advanced during testing; refusing to publish a stale build')
    tree=api('GET','/git/commits/'+parent)['tree']['sha'];files={};manifest={
        'source_commit':source,'workflow_run':os.environ['GITHUB_RUN_ID'],
        'platform':'Windows x64','service_implementation':'native C++',
        'render_worker':'packaged original Python/NumPy CPU renderer',
        'roblox_executables_included':False,'game_join_validated':False,'files':{}}
    evidence=json.loads(Path('server2013/output/result.json').read_text())
    if evidence.get('custom_globals_binding_validated') is not True:
        raise RuntimeError('Native Player did not verify server-generated globals')
    if evidence.get('custom_schema_delivery_validated') is not True:
        raise RuntimeError('Native Player did not ACK the complete original schema')
    manifest['schema_transport_delivery_validated']=True
    if evidence.get('custom_property_replication_validated') is not True:
        raise RuntimeError('Server-only service name was not observed in native Player')
    manifest['schema_property_route_validated']=True
    manifest['property_replication_validated']=True
    if evidence.get('custom_instance_replication_validated') is not True:
        raise RuntimeError('Owned StringValue nonce/GUID was not observed in native Player scene')
    manifest['new_instance_replication_validated']=True
    manifest['playable_world_validated']=False
    manifest['application_globals_validated']=True
    manifest['world_replication_implemented']=False
    for name in ('LICENSE','PATENTS'):
        files['server2013/bin/LICENSES/RakNet-'+name+'.txt']=(Path('hosting2013/raknet_reference')/name).read_bytes()
    root=Path('server2013/dist')
    for name in ('RCCService.exe','RCCRenderWorker.exe'):
        data=(root/name).read_bytes()
        if data[:2]!=b'MZ' or not 1024<=len(data)<90*1024*1024:raise ValueError('Unexpected owned PE output')
        files['server2013/bin/'+name]=data
        manifest['files'][name]={'bytes':len(data),'sha256':hashlib.sha256(data).hexdigest()}
    for name in ('numpy','pillow','pyinstaller'):
        distribution=importlib.metadata.distribution(name)
        for entry in distribution.files or []:
            if 'license' not in entry.name.lower() and 'copying' not in entry.name.lower():continue
            path=distribution.locate_file(entry)
            if path.is_file() and path.stat().st_size<1024*1024 and path.suffix.lower() in ('.txt','.md',''):
                safe='-'.join(entry.parts[-3:])
                files['server2013/bin/LICENSES/'+name+'-'+safe]=path.read_bytes()
    for name in ('LICENSE.txt','LICENSE'):
        path=Path(sys.base_prefix)/name
        if path.is_file():files['server2013/bin/LICENSES/Python-LICENSE.txt']=path.read_bytes();break
    files['server2013/bin/build.json']=(json.dumps(manifest,indent=2)+'\n').encode()
    elements=[]
    for path,data in files.items():
        blob=api('POST','/git/blobs',{'content':base64.b64encode(data).decode(),'encoding':'base64'})
        elements.append({'path':path,'mode':'100644','type':'blob','sha':blob['sha']})
    new_tree=api('POST','/git/trees',{'base_tree':tree,'tree':elements})['sha']
    commit=api('POST','/git/commits',{'message':'Publish tested custom RCCService and renderer executables [skip ci]',
        'tree':new_tree,'parents':[parent]})['sha']
    api('PATCH','/git/refs/heads/'+BRANCH,{'sha':commit,'force':False})
    print(json.dumps({'published_commit':commit,'manifest':manifest,'license_files':len(files)-3},indent=2))

if __name__=='__main__':main()
