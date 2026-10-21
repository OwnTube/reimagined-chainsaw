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


def press_owned_key(pid, virtual_key, duration=1, method='system', activate=True):
    """Deliver one bounded key only while the owned Player is foreground."""
    records = windows_for_pid(pid)
    candidates = [w for w in records if w['visible'] and w['top_level'] and w['class']=='WINDOWSCLIENT']
    if len(candidates)!=1:raise RuntimeError('Expected one owned Player game window')
    user32 = ctypes.windll.user32
    user32.GetForegroundWindow.restype = wintypes.HWND
    user32.SetForegroundWindow(wintypes.HWND(candidates[0]['handle']))
    time.sleep(0.5)
    owner = wintypes.DWORD()
    user32.GetWindowThreadProcessId(user32.GetForegroundWindow(),ctypes.byref(owner))
    if owner.value!=pid:raise RuntimeError('Owned Player did not acquire keyboard focus')
    scan = user32.MapVirtualKeyW(virtual_key,0)
    window = wintypes.HWND(candidates[0]['handle'])
    user32.PostMessageW.argtypes = [wintypes.HWND,wintypes.UINT,wintypes.WPARAM,wintypes.LPARAM]
    metadata = {'method':method}
    kernel = ctypes.windll.kernel32
    session = wintypes.DWORD()
    if kernel.ProcessIdToSessionId(pid,ctypes.byref(session)):metadata['player_session_id'] = session.value
    kernel.WTSGetActiveConsoleSessionId.restype = wintypes.DWORD
    metadata['active_console_session_id'] = kernel.WTSGetActiveConsoleSessionId()
    class Mouse(ctypes.Structure):
        _fields_ = [('x',wintypes.LONG),('y',wintypes.LONG),('data',wintypes.DWORD),('flags',wintypes.DWORD),('time',wintypes.DWORD),('extra',ctypes.c_size_t)]
    class Key(ctypes.Structure):
        _fields_ = [('vk',wintypes.WORD),('scan',wintypes.WORD),('flags',wintypes.DWORD),('time',wintypes.DWORD),('extra',ctypes.c_size_t)]
    class Payload(ctypes.Union):_fields_ = [('mouse',Mouse),('key',Key)]
    class Input(ctypes.Structure):_fields_ = [('kind',wintypes.DWORD),('payload',Payload)]
    user32.SendInput.argtypes = [wintypes.UINT,ctypes.POINTER(Input),ctypes.c_int]
    # Activating the native client area gives DirectInput time to acquire its
    # keyboard before the bounded test key. Stay inside the owned game window.
    rect = wintypes.RECT()
    user32.GetClientRect(window,ctypes.byref(rect))
    point = wintypes.POINT(rect.right//2,rect.bottom//2)
    user32.ClientToScreen(window,ctypes.byref(point))
    user32.SetCursorPos(point.x,point.y)
    click = (Input*2)()
    click[0].kind=0;click[0].payload.mouse.flags=2
    click[1].kind=0;click[1].payload.mouse.flags=4
    if activate:
        metadata['activation_click_accepted'] = user32.SendInput(2,click,ctypes.sizeof(Input))
        time.sleep(2)
    user32.GetWindowThreadProcessId(user32.GetForegroundWindow(),ctypes.byref(owner))
    if owner.value!=pid:raise RuntimeError('Owned Player lost focus before keyboard test')
    def send_scan(up):
        event = Input();event.kind = 1;event.payload.key = Key(0,scan,8|(2 if up else 0),0,0)
        return user32.SendInput(1,ctypes.byref(event),ctypes.sizeof(event))
    try:
        if method=='message':
            if not user32.PostMessageW(window,0x100,virtual_key,1|(scan<<16)):raise ctypes.WinError()
        elif method=='scancode':metadata['send_input_down_accepted'] = send_scan(False)
        else:user32.keybd_event(virtual_key,scan,0,0)
        metadata['async_key_down'] = bool(user32.GetAsyncKeyState(virtual_key)&0x8000)
        time.sleep(duration)
    finally:
        if method=='message':user32.PostMessageW(window,0x101,virtual_key,1|(scan<<16)|0xc0000000)
        elif method=='scancode':metadata['send_input_up_accepted'] = send_scan(True)
        else:user32.keybd_event(virtual_key,scan,2,0)
    return metadata


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--studio',type=Path)
    parser.add_argument('--native-server',type=Path,help='Our compiled RCCService.exe; test harness remains Python')
    parser.add_argument('--custom-host',action='store_true',help='Launch our independent Python transport, without Studio')
    parser.add_argument('--player',type=Path,help='Experiment with the pinned standalone Player instead of a second Studio')
    parser.add_argument('--player-profile',choices=('stock','local-signed'),default='stock')
    parser.add_argument('--host-profile',choices=('test','player','local-player'),default='test',help='Player-host profiles omit Studio testMode')
    parser.add_argument('--core-loader',choices=('native','compat'),default='compat')
    parser.add_argument('--test-input',action='store_true',help='Send D only to the owned foreground Player after UI and walking pass')
    parser.add_argument('--input-method',choices=('system','message','scancode'),default='system')
    parser.add_argument('--trace-transport',action='store_true',help='Observe the owned connection through a loopback UDP relay')
    parser.add_argument('--record',action='store_true',help='Record actual joining and a short native keyboard/menu demonstration')
    parser.add_argument('--output',type=Path,default=Path('hosting2013/output'))
    parser.add_argument('--timeout',type=int,default=90)
    args = parser.parse_args()
    if args.native_server:args.custom_host=True
    if os.name != 'nt': parser.error('Native Windows required')
    if not 10 <= args.timeout <= 180: parser.error('Timeout must be 10..180 seconds')
    if args.player_profile=='local-signed' and not args.player:parser.error('local-signed requires the standalone Player')
    if args.test_input and (not args.player or args.player_profile!='local-signed'):parser.error('Input testing requires the configured standalone Player')
    if args.record and not args.test_input and not args.custom_host:parser.error('Recording requires the standalone keyboard-validated test')
    if not args.custom_host and not args.studio:parser.error('Reference host requires --studio')
    if args.custom_host and (not args.player or args.player_profile!='local-signed'):parser.error('Custom host requires configured standalone Player')
    if args.custom_host and (args.trace_transport or args.test_input):parser.error('Transport checkpoint does not yet provide a world or keyboard test')
    studio = args.studio.resolve(strict=True) if args.studio else None
    specs = json.loads((Path(__file__).resolve().parents[1]/'rcc2013/packages.json').read_text())
    digest = hashlib.sha256(studio.read_bytes()).hexdigest() if studio else None
    if studio and digest != specs['studio']['executable_sha256']: raise ValueError('Studio identity mismatch')
    player = args.player.resolve(strict=True) if args.player else None
    if player and hashlib.sha256(player.read_bytes()).hexdigest() != specs['player']['executable_sha256']:
        raise ValueError('Standalone Player identity mismatch')
    out = args.output.resolve(); out.mkdir(parents=True,exist_ok=False)
    with socket.socket(socket.AF_INET,socket.SOCK_DGRAM) as sock:
        sock.bind(('127.0.0.1',0)); port = sock.getsockname()[1]
    client_port = port
    relay = None
    token = secrets.token_hex(24)
    markers = {role:'RCCJOIN_'+role+'_'+secrets.token_hex(12) for role in ('host','client')}
    report = {'passed':False,'scope':'two separate unmodified 2013 Studio peers on loopback',
              'studio_sha256':digest,'port':port,'server_hosting_validated':False,
              'client_join_validated':False,'replicated_movement_validated':False,
              'client_character_movement_validated':False,'standalone_player_join_validated':False,
              'launch_profile':'-ide -testMode -fileLocation distinct empty local places -script owned Lua','peers':{}}
    report['client_kind'] = 'standalone_player' if player else 'studio'
    report['core_loader'] = args.core_loader
    report['host_profile'] = args.host_profile
    if args.host_profile!='test':report['launch_profile'] = '-ide -fileLocation empty local place -script owned Lua (without testMode)'
    if player:
        report['scope'] = 'unmodified 2013 Studio host and standalone Player on loopback'
        report['player_sha256'] = specs['player']['executable_sha256']
        report['client_launch_profile'] = '-t 0 -a loopback /Login/Negotiate.ashx -j loopback /game/join.ashx'
        report['player_configuration'] = 'copied AppSettings.xml BaseUrl points only to the owned loopback backend'
    backend_requests = []
    backend, backend_thread = None, None
    hosts_path, hosts_line = None, None
    processes, streams = {}, []
    recording = None
    executables = {}
    # Runtime copies are outside the evidence folder: never upload executables.
    runtime = (player if args.custom_host else studio).parent.parent/('join-'+secrets.token_hex(6))
    runtime.mkdir()
    def launch(role):
        nonlocal backend, backend_thread, hosts_path, hosts_line
        if role=='host' and args.custom_host:
            peer=out/role;peer.mkdir()
            stream=(peer/'process.log').open('wb');streams.append(stream)
            script=Path(__file__).resolve().parents[1]/'server2013/server.py'
            command=[sys.executable,str(script),'--port',str(port),'--output',str(peer),'--duration',str(min(180,args.timeout+30))]
            if args.native_server:
                command=[str(args.native_server.resolve(strict=True)),'-console','--network-only','--port',str(port),'--output',str(peer),'--duration',str(min(180,args.timeout+30))]
            process=subprocess.Popen(command,stdout=stream,stderr=subprocess.STDOUT)
            processes[role]=process;executables[role]=args.native_server.resolve() if args.native_server else Path(sys.executable)
            report['peers'][role]={'pid':process.pid,'engine_marker_lines':[]}
            return
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
        source = script_source(role,markers[role],client_port if role=='client' else port,token)
        peer = out/role; peer.mkdir()
        (peer/'bootstrap.lua').write_text(source,encoding='utf-8')
        place = peer/'empty.rbxlx'; write_scene(place)
        stream = (peer/'process.log').open('wb'); streams.append(stream)
        env = os.environ.copy()
        for key in ('QT_PLUGIN_PATH','QT_QPA_PLATFORM_PLUGIN_PATH'):env.pop(key,None)
        if standalone:
            signer = None
            core_assets = {}
            core_images = {}
            if args.player_profile=='local-signed':
                from local_player import configure, LOCAL_DOMAIN
                from core_assets import restore, restore_images
                core_assets,core_manifest = ({},{}) if args.custom_host else restore(runtime/'core-assets')
                report['core_assets'] = core_manifest
                core_images,image_manifest = ({},{}) if args.custom_host else restore_images(runtime/'core-images')
                report['core_images'] = image_manifest
                if not args.custom_host:source = source.replace('local loadCoreGui = false','local loadCoreGui = true')
                # The native local-RCC flag is consulted in the numeric-address
                # branch; literal localhost follows a different handshake path.
                source = source.replace('network:PlayerConnect(0, "localhost",','network:PlayerConnect(0, "127.0.0.1",')
                (peer/'bootstrap.lua').write_text(source,encoding='utf-8')
                signer,configuration = configure(deployment/player.name)
                report['local_player_configuration'] = configuration
                report['player_sha256'] = configuration['configured_sha256']
                report['scope'] = ('native C++ RCCService.exe and native 2013 Player; no Studio host' if args.native_server else 'independent Python transport and native 2013 Player; no Studio host') if args.custom_host else 'unmodified 2013 Studio host and locally configured standalone 2013 Player'
                settings_dir = deployment/'ClientSettings'
                settings_dir.mkdir(exist_ok=True)
                player_flags = {'FFlagDebugLocalRccServerConnection':'True','FLogCoreScripts':'1'}
                (settings_dir/'ClientAppSettings.json').write_text(json.dumps(player_flags),encoding='utf-8')
                report['player_local_flags'] = player_flags
                hosts_path = Path(os.environ['WINDIR'])/'System32/drivers/etc/hosts'
                hosts_line = ('\r\n127.0.0.1 '+LOCAL_DOMAIN+' www.'+LOCAL_DOMAIN+' # RCC2013_'+secrets.token_hex(8)+'\r\n').encode('ascii')
                with hosts_path.open('ab') as hosts:hosts.write(hosts_line)
                env['NO_PROXY'] = env.get('NO_PROXY','')+',127.0.0.1,localhost,.'+LOCAL_DOMAIN
            class JoinHandler(BaseHTTPRequestHandler):
                def do_GET(self):
                    parsed = urlsplit(self.path)
                    path = parsed.path
                    asset = parse_qs(parsed.query).get('id',[''])[0] if path.lower().rstrip('/')=='/asset' else ''
                    record = {'method':'GET','path':path}
                    if asset:record['asset_id'] = asset[:20]
                    backend_requests.append(record)
                    content_type = 'text/plain; charset=utf-8'
                    if path=='/game/join.ashx':content,status = signer.sign(source) if signer else source.encode('utf-8'),200
                    elif asset in ('900000001','900000002'):
                        owned = 'print('+json.dumps(markers[role]+'|CORE_PROBE_RAN|'+asset)+')\n'
                        content,status = (signer.sign(owned,legacy=True) if asset=='900000001' else owned.encode('utf-8')),200
                    elif asset=='900000003':
                        owned = 'print('+json.dumps(markers[role]+'|CORE_PROBE_RAN|'+asset)+')\n'
                        root = ET.Element('roblox',version='4')
                        item = ET.SubElement(root,'Item',{'class':'Script','referent':'RBX0'})
                        props = ET.SubElement(item,'Properties')
                        ET.SubElement(props,'ProtectedString',name='Source').text = owned
                        content,status = ET.tostring(root,encoding='utf-8',xml_declaration=True),200
                    elif asset in core_assets:
                        local_source = core_assets[asset].decode('utf-8')
                        for prefix in ('http://www.roblox.com','https://www.roblox.com','http://roblox.com','https://roblox.com'):
                            local_source = local_source.replace(prefix,base)
                        content,status = signer.sign(local_source,legacy=True),200
                    elif asset in core_images:
                        content,status = core_images[asset],200
                        content_type = 'image/png'
                    elif path in ('/game/studio.ashx','/game/visit.ashx'):
                        bootstrap = 'print('+json.dumps(markers[role]+'|CORE_BOOTSTRAP_READY')+')\n'
                        if signer and args.core_loader=='compat' and not args.custom_host:
                            from core_loader import bootstrap as build_core_loader
                            bootstrap += build_core_loader(core_assets,base,markers[role])
                        elif signer and not args.custom_host:
                            bootstrap += ('local context=game:GetService("ScriptContext")\n'
                                          'print('+json.dumps(markers[role]+'|SCRIPTS_DISABLED_BEFORE|')+'..tostring(context.ScriptsDisabled))\n'
                                          'context.ScriptsDisabled=false\n'
                                          'print('+json.dumps(markers[role]+'|SCRIPTS_DISABLED_AFTER|')+'..tostring(context.ScriptsDisabled))\n'
                                          'local gui=game:GetService("CoreGui"):FindFirstChild("RobloxGui")\n'
                                          'context:AddCoreScript(900000001,gui,"RccSignedProbe")\n'
                                          'context:AddCoreScript(900000002,gui,"RccPlainProbe")\n'
                                          'context:AddCoreScript(900000003,gui,"RccXmlProbe")\n')
                            # Execute the archived root in the native signed web
                            # loader; it then creates the original child CoreScripts.
                            bootstrap += core_assets['37801172'].decode('utf-8')
                        content,status = signer.sign(bootstrap) if signer else bootstrap.encode('utf-8'),200
                    elif path=='/Login/Negotiate.ashx':content,status = b'ok',200
                    elif path=='/game/logout.aspx':content,status = b'',200
                    else:content,status = b'Not found',404
                    record['status'] = status
                    self.send_response(status)
                    self.send_header('Content-Type',content_type)
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
            if role=='host' and args.host_profile=='local-player':
                settings_dir = deployment/'ClientSettings'
                settings_dir.mkdir(exist_ok=True)
                local_flags = {'FFlagDebugLocalRccServerConnection':'True'}
                (settings_dir/'ClientAppSettings.json').write_text(json.dumps(local_flags),encoding='utf-8')
                report['host_local_flags'] = local_flags
            command = [str(deployment/studio.name),'-ide']
            if role!='host' or args.host_profile=='test':command.append('-testMode')
            command.extend(['-fileLocation',str(place),'-script',source])
            if role=='host':report['host_test_mode'] = args.host_profile=='test'
        process = subprocess.Popen(command,
                                   cwd=deployment,env=env,stdout=stream,stderr=subprocess.STDOUT)
        processes[role] = process
        executables[role] = deployment/(player.name if standalone else studio.name)
        report['peers'][role] = {'pid':process.pid,'engine_marker_lines':[]}
    def observe(role):
        if role=='host' and args.custom_host:
            path=out/role/'server-result.json'
            if path.exists():
                state=json.loads(path.read_text())
                report['custom_server']=state
                return '|SERVER_READY|' if state['port']==port else ''
            return ''
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
        if args.record:
            from windows_recording import DesktopRecording
            recording=DesktopRecording(out)
            recording.event('custom RCC host launch requested; no Studio' if args.custom_host else 'Studio host launch requested')
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
        if recording:recording.event('custom RCC ready with verified same-process UDP binding' if args.custom_host else 'Studio server ready with verified same-process UDP binding')
        try:
            if args.custom_host:raise ValueError('Custom host has no Roblox engine memory profile')
            from native_profile import inspect
            report['host_native_profile'] = inspect(processes['host'],executables['host'])
        except Exception as error:report['host_native_profile_error'] = str(error)
        if recording:recording.event('standalone Roblox Player launch requested')
        if args.trace_transport:
            from transport_trace import LoopbackRelay
            relay = LoopbackRelay(port,out/'transport-trace.json')
            client_port = relay.port
            relay.start()
            report['transport_relay_port'] = client_port
        launch('client')
        maximized=False
        deadline = time.monotonic()+args.timeout
        while time.monotonic()<deadline and all(p.poll() is None for p in processes.values()):
            host, client = observe('host'), observe('client')
            if recording and not maximized:
                candidates=[w for w in windows_for_pid(processes['client'].pid) if w['visible'] and w['top_level'] and w['class']=='WINDOWSCLIENT']
                if len(candidates)==1:
                    ctypes.windll.user32.ShowWindow(wintypes.HWND(candidates[0]['handle']),3)
                    maximized=True
                    recording.event('owned standalone Player window maximized')
            if args.custom_host:
                state=report.get('custom_server',{})
                report['custom_transport_handshake_validated'] = state.get('transport_handshake_observed',False) and '|CONNECTION_ACCEPTED' in client
                if report['custom_transport_handshake_validated']:
                    if recording:recording.event('native Player accepted transport; world replication is unfinished')
                    time.sleep(5);observe('host');observe('client');break
            if '|ERROR|' in host+client:raise RuntimeError('Peer Lua failed; inspect native evidence')
            if '|CONNECTION_FAILED|' in client:
                # Retain a short diagnostic interval for asynchronous UI loading.
                time.sleep(8)
                observe('host');observe('client')
                raise RuntimeError('Native client connection failed')
            report['client_join_validated'] = '|PLAYER_ADDED|' in host and '|CONNECTION_ACCEPTED' in client and '|REPLICATED_TOKEN|'+token in client
            report['standalone_player_join_validated'] = bool(player) and report['client_join_validated']
            report['replicated_movement_validated'] = report['client_join_validated'] and '|REPLICATED_MOVEMENT|' in client and '|ROUNDTRIP_CONFIRMED|' in host
            report['client_character_movement_validated'] = '|CLIENT_CHARACTER_MOVED|' in client and '|SERVER_CHARACTER_MOVED|' in host
            report['core_gui_validated'] = '|CORE_GUI_READY' in client
            if report['replicated_movement_validated'] and report['client_character_movement_validated'] and (args.player_profile!='local-signed' or report['core_gui_validated']) and (not args.test_input or '|CLIENT_WALK_STOPPED' in client):break
            time.sleep(1)
        report['keyboard_movement_validated'] = False
        if recording:recording.event('network, character, and archived GUI observations collected')
        if args.test_input and player and report.get('core_gui_validated') and '|CLIENT_WALK_STOPPED' in client:
            time.sleep(1)
            report['keyboard_os_evidence'] = press_owned_key(processes['client'].pid,0x44,method=args.input_method)
            report['keyboard_input_sent'] = True
            report['keyboard_input_method'] = args.input_method
            if recording:recording.event('OS D key press delivered to owned Player')
            input_deadline = time.monotonic()+8
            while time.monotonic()<input_deadline:
                host,client = observe('host'),observe('client')
                report['keyboard_movement_validated'] = '|CLIENT_KEYBOARD_MOVED|' in client and '|SERVER_KEYBOARD_MOVED|' in host
                if report['keyboard_movement_validated']:break
                time.sleep(0.5)
        report['network_test_passed'] = report['server_hosting_validated'] and report['replicated_movement_validated']
        report['passed'] = report['network_test_passed'] and report['client_character_movement_validated'] and (args.player_profile!='local-signed' or report.get('core_gui_validated',False)) and (not args.test_input or report['keyboard_movement_validated'])
        if not report['passed']:
            if not report['network_test_passed']:report['error'] = 'Join/replication evidence incomplete before deadline'
            elif not report.get('core_gui_validated',False):report['error'] = 'Archived CoreGui evidence incomplete before deadline'
            elif args.test_input and not report['keyboard_movement_validated']:report['error'] = 'Native keyboard movement was not verified on both peers'
            else:report['error'] = 'Character movement evidence incomplete before deadline'
        if args.custom_host:
            report['game_join_validated']=False
            report['passed']=False
            report['error']='Custom host transport experiment only: Roblox world replication and simulation are not implemented'
            report['host_kind']='custom_cpp' if args.native_server else 'custom_python'
            if args.native_server:report['custom_executable_sha256']=hashlib.sha256(args.native_server.read_bytes()).hexdigest()
            report['studio_launched']=False
            report['probe_checkpoint']='transport handshake; full game join remains false'
            report['probe_checkpoint_passed']=report.get('custom_transport_handshake_validated',False) and report['udp_port_bound_by_host']
            if args.native_server:
                from correlate_service_guids import verify_custom_globals
                binding=verify_custom_globals(report.get('custom_server',{}),report['peers']['client']['engine_marker_lines'])
                report['custom_globals_binding_observation']=binding
                report['custom_globals_binding_validated']=binding['validated']
                from verify_owned_schema import verify_delivery
                schema_delivery=verify_delivery(report.get('custom_server',{}))
                report['custom_schema_delivery']=schema_delivery
                report['custom_schema_delivery_validated']=schema_delivery['transport_delivery_validated']
                report['probe_checkpoint']='transport, server-generated service GUID binding and schema datagram ACKs; schema application and full game join remain unproved'
                report['probe_checkpoint_passed']=report['probe_checkpoint_passed'] and binding['validated'] and schema_delivery['transport_delivery_validated']
                report['error']=('Custom host globals checkpoint only: owned world replication and simulation remain unimplemented'
                                 if binding['validated'] else 'Server-generated service GUIDs were not observed completely in native Player objects')
        # A verified network round trip is separate from character locomotion.
        if not report['client_character_movement_validated']:
            report['movement_limitation'] = 'Character locomotion was not verified on both peers'
        if recording and report['passed']:
            recording.event('native join, replication, GUI, and keyboard checks passed')
            for key,duration in ((0x41,0.6),(0x57,0.6),(0x20,0.1)):
                press_owned_key(processes['client'].pid,key,duration,method='scancode',activate=False)
                time.sleep(0.8)
            recording.event('additional native A, W, and Space keys delivered')
            press_owned_key(processes['client'].pid,0x1b,0.1,method='scancode',activate=False)
            time.sleep(3)
            client=observe('client')
            report['native_menu_opened']='|NATIVE_MENU_SHOWN' in client
            recording.event('Escape menu demonstration')
            from PIL import ImageGrab
            ImageGrab.grab().save(out/'client'/'menu-desktop.png')
            press_owned_key(processes['client'].pid,0x1b,0.1,method='scancode',activate=False)
            time.sleep(3)
            client=observe('client')
            report['native_menu_closed']='|NATIVE_MENU_CLOSED_AFTER_OPEN' in client
    except Exception as error:
        report['passed'] = False
        report['error'] = str(error)
    finally:
        if recording:
            report['recording']=recording.finish()
            if not report['recording']['validated']:
                report['passed']=False
                report['recording_error']=report['recording'].get('error','Recording did not validate')
        from PIL import ImageGrab
        # The last-launched client is already foreground. Capture it first.
        for role, process in reversed(list(processes.items())):
            peer = out/role
            try:
                observe(role)
                if process.poll() is None and not (args.custom_host and role=='host'):
                    try:
                        from native_profile import inspect
                        report['peers'][role]['native_profile'] = inspect(process,executables[role],bool(player and role=='client'))
                    except Exception as error:report['peers'][role]['native_profile_error'] = str(error)
                if args.custom_host and role=='host':continue
                records = windows_for_pid(process.pid) if player and role=='client' else resize_viewport(process.pid,{'width':640,'height':480})
                report['peers'][role]['windows'] = records
                user32 = ctypes.windll.user32
                user32.GetForegroundWindow.restype = wintypes.HWND
                if player and role=='client':
                    candidates = [w for w in records if w['visible'] and w['top_level']]
                    if candidates:
                        window = max(candidates,key=lambda w:max(0,w['rect'][2]-w['rect'][0])*max(0,w['rect'][3]-w['rect'][1]))
                        user32.SetForegroundWindow(wintypes.HWND(window['handle']))
                        time.sleep(0.5)
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
        if relay:report['transport_trace'] = relay.close()
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
    return 0 if report.get('probe_checkpoint_passed',report['passed']) and (not recording or report.get('recording',{}).get('validated')) else 1


if __name__ == '__main__':raise SystemExit(main())
