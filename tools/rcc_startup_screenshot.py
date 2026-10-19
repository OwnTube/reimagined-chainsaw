"""Capture the left panel of the pinned Studio launch on a disposable runner."""
import argparse
import ctypes
from ctypes import wintypes
from datetime import datetime, timezone
import hashlib
import json
import os
from pathlib import Path
import secrets
import subprocess
import sys
import time

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'rcc2026'))
from windows_probe import STUDIO_SHA256, studio_environment
from windows_server_probe import write_place, read_startup_observations


def capture_left_panel(process_id, destination):
    from PIL import ImageGrab
    user32 = ctypes.windll.user32
    user32.SetProcessDPIAware()
    callback_type = ctypes.WINFUNCTYPE(wintypes.BOOL, wintypes.HWND, wintypes.LPARAM)
    user32.EnumWindows.argtypes = [callback_type, wintypes.LPARAM]
    user32.GetWindowThreadProcessId.argtypes = [wintypes.HWND, ctypes.POINTER(wintypes.DWORD)]
    user32.GetWindowTextW.argtypes = [wintypes.HWND, wintypes.LPWSTR, ctypes.c_int]
    user32.IsWindowVisible.argtypes = [wintypes.HWND]
    user32.GetWindowRect.argtypes = [wintypes.HWND, ctypes.POINTER(wintypes.RECT)]
    user32.MoveWindow.argtypes = [wintypes.HWND, ctypes.c_int, ctypes.c_int,
                                  ctypes.c_int, ctypes.c_int, wintypes.BOOL]
    user32.SetForegroundWindow.argtypes = [wintypes.HWND]
    windows = []

    def inspect(handle, _):
        pid = wintypes.DWORD()
        user32.GetWindowThreadProcessId(handle, ctypes.byref(pid))
        if pid.value == process_id and user32.IsWindowVisible(handle):
            title = ctypes.create_unicode_buffer(2048)
            user32.GetWindowTextW(handle, title, len(title))
            if title.value == 'Roblox Studio':
                windows.append(handle)
        return True

    user32.EnumWindows(callback_type(inspect), 0)
    if not windows:
        raise RuntimeError('No visible Studio window owned by this process')
    handle = windows[0]
    if user32.GetSystemMetrics(0) < 1024 or user32.GetSystemMetrics(1) < 728:
        raise RuntimeError('Unexpected runner desktop dimensions')
    if not user32.MoveWindow(handle, 0, 0, 1024, 728, True):
        raise RuntimeError('Could not position the owned Studio window')
    user32.SetForegroundWindow(handle)
    time.sleep(2)
    rect = wintypes.RECT()
    if not user32.GetWindowRect(handle, ctypes.byref(rect)):
        raise RuntimeError('Could not inspect the owned window bounds')
    if (rect.left, rect.top, rect.right, rect.bottom) != (0, 0, 1024, 728):
        raise RuntimeError('Studio window geometry differs from the pinned capture layout')
    # Acquire only the left panel. In this pinned 1024px layout the Quick
    # Sign-In challenge is in the right panel; it never enters the image.
    ImageGrab.grab(bbox=(0, 0, 460, 728)).save(destination)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--studio', type=Path, required=True)
    parser.add_argument('--output', type=Path, required=True)
    args = parser.parse_args()
    if os.name != 'nt':
        parser.error('Requires Windows')
    studio = args.studio.resolve(strict=True)
    if hashlib.sha256(studio.read_bytes()).hexdigest() != STUDIO_SHA256:
        parser.error('Studio hash differs from the pinned build')
    out = args.output.resolve()
    out.mkdir(parents=True, exist_ok=False)
    place = out / 'owned-place.rbxlx'
    write_place(place, 'RCCSCREENSHOT_'+secrets.token_hex(16)+':')
    command = [str(studio), '-task', 'StartServer', '-localProjectFile', str(place),
        '-placeId', '0', '-universeId', '0', '-port', '53640', '-creatorId', '0',
        '-creatorType', '0', '-placeVersion', '0', '-numTestServerPlayersUponStartup', '0']
    report = {'studio_sha256': STUDIO_SHA256, 'screenshot_kind': 'partial Windows startup capture',
              'capture_region': 'left 460x728 of an owned 1024x728 Studio window',
              'right_signin_challenge_panel': 'excluded at capture',
              'engine_render_validated': False, 'hosting_validated': False}
    process = subprocess.Popen(command, cwd=studio.parent, env=studio_environment(studio),
                               stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    try:
        deadline = time.monotonic()+90
        while process.poll() is None and time.monotonic() < deadline:
            observations = read_startup_observations(process.pid)
            report['startup_observations'] = observations
            if observations['launch_arguments_rejected'] or observations['launch_values_rejected']:
                raise RuntimeError('Studio rejected the current launch profile')
            if observations['login_surface_observed']:
                time.sleep(5)
                capture_left_panel(process.pid, out/'rcc-current-startup.png')
                report['captured_at_utc'] = datetime.now(timezone.utc).isoformat()
                report['screenshot_captured'] = True
                break
            time.sleep(1)
        if not report.get('screenshot_captured'):
            raise RuntimeError('No recognized sign-in surface appeared within the capture budget')
    finally:
        if process.poll() is None:
            process.terminate()
            try:
                process.wait(timeout=10)
            except subprocess.TimeoutExpired:
                process.kill()
                process.wait(timeout=10)
        (out/'capture.json').write_text(json.dumps(report, indent=2)+'\n', encoding='utf-8')
    print(json.dumps(report, indent=2))


if __name__ == '__main__':
    main()
