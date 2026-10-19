"""Experimental Windows runtime probe for the pinned Studio build, not an RCC server."""
import argparse
import base64
import hashlib
import json
import os
from pathlib import Path
import secrets
import struct
import subprocess
import sys
import zlib

STUDIO_SHA256 = 'cc70176d50d5f2c1edc26d40f1fcdc530748fc83dedc63c2fdbb251f766972d2'


def parse_events(text, marker):
    events = []
    decoder = json.JSONDecoder()
    for line in text.splitlines():
        offset = line.find(marker)
        if offset >= 0:
            event, _ = decoder.raw_decode(line[offset+len(marker):])
            if not isinstance(event, dict) or 'kind' not in event or 'data' not in event:
                raise ValueError('Malformed probe record')
            events.append(event)
    return events


def validate_png(data):
    if not data.startswith(b'\x89PNG\r\n\x1a\n'):
        raise ValueError('Capture is not a PNG')
    offset, chunks, dimensions = 8, [], None
    while offset < len(data):
        if offset + 12 > len(data):
            raise ValueError('Truncated PNG chunk')
        length = struct.unpack_from('>I', data, offset)[0]
        end = offset + length + 12
        if end > len(data):
            raise ValueError('PNG chunk exceeds buffer')
        kind = data[offset+4:offset+8]
        payload = data[offset+8:offset+8+length]
        crc = struct.unpack_from('>I', data, end-4)[0]
        if zlib.crc32(kind + payload) & 0xffffffff != crc:
            raise ValueError('PNG checksum mismatch')
        if not chunks:
            if kind != b'IHDR' or length != 13:
                raise ValueError('PNG has no valid IHDR')
            dimensions = struct.unpack_from('>II', payload)
        chunks.append(kind)
        offset = end
        if kind == b'IEND':
            if length != 0 or offset != len(data):
                raise ValueError('Invalid PNG termination')
            break
    if not dimensions or min(dimensions) <= 0 or b'IDAT' not in chunks or chunks[-1] != b'IEND':
        raise ValueError('Incomplete PNG')
    return dimensions


def collect_result(events, want_render):
    if not any(e['kind'] == 'probe_complete' and e['data'] is True for e in events):
        raise ValueError('Studio did not complete the probe; inspect process.log and script-output.log')
    capabilities = [e['data'] for e in events if e['kind'] == 'capabilities']
    if len(capabilities) != 1:
        raise ValueError('Expected one capability record')
    result = {'capabilities': capabilities[0], 'render_requested': want_render,
              'client_join_validated': False, 'server_hosting_validated': False}
    png = None
    if want_render:
        failed = [e['data'] for e in events if e['kind'] == 'render_failed']
        if failed:
            raise ValueError('Studio capture failed: ' + str(failed))
        completed = [e['data'] for e in events if e['kind'] == 'render_complete']
        chunks = [e['data'] for e in events if e['kind'] == 'png_chunk']
        if len(completed) != 1 or len(chunks) != completed[0]['chunks']:
            raise ValueError('Screenshot transfer did not complete')
        if [c['index'] for c in chunks] != list(range(1, len(chunks)+1)):
            raise ValueError('Missing or duplicate screenshot chunks')
        encoded = ''.join(c['base64'] for c in chunks)
        if len(encoded) > 45 * 1024 * 1024:
            raise ValueError('Screenshot exceeds transfer limit')
        png = base64.b64decode(encoded, validate=True)
        dimensions = validate_png(png)
        if len(png) != completed[0]['bytes'] or dimensions != (256, 256):
            raise ValueError('Screenshot metadata mismatch')
        result['render'] = {'bytes': len(png), 'dimensions': dimensions,
                            'sha256': hashlib.sha256(png).hexdigest()}
    return result, png


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--studio', type=Path, required=True, help='Full path to RobloxStudioBeta.exe')
    parser.add_argument('--output', type=Path, required=True, help='New output directory')
    parser.add_argument('--place', type=Path, help='Optional local place; default is Studio Baseplate')
    parser.add_argument('--render', action='store_true', help='Attempt a 256x256 viewport PNG; may prompt in Studio')
    parser.add_argument('--timeout', type=int, default=180)
    args = parser.parse_args()
    if os.name != 'nt':
        parser.error('This probe requires a Windows desktop with Roblox Studio. It was not runtime-tested on Linux.')
    if args.timeout < 1:
        parser.error('--timeout must be positive')
    studio = args.studio.resolve(strict=True)
    if hashlib.sha256(studio.read_bytes()).hexdigest() != STUDIO_SHA256:
        parser.error('Studio SHA-256 differs from the examined 0.743 build')
    place = args.place.resolve(strict=True) if args.place else None
    out = args.output.resolve()
    out.mkdir(parents=True, exist_ok=False)
    marker = 'RCCPROBE_' + secrets.token_hex(16) + ':'
    template = Path(__file__).with_name('probe.luau').read_text()
    script = out/'probe.generated.luau'
    script.write_text(template.replace('__RCC_MARKER__', marker)
                      .replace('__RCC_RENDER__', 'true' if args.render else 'false'), encoding='utf-8')
    script_output = out/'script-output.log'
    command = [str(studio), '--task', 'RunScript', '--runScriptFile', str(script),
               '--outputFile', str(script_output), '--quitAfterExecution']
    if place:
        command += ['--localPlaceFile', str(place)]
    with (out/'process.log').open('wb') as log:
        process = subprocess.Popen(command, cwd=studio.parent, stdout=log, stderr=subprocess.STDOUT)
        try:
            code = process.wait(timeout=args.timeout)
        except subprocess.TimeoutExpired:
            from windows_diagnostics import capture_startup
            capture_startup(out, process.pid)
            process.terminate()
            try:
                process.wait(timeout=10)
            except subprocess.TimeoutExpired:
                process.kill()
                process.wait(timeout=10)
            raise RuntimeError('Studio timed out; logs retained in '+str(out))
    from windows_diagnostics import capture_startup
    capture_startup(out, process.pid)
    if code:
        raise RuntimeError('Studio exited with code '+str(code)+'; logs retained in '+str(out))
    if not script_output.exists():
        raise RuntimeError('Studio produced no script output; inspect '+str(out/'process.log'))
    events = parse_events(script_output.read_text(encoding='utf-8-sig', errors='strict'), marker)
    (out/'events.json').write_text(json.dumps(events, indent=2), encoding='utf-8')
    result, png = collect_result(events, args.render)
    result['studio_sha256'] = STUDIO_SHA256
    if png is not None:
        (out/'viewport.png').write_bytes(png)
    (out/'result.json').write_text(json.dumps(result, indent=2), encoding='utf-8')
    print(json.dumps(result, indent=2))


if __name__ == '__main__':
    try:
        main()
    except (OSError, ValueError, RuntimeError) as error:
        print(str(error), file=sys.stderr)
        raise SystemExit(1)
