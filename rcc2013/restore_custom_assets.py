"""Extract seven pinned mesh/texture files, without extracting any executable."""
import argparse
import hashlib
import json
from pathlib import Path
import shutil
import urllib.request
import zipfile

def restore(destination,archive):
    spec=json.loads(Path(__file__).with_name('packages.json').read_text())['player']
    manifest=json.loads(Path(__file__).with_name('custom_assets.json').read_text())['files']
    with archive.open('rb') as stream:
        if hashlib.file_digest(stream,'sha256').hexdigest()!=spec['zip_sha256']:raise ValueError('Original archive identity mismatch')
    destination.mkdir(parents=True,exist_ok=True);records=[]
    with zipfile.ZipFile(archive) as source:
        for name,digest in manifest.items():
            data=source.read(spec['archive_root']+'/content/'+name)
            if hashlib.sha256(data).hexdigest()!=digest:raise ValueError('Asset digest mismatch: '+name)
            target=destination/name;target.parent.mkdir(parents=True,exist_ok=True);target.write_bytes(data)
            records.append({'asset':name,'sha256':digest,'bytes':len(data)})
    return {'executables_extracted':0,'files':records}

if __name__=='__main__':
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--destination',type=Path,default=Path('vendor/custom-content'))
    parser.add_argument('--archive',type=Path)
    args=parser.parse_args()
    if args.archive is None:
        args.archive=Path('cache/player.zip');args.archive.parent.mkdir(parents=True,exist_ok=True)
        if not args.archive.exists():
            spec=json.loads(Path(__file__).with_name('packages.json').read_text())['player']
            with urllib.request.urlopen(spec['url'],timeout=90) as response,args.archive.open('wb') as stream:shutil.copyfileobj(response,stream)
    print(json.dumps(restore(args.destination,args.archive),indent=2))
