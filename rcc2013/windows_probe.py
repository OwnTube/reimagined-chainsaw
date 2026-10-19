"""Observe an owned scene in unmodified 2013 Studio with an owned Lua plugin."""
import argparse
import ctypes
from ctypes import wintypes
from datetime import datetime, timezone
import hashlib
import json
import os
from pathlib import Path
import re
import secrets
import subprocess
import time
import xml.etree.ElementTree as ET


def write_scene(path):
    root = ET.Element('roblox', version='4')
    for value in ('null', 'nil'):
        ET.SubElement(root, 'External').text = value
    workspace = ET.SubElement(root, 'Item', {'class': 'Workspace', 'referent': 'RBX0'})
    props = ET.SubElement(workspace, 'Properties')
    ET.SubElement(props, 'string', name='Name').text = 'Workspace'
    ET.ElementTree(root).write(path, encoding='utf-8', xml_declaration=True)


def plugin_source(marker):
    return '''
local marker = MARKER
print(marker .. "|PLUGIN_LOADED")
spawn(function()
    wait(5)
    local ok, problem = pcall(function()
        local world = game:GetService("Workspace")
        local model = Instance.new("Model")
        model.Name = "RCC2013_OwnedScene"
        model.Parent = world
        local function block(name, color, position, size)
            local part = Instance.new("Part")
            part.Name = name
            part.Anchored = true
            part.BrickColor = BrickColor.new(color)
            part.Size = size
            part.CFrame = CFrame.new(position)
            part.TopSurface = Enum.SurfaceType.Studs
            part.BottomSurface = Enum.SurfaceType.Smooth
            part.Parent = model
        end
        block("Floor", 194, Vector3.new(0,-0.5,0), Vector3.new(32,1,24))
        block("Red", 21, Vector3.new(-4,2,0), Vector3.new(3,4,3))
        block("Green", 37, Vector3.new(0,3,0), Vector3.new(4,6,4))
        block("Blue", 23, Vector3.new(4,2,0), Vector3.new(3,4,3))
        local camera = world.CurrentCamera
        if not camera then
            camera = Instance.new("Camera")
            camera.Parent = world
            world.CurrentCamera = camera
        end
        camera.CameraType = Enum.CameraType.Scriptable
        camera.CoordinateFrame = CFrame.new(Vector3.new(19,15,23), Vector3.new(0,2,0))
        camera.Focus = CFrame.new(0,2,0)
        camera.FieldOfView = 50
        print(marker .. "|SCENE_READY|" .. version())
    end)
    if not ok then print(marker .. "|SCENE_ERROR|" .. tostring(problem)) end
end)
'''.replace('MARKER', json.dumps(marker))


def collect_logs(output):
    candidates = list((Path(os.environ['LOCALAPPDATA'])/'Roblox'/'logs').glob('*'))
    chunks = []
    for path in sorted((p for p in candidates if p.is_file()), key=lambda p:p.stat().st_mtime)[-12:]:
        if path.suffix.lower() not in ('.txt', '.log'):
            continue
        text = path.read_bytes()[-2*1024*1024:].decode('utf-8', errors='replace')
        chunks.append(text)
        lines = []
        for line in text.splitlines():
            if re.search(r'cookie|authorization|access_token|password|ticket', line, re.I):
                lines.append('[redacted authentication metadata]')
            else:
                lines.append(re.sub(r'(https?://[^\s?#]+)[?#][^\s]*', r'\1', line))
        (output/path.name).write_text('\n'.join(lines)+'\n', encoding='utf-8')
    return '\n'.join(chunks)


def windows_for_pid(pid):
    user32 = ctypes.windll.user32
    callback_type = ctypes.WINFUNCTYPE(wintypes.BOOL, wintypes.HWND, wintypes.LPARAM)
    user32.GetWindowThreadProcessId.argtypes = [wintypes.HWND, ctypes.POINTER(wintypes.DWORD)]
    user32.GetWindowTextW.argtypes = [wintypes.HWND, wintypes.LPWSTR, ctypes.c_int]
    user32.GetClassNameW.argtypes = [wintypes.HWND, wintypes.LPWSTR, ctypes.c_int]
    user32.GetWindowRect.argtypes = [wintypes.HWND, ctypes.POINTER(wintypes.RECT)]
    user32.IsWindowVisible.argtypes = [wintypes.HWND]
    records = []
    def inspect(handle, _):
        owner = wintypes.DWORD()
        user32.GetWindowThreadProcessId(handle, ctypes.byref(owner))
        if owner.value == pid:
            title, name, rect = ctypes.create_unicode_buffer(2048), ctypes.create_unicode_buffer(256), wintypes.RECT()
            user32.GetWindowTextW(handle, title, len(title))
            user32.GetClassNameW(handle, name, len(name))
            user32.GetWindowRect(handle, ctypes.byref(rect))
            records.append({'title':title.value,'class':name.value,'visible':bool(user32.IsWindowVisible(handle)),
                            'rect':[rect.left,rect.top,rect.right,rect.bottom]})
        return True
    callback = callback_type(inspect)
    user32.EnumWindows(callback, 0)
    return records


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--studio', type=Path, required=True)
    parser.add_argument('--output', type=Path, default=Path('output'))
    args = parser.parse_args()
    if os.name != 'nt':
        parser.error('Native Windows is required')
    specs = json.loads(Path(__file__).with_name('packages.json').read_text())
    studio = args.studio.resolve(strict=True)
    if hashlib.sha256(studio.read_bytes()).hexdigest() != specs['studio']['executable_sha256']:
        parser.error('Executable identity mismatch')
    out = args.output.resolve()
    out.mkdir(parents=True, exist_ok=False)
    marker = 'RCC2013_'+secrets.token_hex(12)
    place = out/'Rcc2013OwnedScene.rbxlx'
    write_scene(place)
    plugin = studio.parent/'BuiltInPlugins'/'Rcc2013Probe'/'bootstrap.lua'
    plugin.parent.mkdir(parents=True, exist_ok=False)
    plugin.write_text(plugin_source(marker), encoding='utf-8')
    report = {'studio_sha256':specs['studio']['executable_sha256'],
              'scene_script_executed':False,'engine_render_validated':False,
              'screenshot_kind':'startup diagnostic, pending scene verification',
              'owned_addition':'BuiltInPlugins/Rcc2013Probe/bootstrap.lua',
              'launch_profile':'-ide -fileLocation owned.rbxlx'}
    env = os.environ.copy()
    env.pop('QT_PLUGIN_PATH', None)
    env.pop('QT_QPA_PLATFORM_PLUGIN_PATH', None)
    with (out/'process.log').open('wb') as log:
        process = subprocess.Popen([str(studio), '-ide', '-fileLocation', str(place)],
            cwd=studio.parent, env=env, stdout=log, stderr=subprocess.STDOUT)
        try:
            start = time.monotonic()
            while process.poll() is None and time.monotonic()-start < 60:
                text = collect_logs(out)+(out/'process.log').read_text(errors='replace')
                if marker+'|SCENE_READY|' in text:
                    report['scene_script_executed'] = True
                    report['engine_marker_lines'] = [line for line in text.splitlines() if marker in line]
                    time.sleep(4)
                    break
                time.sleep(1)
            collect_logs(out)
            report['windows'] = windows_for_pid(process.pid)
            report['exit_code_before_cleanup'] = process.poll()
            from PIL import ImageGrab
            ImageGrab.grab().save(out/'runner-desktop.png')
            report['captured_at_utc'] = datetime.now(timezone.utc).isoformat()
        finally:
            if process.poll() is None:
                process.terminate()
                try:
                    process.wait(timeout=10)
                except subprocess.TimeoutExpired:
                    process.kill()
                    process.wait(timeout=10)
            (out/'result.json').write_text(json.dumps(report, indent=2)+'\n', encoding='utf-8')
    print(json.dumps(report, indent=2))


if __name__ == '__main__':
    main()
