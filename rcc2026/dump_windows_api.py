"""Attempt a native API dump with an owned-process timeout; retains failures."""
import argparse
import hashlib
import json
import os
from pathlib import Path
import subprocess
import sys
from windows_probe import STUDIO_SHA256

parser=argparse.ArgumentParser(description=__doc__)
parser.add_argument('--studio',type=Path,required=True)
parser.add_argument('--output',type=Path,required=True)
args=parser.parse_args()
if os.name!='nt':parser.error('Requires native Windows')
studio=args.studio.resolve(strict=True)
if hashlib.sha256(studio.read_bytes()).hexdigest()!=STUDIO_SHA256:
    parser.error('Studio identity differs from the examined release')
out=args.output.resolve()
out.mkdir(parents=True,exist_ok=False)
api=out/'full-api.json'
result={'studio_sha256':STUDIO_SHA256,'engine_api_dump_validated':False,
        'render_validated':False,'join_validated':False}
with (out/'process.log').open('wb') as log:
    p=subprocess.Popen([str(studio),'--fullApi',str(api)],cwd=studio.parent,stdout=log,stderr=subprocess.STDOUT)
    try:result['exit_code']=p.wait(timeout=120)
    except subprocess.TimeoutExpired:
        p.terminate()
        try:p.wait(timeout=10)
        except subprocess.TimeoutExpired:p.kill();p.wait(timeout=10)
        result['error']='timeout'
if api.exists():
    try:
        data=json.loads(api.read_text(encoding='utf-8-sig'))
        classes=data.get('Classes') if isinstance(data,dict) else None
        if isinstance(classes,list) and len(classes)>0:
            result['engine_api_dump_validated']=result.get('exit_code')==0
            result['class_count']=len(classes)
    except (UnicodeError,ValueError) as error:result['error']=str(error)
(out/'result.json').write_text(json.dumps(result,indent=2))
print(json.dumps(result,indent=2))
sys.exit(0 if result['engine_api_dump_validated'] else 1)
