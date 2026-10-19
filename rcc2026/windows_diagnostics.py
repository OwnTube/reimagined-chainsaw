"""Record startup evidence from a disposable Windows test runner."""
import ctypes
import json
import os
from pathlib import Path
import re


def sanitize_log(text):
    """Keep startup diagnostics without publishing authentication material."""
    output = []
    for line in text.splitlines():
        if re.search(r'QuickSignInUtil|\.ROBLOSECURITY|\b(?:authorization|access_token|refresh_token|privateKey)\b', line, re.I):
            output.append('[redacted authentication metadata]')
        else:
            output.append(re.sub(r'https?://[^\s\'"<>]+',
                                 lambda m: re.split(r'[?#]', m.group(0), maxsplit=1)[0], line))
    return '\n'.join(output) + '\n'


def omit_desktop_capture(text):
    """Avoid capturing a sign-in challenge, including before its QR event is logged."""
    return ('[FLog::QuickSignInUtil]' in text or
            bool(re.search(r'Authenticated\s*:\s*NO', text) and 'LoginPageOpenTime' in text))


def capture_startup(output, process_id):
    output = Path(output) / 'startup-diagnostics'
    output.mkdir(exist_ok=True)
    report = {'process_id': process_id, 'windows': [], 'errors': []}
    own_log_text = ''
    try:
        logs = Path(os.environ['LOCALAPPDATA']) / 'Roblox' / 'logs'
        for source in sorted(logs.glob('*.log'), key=lambda p: p.stat().st_mtime)[-10:]:
            text = source.read_bytes()[-4 * 1024 * 1024:].decode('utf-8', errors='replace')
            if f"for process '{int(process_id)}'" in text:
                own_log_text += text
            (output / source.name).write_text(sanitize_log(text), encoding='utf-8')
        report['log_policy'] = 'last 4 MiB per log; authentication metadata redacted'
    except Exception as error:
        report['errors'].append('Studio logs: ' + str(error))
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
        if omit_desktop_capture(own_log_text):
            report['screenshot_omitted'] = 'Unauthenticated sign-in surface can contain a live authentication challenge'
        else:
            from PIL import ImageGrab
            ImageGrab.grab().save(output / 'runner-desktop.png')
            report['screenshot_kind'] = 'Windows desktop diagnostic; not an engine render'
    except Exception as error:
        report['errors'].append('Desktop capture: ' + str(error))
    (output / 'startup.json').write_text(json.dumps(report, indent=2), encoding='utf-8')
