"""Restore pinned archived CoreScripts outside source/evidence directories."""
from concurrent.futures import ThreadPoolExecutor
import hashlib
import json
from pathlib import Path
from urllib.request import urlopen
import zlib


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


def restore_images(directory):
    manifest = json.loads(Path(__file__).with_name('core_images.json').read_text())
    directory.mkdir(parents=True,exist_ok=True)
    def fetch(item):
        asset,spec = item
        if spec['url']!='https://assetdelivery.roblox.com/v1/asset/?id='+asset:
            raise ValueError('Unexpected pinned image source')
        with urlopen(spec['url'],timeout=20) as response:data=response.read(2*1024*1024+1)
        if data.startswith(b'\x1f\x8b'):
            inflater = zlib.decompressobj(31)
            data = inflater.decompress(data,2*1024*1024+1)
            if inflater.unconsumed_tail:raise ValueError('Oversized compressed image')
        if len(data)>2*1024*1024 or hashlib.sha256(data).hexdigest()!=spec['sha256']:
            raise ValueError('Pinned UI image identity mismatch: '+asset)
        (directory/(asset+'.png')).write_bytes(data)
        return asset,data
    with ThreadPoolExecutor(max_workers=6) as pool:
        return dict(pool.map(fetch,manifest['assets'].items())),manifest
