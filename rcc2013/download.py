"""Download the complete pinned archive deployments, without redistributing them."""
import argparse
from concurrent.futures import ThreadPoolExecutor
import hashlib
import json
from pathlib import Path, PurePosixPath
import shutil
import stat
import urllib.request
import zipfile


def digest(path):
    with path.open('rb') as stream:
        return hashlib.file_digest(stream, 'sha256').hexdigest()


def restore(name, spec, destination, cache):
    archive = cache/(name+'.zip')
    if not archive.exists() or digest(archive) != spec['zip_sha256']:
        temporary = cache/(name+'.download')
        with urllib.request.urlopen(spec['url'], timeout=120) as response, temporary.open('wb') as stream:
            shutil.copyfileobj(response, stream)
        if digest(temporary) != spec['zip_sha256']:
            raise ValueError('Archive digest mismatch: '+name)
        temporary.replace(archive)
    target = destination/name
    target.mkdir(parents=True, exist_ok=False)
    files = 0
    with zipfile.ZipFile(archive) as source:
        if sum(i.file_size for i in source.infolist()) > 1024*1024*1024:
            raise ValueError('Unexpected expanded archive size')
        for info in source.infolist():
            path = PurePosixPath(info.filename.replace('\\', '/'))
            if path.is_absolute() or '..' in path.parts or not path.parts or path.parts[0] != spec['archive_root']:
                raise ValueError('Unexpected archive path')
            if stat.S_ISLNK(info.external_attr >> 16):
                raise ValueError('Archive symlinks are unsupported')
            relative = path.parts[1:]
            if not relative:
                continue
            output = target.joinpath(*relative)
            if info.is_dir():
                output.mkdir(parents=True, exist_ok=True)
            else:
                output.parent.mkdir(parents=True, exist_ok=True)
                with source.open(info) as read, output.open('wb') as write:
                    shutil.copyfileobj(read, write)
                files += 1
    executable = target/spec['executable']
    if digest(executable) != spec['executable_sha256']:
        raise ValueError('Executable digest mismatch: '+name)
    return {'name': name, 'files': files, 'zip_sha256': spec['zip_sha256'],
            'executable_sha256': spec['executable_sha256'], 'file_version': spec['file_version']}


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--destination', type=Path, default=Path('vendor'))
    parser.add_argument('--only',choices=('studio','player'),help='Restore one deployment only')
    parser.add_argument('--cache', type=Path, default=Path('cache'))
    args = parser.parse_args()
    args.cache.mkdir(parents=True, exist_ok=True)
    specs = json.loads(Path(__file__).with_name('packages.json').read_text())
    if args.only:specs={args.only:specs[args.only]}
    with ThreadPoolExecutor(max_workers=2) as pool:
        results = list(pool.map(lambda pair: restore(*pair, args.destination, args.cache), specs.items()))
    print(json.dumps(results, indent=2))
