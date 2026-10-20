"""Bounded two-process local join test for the pinned, unmodified 2013 Studio."""
import argparse
import ctypes
from ctypes import wintypes
import hashlib
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
import json
import os
from pathlib import Path
import secrets
import shutil
import socket
import subprocess
import sys
import threading
import time
from urllib.parse import urlsplit, parse_qs
import xml.etree.ElementTree as ET

sys.path.insert(0, str(Path(__file__).resolve().parents[1]/'rcc2013'))
from windows_probe import collect_logs, resize_viewport, windows_for_pid, write_scene


def udp_binding(pid, port):
    # Query the native PID table directly; PowerShell/CIM initialization can
    # exceed the whole startup window on an otherwise healthy hosted runner.
    class Row(ctypes.Structure):
        _fields_ = [('address',wintypes.DWORD),('port',wintypes.DWORD),('pid',wintypes.DWORD)]
    get_table = ctypes.windll.iphlpapi.GetExtendedUdpTable
    get_table.argtypes = [ctypes.c_void_p,ctypes.POINTER(wintypes.DWORD),wintypes.BOOL,
                         wintypes.DWORD,ctypes.c_int,wintypes.DWORD]
    get_table.restype = wintypes.DWORD
    size = wintypes.DWORD()
    status = get_table(None,ctypes.byref(size),False,2,1,0)
    if status not in (0,122):raise OSError(status,'UDP owner table query failed')
    for _ in range(3):
        if not 4 <= size.value <= 1024*1024:raise RuntimeError('Unexpected UDP owner table size')
        buffer = ctypes.create_string_buffer(size.value)
        status = get_table(buffer,ctypes.byref(size),False,2,1,0)
        if status==122:continue
        if status:raise OSError(status,'UDP owner table read failed')
        count = wintypes.DWORD.from_buffer_copy(buffer.raw[:4]).value
        if 4+count*ctypes.sizeof(Row)>len(buffer):raise RuntimeError('Truncated UDP owner table')
        for i in range(count):
            row = Row.from_buffer_copy(buffer.raw,4+i*ctypes.sizeof(Row))
            if row.pid==pid and socket.ntohs(row.port & 65535)==port:return True
        return False
    raise RuntimeError('UDP owner table changed repeatedly')


def script_source(role, marker, port, token):
    source = Path(__file__).with_name(role+'.lua').read_text()
    return source.replace('__RCC_MARKER__',json.dumps(marker)).replace('__RCC_PORT__',str(port)).replace('__RCC_TOKEN__',json.dumps(token)).replace('__RCC_CORE_GUI__','false')


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--studio',type=Path,required=True)
    parser.add_argument('--player',type=Path,help='Experiment with the pinned standalone Player instead of a second Studio')
    parser.add_argument('--player-profile',choices=('stock','local-signed'),default='stock')
    parser.add_argument('--host-profile',choices=('test','player'),default='test',help='Player-host profile omits Studio testMode')
    parser.add_argument('--output',type=Path,default=Path('hosting2013/output'))
    parser.add_argument('--timeout',type=int,default=90)
    args = parser.parse_args()
    if os.name != 'nt': parser.error('Native Windows required')
    if not 10 <= args.timeout <= 180: parser.error('Timeout must be 10..180 seconds')
    if args.player_profile=='local-signed' and not args.player:parser.error('local-signed requires the standalone Player')
    studio = args.studio.resolve(strict=True)
    specs = json.loads((Path(__file__).resolve().parents[1]/'rcc2013/packages.json').read_text())
    digest = hashlib.sha256(studio.read_bytes()).hexdigest()
    if digest != specs['studio']['executable_sha256']: raise ValueError('Studio identity mismatch')
    player = args.player.resolve(strict=True) if args.player else None
    if player and hashlib.sha256(player.read_bytes()).hexdigest() != specs['player']['executable_sha256']:
        raise ValueError('Standalone Player identity mismatch')
    out = args.output.resolve(); out.mkdir(parents=True,exist_ok=False)
    with socket.socket(socket.AF_INET,socket.SOCK_DGRAM) as sock:
        sock.bind(('127.0.0.1',0)); port = sock.getsockname()[1]
    token = secrets.token_hex(24)
    markers = {role:'RCCJOIN_'+role+'_'+secrets.token_hex(12) for role in ('host','client')}
    report = {'passed':False,'scope':'two separate unmodified 2013 Studio peers on loopback',
              'studio_sha256':digest,'port':port,'server_hosting_validated':False,
              'client_join_validated':False,'replicated_movement_validated':False,
              'client_character_movement_validated':False,'standalone_player_join_validated':False,
              'launch_profile':'-ide -testMode -fileLocation distinct empty local places -script owned Lua','peers':{}}
    report['client_kind'] = 'standalone_player' if player else 'studio'
    if player:
        report['scope'] = 'unmodified 2013 Studio host and standalone Player on loopback'
        report['player_sha256'] = specs['player']['executable_sha256']
        report['client_launch_profile'] = '-t 0 -a loopback /Login/Negotiate.ashx -j loopback /game/join.ashx'
        report['player_configuration'] = 'copied AppSettings.xml BaseUrl points only to the owned loopback backend'
    backend_requests = []
    backend, backend_thread = None, None
    hosts_path, hosts_line = None, None
    processes, streams = {}, []
    # Runtime copies are outside the evidence folder: never upload executables.
    runtime = studio.parent.parent/('join-'+secrets.token_hex(6))
    runtime.mkdir()
    def launch(role):
        nonlocal backend, backend_thread, hosts_path, hosts_line
        deployment = runtime/role
        standalone = role=='client' and player is not None
        shutil.copytree(player.parent if standalone else studio.parent,deployment)
        plugins = deployment/'BuiltInPlugins'
        # Remove only our renderer's previous owned plugin, if present.
        old = plugins/'Rcc2013Probe'
        if old.exists():
            entry = old/'bootstrap.lua'
            if not entry.exists() or 'Generated by RCC2013' not in entry.read_text():
                raise RuntimeError('Unexpected content in owned renderer plugin directory')
            shutil.rmtree(old)
        source = script_source(role,markers[role],port,token)
        peer = out/role; peer.mkdir()
        (peer/'bootstrap.lua').write_text(source,encoding='utf-8')
        place = peer/'empty.rbxlx'; write_scene(place)
        stream = (peer/'process.log').open('wb'); streams.append(stream)
        env = os.environ.copy()
        for key in ('QT_PLUGIN_PATH','QT_QPA_PLATFORM_PLUGIN_PATH'):env.pop(key,None)
        if standalone:
            signer = None
            core_assets = {}
            if args.player_profile=='local-signed':
                from local_player import configure, LOCAL_DOMAIN
                from core_assets import restore
                core_assets,core_manifest = restore(runtime/'core-assets')
                report['core_assets'] = core_manifest
                source = source.replace('local loadCoreGui = false','local loadCoreGui = true')
                (peer/'bootstrap.lua').write_text(source,encoding='utf-8')
                signer,configuration = configure(deployment/player.name)
                report['local_player_configuration'] = configuration
                report['player_sha256'] = configuration['configured_sha256']
                report['scope'] = 'unmodified 2013 Studio host and locally configured standalone 2013 Player'
                hosts_path = Path(os.environ['WINDIR'])/'System32/drivers/etc/hosts'
                hosts_line = ('\r\n127.0.0.1 '+LOCAL_DOMAIN+' www.'+LOCAL_DOMAIN+' # RCC2013_'+secrets.token_hex(8)+'\r\n').encode('ascii')
                with hosts_path.open('ab') as hosts:hosts.write(hosts_line)
                env['NO_PROXY'] = env.get('NO_PROXY','')+',127.0.0.1,localhost,.'+LOCAL_DOMAIN
            class JoinHandler(BaseHTTPRequestHandler):
                def do_GET(self):
                    parsed = urlsplit(self.path)
                    path = parsed.path
                    asset = parse_qs(parsed.query).get('id',[''])[0] if path.rstrip('/')=='/asset' else ''
                    record = {'method':'GET','path':path}
                    if asset:record['asset_id'] = asset[:20]
                    backend_requests.append(record)
                    if path=='/game/join.ashx':content,status = signer.sign(source) if signer else source.encode('utf-8'),200
                    elif asset in core_assets:
                        local_source = core_assets[asset].decode('utf-8')
                        for prefix in ('http://www.roblox.com','https://www.roblox.com','http://roblox.com','https://roblox.com'):
                            local_source = local_source.replace(prefix,base)
                        content,status = signer.sign(local_source),200
                    elif path in ('/game/studio.ashx','/game/visit.ashx'):
                        bootstrap = 'print('+json.dumps(markers[role]+'|CORE_BOOTSTRAP_READY')+')'
                        content,status = signer.sign(bootstrap) if signer else bootstrap.encode('utf-8'),200
                    elif path=='/Login/Negotiate.ashx':content,status = b'ok',200
                    elif path=='/game/logout.aspx':content,status = b'',200
                    else:content,status = b'Not found',404
                    record['status'] = status
                    self.send_response(status)
                    self.send_header('Content-Type','text/plain; charset=utf-8')
                    self.send_header('Content-Length',str(len(content)))
                    self.end_headers();self.wfile.write(content)
                def log_message(self,*args):pass
            backend = ThreadingHTTPServer(('127.0.0.1',80 if signer else 0),JoinHandler)
            backend_thread = threading.Thread(target=backend.serve_forever,daemon=True)
            backend_thread.start()
            base = 'http://www.'+LOCAL_DOMAIN if signer else 'http://127.0.0.1:'+str(backend.server_port)
            config = deployment/'AppSettings.xml'
            settings = ET.parse(config)
            base_node = settings.getroot().find('BaseUrl')
            if base_node is None:raise RuntimeError('Pinned Player BaseUrl setting missing')
            base_node.text = base
            settings.write(config,encoding='utf-8',xml_declaration=True)
            report['player_appsettings_sha256'] = hashlib.sha256(config.read_bytes()).hexdigest()
            command = [str(deployment/player.name),'-t','0','-a',base+'/Login/Negotiate.ashx','-j',base+'/game/join.ashx']
        else:
            command = [str(deployment/studio.name),'-ide']
            if role!='host' or args.host_profile=='test':command.append('-testMode')
            command.extend(['-fileLocation',str(place),'-script',source])
            if role=='host':report['host_test_mode'] = args.host_profile=='test'
        process = subprocess.Popen(command,
                                   cwd=deployment,env=env,stdout=stream,stderr=subprocess.STDOUT)
        processes[role] = process
        report['peers'][role] = {'pid':process.pid,'engine_marker_lines':[]}
    def observe(role):
        collect_logs(out/role)
        # Native engine events rotate among worker-thread files. Preserve every
        # observed owned marker, including those no longer in the newest 12 logs.
        root = Path(os.environ['LOCALAPPDATA'])/'Roblox'/'logs'
        paths = sorted((p for p in root.glob('*') if p.is_file() and p.suffix.lower() in ('.txt','.log')),
                       key=lambda p:p.stat().st_mtime)[-128:]
        paths.append(out/role/'process.log')
        lines = list(report['peers'][role]['engine_marker_lines'])
        for path in paths:
            text = path.read_bytes()[-2*1024*1024:].decode('utf-8',errors='replace')
            lines.extend(line for line in text.splitlines() if markers[role] in line)
        lines = list(dict.fromkeys(lines))
        report['peers'][role]['engine_marker_lines'] = lines
        (out/role/'engine-events.log').write_text('\n'.join(lines)+'\n',encoding='utf-8')
        return '\n'.join(lines)
    try:
        launch('host')
        deadline = time.monotonic()+args.timeout
        while time.monotonic()<deadline and processes['host'].poll() is None:
            host = observe('host')
            if '|ERROR|' in host: raise RuntimeError('Host Lua failed; inspect host evidence')
            if '|SERVER_READY|' in host:break
            time.sleep(1)
        else:raise RuntimeError('No native server startup marker before deadline')
        report['udp_port_bound_by_host'] = udp_binding(processes['host'].pid,port)
        report['server_hosting_validated'] = report['udp_port_bound_by_host'] is True
        if not report['server_hosting_validated']:raise RuntimeError('Host process has no matching UDP endpoint')
        launch('client')
        deadline = time.monotonic()+args.timeout
        while time.monotonic()<deadline and all(p.poll() is None for p in processes.values()):
            host, client = observe('host'), observe('client')
            if '|ERROR|' in host+client:raise RuntimeError('Peer Lua failed; inspect native evidence')
            if '|CONNECTION_FAILED|' in client:raise RuntimeError('Native client connection failed')
            report['client_join_validated'] = '|PLAYER_ADDED|' in host and '|CONNECTION_ACCEPTED' in client and '|REPLICATED_TOKEN|'+token in client
            report['standalone_player_join_validated'] = bool(player) and report['client_join_validated']
            report['replicated_movement_validated'] = report['client_join_validated'] and '|REPLICATED_MOVEMENT|' in client and '|ROUNDTRIP_CONFIRMED|' in host
            report['client_character_movement_validated'] = '|CLIENT_CHARACTER_MOVED|' in client and '|SERVER_CHARACTER_MOVED|' in host
            report['core_gui_validated'] = '|CORE_GUI_READY' in client
            if report['replicated_movement_validated'] and report['client_character_movement_validated'] and (args.player_profile!='local-signed' or report['core_gui_validated']):break
            time.sleep(1)
        report['passed'] = report['server_hosting_validated'] and report['replicated_movement_validated']
        if not report['passed']:report['error'] = 'Join/replication evidence incomplete before deadline'
        # A verified network round trip is separate from character locomotion.
        if not report['client_character_movement_validated']:
            report['movement_limitation'] = 'Character locomotion was not verified on both peers'
    except Exception as error:
        report['error'] = str(error)
    finally:
        from PIL import ImageGrab
        # The last-launched client is already foreground. Capture it first.
        for role, process in reversed(list(processes.items())):
            peer = out/role
            try:
                observe(role)
                records = windows_for_pid(process.pid) if player and role=='client' else resize_viewport(process.pid,{'width':640,'height':480})
                report['peers'][role]['windows'] = records
                user32 = ctypes.windll.user32
                user32.GetForegroundWindow.restype = wintypes.HWND
                owner = wintypes.DWORD()
                user32.GetWindowThreadProcessId(user32.GetForegroundWindow(),ctypes.byref(owner))
                if owner.value != process.pid:raise RuntimeError('Owned peer is not foreground')
                views = {tuple(w['rect']) for w in records if w['visible'] and w['title']=='QOgreWidget'}
                if player and role=='client':
                    candidates = [w for w in records if w['visible'] and w['top_level'] and w['rect'][2]-w['rect'][0]>=128 and w['rect'][3]-w['rect'][1]>=64]
                    if candidates:
                        window = max(candidates,key=lambda w:(w['rect'][2]-w['rect'][0])*(w['rect'][3]-w['rect'][1]))
                        views = {tuple(window['rect'])}
                        report['peers'][role]['capture_kind'] = 'standalone Player window diagnostic'
                if len(views)==1:ImageGrab.grab(bbox=next(iter(views))).save(peer/'viewport.png')
                ImageGrab.grab().save(peer/'runner-desktop.png')
            except Exception as error:report['peers'][role]['capture_error'] = str(error)
        for role, process in processes.items():
            report['peers'][role]['exit_code_before_cleanup'] = process.poll()
            if process.poll() is None:
                process.terminate()
                try:process.wait(timeout=10)
                except subprocess.TimeoutExpired:process.kill();process.wait(timeout=10)
        for stream in streams:stream.close()
        if backend:
            backend.shutdown();backend.server_close();backend_thread.join(timeout=5)
            report['backend_requests'] = backend_requests
            report['join_script_requested'] = any(r['path']=='/game/join.ashx' for r in backend_requests)
        if hosts_path and hosts_line:
            hosts_path.write_bytes(hosts_path.read_bytes().replace(hosts_line,b'',1))
        shutil.rmtree(runtime,ignore_errors=True)
        (out/'result.json').write_text(json.dumps(report,indent=2)+'\n',encoding='utf-8')
    print(json.dumps(report,indent=2))
    return 0 if report['passed'] else 1


if __name__ == '__main__':raise SystemExit(main())
