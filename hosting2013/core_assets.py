"""Restore pinned archived CoreScripts outside source/evidence directories."""
from concurrent.futures import ThreadPoolExecutor
import hashlib
import json
from pathlib import Path
from urllib.request import urlopen


def restore(directory):
    manifest = json.loads(Path(__file__).with_name('core_assets.json').read_text())
    directory.mkdir(parents=True,exist_ok=True)
    def fetch(item):
        asset, spec = item
        if not spec['url'].startswith('https://archive.roblonium.com/Assets/CoreScripts/'):
            raise ValueError('Unexpected CoreScript source')
        path = directory/(asset+'.lua')
        data = path.read_bytes() if path.exists() else None
        if data is None or hashlib.sha256(data).hexdigest()!=spec['sha256']:
            with urlopen(spec['url'],timeout=30) as response:data=response.read(2*1024*1024+1)
            if len(data)>2*1024*1024 or hashlib.sha256(data).hexdigest()!=spec['sha256']:
                raise ValueError('Archived CoreScript identity mismatch: '+asset)
            path.write_bytes(data)
        return asset,data
    with ThreadPoolExecutor(max_workers=6) as pool:
        return dict(pool.map(fetch,manifest['assets'].items())),manifest
