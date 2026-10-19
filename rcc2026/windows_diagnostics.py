"""Record startup evidence from a disposable Windows test runner."""
import ctypes
import json
import os
from pathlib import Path
import shutil


def capture_startup(output, process_id):
    output = Path(output) / 'startup-diagnostics'
    output.mkdir(exist_ok=True)
    report = {'process_id': process_id, 'windows': [], 'errors': []}
    try:
        from ctypes import wintypes
        user32 = ctypes.windll.user32
        user32.GetWindowThreadProcessId.argtypes = [wintypes.HWND, ctypes.POINTER(wintypes.DWORD)]
        user32.GetWindowTextW.argtypes = [wintypes.HWND, wintypes.LPWSTR, ctypes.c_int]
        user32.IsWindowVisible.argtypes = [wintypes.HWND]
        callback_type = ctypes.WINFUNCTYPE(wintypes.BOOL, wintypes.HWND, wintypes.LPARAM)

        def inspect_window(handle, _):
            pid = wintypes.DWORD()
            user32.GetWindowThreadProcessId(handle, ctypes.byref(pid))
            if pid.value == process_id:
                title = ctypes.create_unicode_buffer(2048)
                user32.GetWindowTextW(handle, title, len(title))
                report['windows'].append({'title': title.value,
                                          'visible': bool(user32.IsWindowVisible(handle))})
            return True

        user32.EnumWindows(callback_type(inspect_window), 0)
    except Exception as error:
        report['errors'].append('Window inspection: ' + str(error))
    try:
        from PIL import ImageGrab
        ImageGrab.grab().save(output / 'runner-desktop.png')
        report['screenshot_kind'] = 'Windows desktop diagnostic; not an engine render'
    except Exception as error:
        report['errors'].append('Desktop capture: ' + str(error))
    try:
        logs = Path(os.environ['LOCALAPPDATA']) / 'Roblox' / 'logs'
        for source in sorted(logs.glob('*.log'), key=lambda p: p.stat().st_mtime)[-10:]:
            shutil.copyfile(source, output / source.name)
    except Exception as error:
        report['errors'].append('Studio logs: ' + str(error))
    (output / 'startup.json').write_text(json.dumps(report, indent=2), encoding='utf-8')
