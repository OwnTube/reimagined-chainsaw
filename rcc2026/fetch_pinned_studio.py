"""Assemble the examined Studio build from official CDN packages for a Windows CI probe."""
import argparse
from concurrent.futures import ThreadPoolExecutor
import hashlib
import json
from pathlib import Path, PurePosixPath
import re
import urllib.request
import zipfile

BASE = 'https://setup.rbxcdn.com/version-4f087c32742644ab-'
MANIFESTS = {'rbxPkgManifest.txt': '581181443ad4bcdb7ff644d57c62947f2d93181182ee9be9facffaa6350f8125', 'rbxManifest.txt': '8ae26b21cd6a1cff711fce37b762c71d53dd064f53942c0ca071fe4e22a6c92e'}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--destination', type=Path, required=True)
    parser.add_argument('--package-cache', type=Path)
    args = parser.parse_args()
    destination = args.destination.resolve()
    destination.mkdir(parents=True, exist_ok=False)
    cache = args.package_cache.resolve() if args.package_cache else destination.parent/'studio-package-cache'
    cache.mkdir(parents=True, exist_ok=True)
    manifests = {}
    for name, digest in MANIFESTS.items():
        with urllib.request.urlopen(BASE+name, timeout=60) as response:
            data = response.read(8*1024*1024+1)
        if len(data)>8*1024*1024 or hashlib.sha256(data).hexdigest()!=digest:
            raise ValueError('Pinned manifest identity mismatch: '+name)
        manifests[name] = data.decode().splitlines()
    lines = manifests['rbxPkgManifest.txt']
    if lines[0]!='v0' or (len(lines)-1)%4:
        raise ValueError('Unknown package manifest format')
    packages = [lines[i:i+4] for i in range(1,len(lines),4)]
    verification = json.loads(Path(__file__).with_name('evidence').joinpath('studio-download-verification.json').read_text())
    mapping = verification['package_mapping']
    if set(mapping)!=set(p[0] for p in packages):
        raise ValueError('Package set differs from the examined release')

    def fetch(package):
        name, digest, compressed, _ = package
        if not re.fullmatch(r'[A-Za-z0-9_-]+\.zip',name):
            raise ValueError('Invalid package name')
        target = cache/name
        if not target.exists():
            temp = target.with_suffix('.partial')
            try:
                with urllib.request.urlopen(BASE+name,timeout=120) as response, temp.open('wb') as out:
                    while chunk := response.read(1024*1024):
                        out.write(chunk)
                temp.replace(target)
            finally:
                temp.unlink(missing_ok=True)
        data = target.read_bytes()
        if len(data)!=int(compressed) or hashlib.md5(data).hexdigest()!=digest:
            raise ValueError('Package checksum or size mismatch: '+name)
        return target

    with ThreadPoolExecutor(max_workers=6) as pool:
        archives = list(pool.map(fetch,packages))
    for archive in archives:
        with zipfile.ZipFile(archive) as z:
            for item in z.infolist():
                normalized = item.filename.replace('\\','/')
                if normalized.endswith('/'):
                    continue
                name = PurePosixPath(mapping[archive.name]+normalized)
                if name.is_absolute() or '..' in name.parts or any(':' in p for p in name.parts):
                    raise ValueError('Archive member leaves the output directory')
                target = destination.joinpath(*name.parts)
                target.parent.mkdir(parents=True,exist_ok=True)
                target.write_bytes(z.read(item))
    lines = manifests['rbxManifest.txt']
    if len(lines)%2:
        raise ValueError('Malformed file manifest')
    checked = 0
    for name, digest in zip(lines[::2],lines[1::2]):
        normalized = PurePosixPath(name.replace('\\','/'))
        if normalized.is_absolute() or '..' in normalized.parts:
            raise ValueError('Manifest path leaves output directory')
        target = destination.joinpath(*normalized.parts)
        if hashlib.md5(target.read_bytes()).hexdigest()!=digest:
            raise ValueError('File checksum mismatch: '+name)
        checked += 1
    executable = destination/'RobloxStudioBeta.exe'
    digest = hashlib.sha256(executable.read_bytes()).hexdigest()
    if digest!='cc70176d50d5f2c1edc26d40f1fcdc530748fc83dedc63c2fdbb251f766972d2':
        raise ValueError('Studio executable identity mismatch')
    # Deployment configuration written separately from Roblox's verified assets,
    # following the layout used by Vinegar's rbxbin.WriteAppSettings helper.
    (destination/'AppSettings.xml').write_text(
        '<?xml version="1.0" encoding="UTF-8"?>\n<Settings>\n'
        '  <ContentFolder>content</ContentFolder>\n'
        '  <BaseUrl>http://www.roblox.com</BaseUrl>\n</Settings>\n', encoding='utf-8')
    # Qt otherwise searches its compiled-in build-machine plugin paths. The
    # platform DLL is already verified above, under Qt5/platforms/qwindows.dll.
    (destination/'qt.conf').write_text('[Paths]\nPlugins=Qt5\n', encoding='utf-8')
    report = {'version':'0.743.0.7431133','files_verified':checked,'studio_sha256':digest,
              'packages_verified':len(packages),'source':'official Roblox setup CDN',
              'generated_configuration_files':['AppSettings.xml','qt.conf'],
              'engine_executed':False}
    (destination/'assembly-report.json').write_text(json.dumps(report,indent=2))
    print(json.dumps(report,indent=2))


if __name__ == '__main__':
    main()
