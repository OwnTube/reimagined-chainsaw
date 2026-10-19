"""Bounded, account-free attempt to run an owned local Studio test place.

This tests Studio's local StartServer task, not Roblox Player compatibility.
No authentication, binary patches, or third-party place assets are supplied.
"""
import argparse
import hashlib
import json
import os
from pathlib import Path
import re
import secrets
import subprocess
import time
import xml.etree.ElementTree as ET

from windows_diagnostics import capture_startup
from windows_probe import STUDIO_SHA256, parse_events, studio_environment


def write_place(path, marker):
    root = ET.Element('roblox', version='4')
    for value in ('null', 'nil'):
        ET.SubElement(root, 'External').text = value

    def item(parent, class_name, referent, name):
        node = ET.SubElement(parent, 'Item', {'class': class_name, 'referent': referent})
        props = ET.SubElement(node, 'Properties')
        ET.SubElement(props, 'string', name='Name').text = name
        return node, props

    workspace, _ = item(root, 'Workspace', 'RBX0', 'Workspace')
    _, part = item(workspace, 'Part', 'RBX1', 'RccProbePart')
    ET.SubElement(part, 'bool', name='Anchored').text = 'true'
    scripts, _ = item(root, 'ServerScriptService', 'RBX2', 'ServerScriptService')
    _, script = item(scripts, 'Script', 'RBX3', 'RccProbe')
    ET.SubElement(script, 'bool', name='Disabled').text = 'false'
    ET.SubElement(script, 'ProtectedString', name='Source').text = '''
local run = game:GetService("RunService")
local http = game:GetService("HttpService")
local marker = MARKER
local function emit(kind, data)
    print(marker .. http:JSONEncode({kind = kind, data = data}))
end
emit("server_probe", {
    version = version(),
    isStudio = run:IsStudio(),
    isServer = run:IsServer(),
    isRunning = run:IsRunning(),
    ownPlaceLoaded = workspace:FindFirstChild("RccProbePart") ~= nil,
})
game:GetService("Players").PlayerAdded:Connect(function()
    emit("player_added", true)
end)
'''.replace('MARKER', json.dumps(marker))
    ET.ElementTree(root).write(path, encoding='utf-8', xml_declaration=True)


def read_marked_events(marker):
    logs = Path(os.environ['LOCALAPPDATA']) / 'Roblox' / 'logs'
    events = []
    for path in sorted(logs.glob('*.log'), key=lambda p: p.stat().st_mtime)[-10:]:
        try:
            text = path.read_bytes()[-4 * 1024 * 1024:].decode('utf-8', errors='replace')
            events.extend(parse_events(text, marker))
        except (OSError, ValueError):
            continue
    return events


def classify_startup(log_texts, process_id):
    # Native logs contain this exact process-identifying message. Never use a
    # previous API-dump/editor session to diagnose this owned server process.
    identity = f"for process '{int(process_id)}'"
    relevant = [text for text in log_texts if identity in text]
    if not relevant:
        return {'native_log_identified': False, 'launch_arguments_rejected': None,
                'launch_values_rejected': None, 'login_dialog_observed': None,
                'start_server_intent_observed': None}
    text = '\n'.join(relevant)
    return {'native_log_identified': True,
            'launch_arguments_rejected': 'Invalid Launch Intent! Too many arguments provided' in text,
            'launch_values_rejected': 'Invalid Launch Intent! Validation failed' in text,
            'login_dialog_observed': bool(re.search(r'Authenticated\s*:\s*NO', text))
                and 'show login dialog [end]' in text,
            'start_server_intent_observed': 'Studio Launch Intent is StartServer' in text}


def read_startup_observations(process_id):
    logs = Path(os.environ['LOCALAPPDATA']) / 'Roblox' / 'logs'
    texts = []
    for path in sorted(logs.glob('*.log'), key=lambda p: p.stat().st_mtime)[-10:]:
        try:
            texts.append(path.read_bytes()[-4 * 1024 * 1024:].decode('utf-8', errors='replace'))
        except OSError:
            continue
    return classify_startup(texts, process_id)


def udp_binding(process_id, port):
    # Numeric arguments only. The output contains booleans, not the runner's
    # network inventory or unrelated processes.
    command = (f'$p = @(Get-NetUDPEndpoint -OwningProcess {int(process_id)} '
               '-ErrorAction SilentlyContinue); '
               f'@{{port_bound = [bool](@($p | Where-Object LocalPort -eq {int(port)}).Count)}} '
               '| ConvertTo-Json -Compress')
    result = subprocess.run(['powershell.exe', '-NoProfile', '-NonInteractive', '-Command', command],
                            capture_output=True, text=True, timeout=15)
    if result.returncode:
        return None
    return json.loads(result.stdout).get('port_bound')


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--studio', type=Path, required=True)
    parser.add_argument('--output', type=Path, required=True)
    parser.add_argument('--timeout', type=int, default=90)
    parser.add_argument('--port', type=int, default=53640)
    args = parser.parse_args()
    if os.name != 'nt':
        parser.error('Requires native Windows')
    if not 1 <= args.port <= 65535 or not 1 <= args.timeout <= 300:
        parser.error('Invalid port or timeout')
    studio = args.studio.resolve(strict=True)
    if hashlib.sha256(studio.read_bytes()).hexdigest() != STUDIO_SHA256:
        parser.error('Studio identity differs from the examined build')
    out = args.output.resolve()
    out.mkdir(parents=True, exist_ok=False)
    marker = 'RCCSERVER_' + secrets.token_hex(16) + ':'
    place = out / 'owned-server-test.rbxlx'
    write_place(place, marker)
    # Derived from this exact build's StartServer launch builder, not the
    # older injector example. localPlaceFile belongs to the edit-file intent;
    # StartServer emits localProjectFile plus the server/place metadata below.
    command = [str(studio), '-task', 'StartServer', '-localProjectFile', str(place),
               '-placeId', '0', '-universeId', '0', '-port', str(args.port),
               '-creatorId', '0', '-creatorType', '0', '-placeVersion', '0',
               '-numTestServerPlayersUponStartup', '0']
    result = {'studio_sha256': STUDIO_SHA256, 'launch_task': 'StartServer',
              'server_script_validated': False, 'udp_port_bound_by_studio': None,
              'server_hosting_validated': False, 'client_join_validated': False,
              'render_validated': False, 'scope': 'unmodified Studio local test task'}
    result['launch_profile'] = '743-builder-local-project-zero-place-metadata'
    events = []
    with (out / 'process.log').open('wb') as log:
        process = subprocess.Popen(command, cwd=studio.parent, env=studio_environment(studio),
                                   stdout=log, stderr=subprocess.STDOUT)
        try:
            deadline = time.monotonic() + args.timeout
            while process.poll() is None and time.monotonic() < deadline:
                observations = read_startup_observations(process.pid)
                result['startup_observations'] = observations
                if observations['launch_arguments_rejected']:
                    result['startup_blocker'] = 'invalid_launch_arguments'
                    break
                if observations['launch_values_rejected']:
                    result['startup_blocker'] = 'invalid_launch_values'
                    break
                if observations['login_dialog_observed']:
                    result['startup_blocker'] = 'unauthenticated_login_dialog'
                    break
                events = read_marked_events(marker)
                records = [e['data'] for e in events if e['kind'] == 'server_probe']
                if len(records) == 1:
                    record = records[0]
                    result['server_script_validated'] = all(record.get(k) is True for k in
                        ('isStudio', 'isServer', 'isRunning', 'ownPlaceLoaded'))
                    result['engine_record'] = record
                    if result['server_script_validated']:
                        result['udp_port_bound_by_studio'] = udp_binding(process.pid, args.port)
                        if result['udp_port_bound_by_studio'] is True:
                            break
                time.sleep(1)
            result['process_exit_code_before_cleanup'] = process.poll()
            if not result['server_script_validated']:
                result['error'] = 'No validated server script record; inspect startup diagnostics'
        finally:
            capture_startup(out, process.pid)
            if process.poll() is None:
                process.terminate()
                try:
                    process.wait(timeout=10)
                except subprocess.TimeoutExpired:
                    process.kill()
                    process.wait(timeout=10)
            (out / 'events.json').write_text(json.dumps(events, indent=2), encoding='utf-8')
            (out / 'result.json').write_text(json.dumps(result, indent=2), encoding='utf-8')
    print(json.dumps(result, indent=2))
    return 0 if result['server_script_validated'] and result['udp_port_bound_by_studio'] is True else 1


if __name__ == '__main__':
    raise SystemExit(main())
