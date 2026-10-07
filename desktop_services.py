"""Windows 桌面服务：配置、显示器、托盘、原声和开机启动。"""
from __future__ import annotations

import ctypes
from ctypes import wintypes
import json
from pathlib import Path
import queue
import subprocess
import threading

PROJECT = Path(__file__).resolve().parent
SETTINGS_PATH = PROJECT / 'settings.json'
RUN_KEY = r'Software\Microsoft\Windows\CurrentVersion\Run'
RUN_NAME = 'NailongDesktopPet'


def load_settings() -> dict:
    try:
        value = json.loads(SETTINGS_PATH.read_text(encoding='utf-8'))
        return value if isinstance(value, dict) else {}
    except (OSError, ValueError):
        return {}


def save_settings(value: dict) -> None:
    temporary = SETTINGS_PATH.with_suffix('.tmp')
    temporary.write_text(json.dumps(value, ensure_ascii=False, indent=2), encoding='utf-8')
    temporary.replace(SETTINGS_PATH)


def monitors() -> list[tuple[int, int, int, int]]:
    """返回各显示器工作区域，支持负坐标。"""
    class MonitorInfo(ctypes.Structure):
        _fields_ = [('cbSize', wintypes.DWORD), ('rcMonitor', wintypes.RECT),
                    ('rcWork', wintypes.RECT), ('dwFlags', wintypes.DWORD)]

    areas = []
    callback_type = ctypes.WINFUNCTYPE(wintypes.BOOL, wintypes.HMONITOR,
                                      wintypes.HDC, ctypes.POINTER(wintypes.RECT), wintypes.LPARAM)

    def collect(handle, _dc, _rect, _data):
        info = MonitorInfo()
        info.cbSize = ctypes.sizeof(info)
        get_info = ctypes.windll.user32.GetMonitorInfoW
        get_info.argtypes = [wintypes.HMONITOR, ctypes.POINTER(MonitorInfo)]
        if get_info(handle, ctypes.byref(info)):
            r = info.rcWork
            areas.append((r.left, r.top, r.right, r.bottom))
        return True

    callback = callback_type(collect)
    ctypes.windll.user32.EnumDisplayMonitors(None, None, callback, 0)
    return areas or [(0, 0, 1920, 1080)]


def place_in_monitor(x: int, y: int, width: int, height: int, snap: bool = False):
    areas = monitors()
    def distance(area):
        left, top, right, bottom = area
        cx, cy = x + width / 2, y + height / 2
        return max(left - cx, 0, cx - right)**2 + max(top - cy, 0, cy - bottom)**2
    left, top, right, bottom = min(areas, key=distance)
    x = max(left, min(x, right - width))
    y = max(top, min(y, bottom - height))
    if snap:
        if abs(x - left) < 24:
            x = left
        elif abs(x + width - right) < 24:
            x = right - width
        if abs(y - top) < 24:
            y = top
        elif abs(y + height - bottom) < 24:
            y = bottom - height
    return round(x), round(y)


def autostart_enabled() -> bool:
    import winreg
    try:
        with winreg.OpenKey(winreg.HKEY_CURRENT_USER, RUN_KEY) as key:
            command, _ = winreg.QueryValueEx(key, RUN_NAME)
            return command == autostart_command()
    except OSError:
        return False


def autostart_command() -> str:
    executable = PROJECT / '.venv' / 'Scripts' / 'pythonw.exe'
    return f'"{executable}" "{PROJECT / "launcher.pyw"}"'


def set_autostart(enabled: bool) -> None:
    import winreg
    with winreg.CreateKey(winreg.HKEY_CURRENT_USER, RUN_KEY) as key:
        if enabled:
            winreg.SetValueEx(key, RUN_NAME, 0, winreg.REG_SZ, autostart_command())
        else:
            try:
                winreg.DeleteValue(key, RUN_NAME)
            except FileNotFoundError:
                pass


class Audio:
    def __init__(self, video: Path, events: queue.Queue):
        self.sound = None
        self.status = '正在准备原声'
        self.closed = False
        self.events = events
        self.lock = threading.Lock()
        threading.Thread(target=self._prepare, args=(video,), daemon=True).start()

    def _prepare(self, video):
        try:
            import imageio_ffmpeg
            import pygame
            cache = PROJECT / '.cache'
            cache.mkdir(exist_ok=True)
            target = cache / 'original-8s.wav'
            signature = f'{video.resolve()}:{video.stat().st_mtime_ns}:{video.stat().st_size}'
            stamp = cache / 'audio-source.txt'
            if not target.exists() or not stamp.exists() or stamp.read_text(encoding='utf-8') != signature:
                result = subprocess.run(
                    [imageio_ffmpeg.get_ffmpeg_exe(), '-y', '-i', str(video),
                     '-t', '8', '-vn', '-ac', '2', '-ar', '44100', str(target)],
                    capture_output=True, creationflags=subprocess.CREATE_NO_WINDOW,
                    timeout=45,
                )
                if result.returncode:
                    raise RuntimeError('视频无可用音轨或音频解码失败')
                stamp.write_text(signature, encoding='utf-8')
            with self.lock:
                if self.closed:
                    return
                pygame.mixer.init()
                self.sound = pygame.mixer.Sound(str(target))
            self.events.put(('audio', '视频原声已就绪'))
        except Exception as exc:
            self.events.put(('audio', f'原声不可用：{exc}'))

    def play(self, volume: float):
        if self.sound is not None:
            self.sound.stop()
            self.sound.set_volume(volume)
            self.sound.play()

    def stop(self):
        if self.sound is not None:
            self.sound.stop()

    def set_volume(self, volume):
        if self.sound is not None:
            self.sound.set_volume(volume)

    def close(self):
        with self.lock:
            self.closed = True
            self.stop()
            if self.sound is not None:
                import pygame
                pygame.mixer.quit()


def start_tray(image, events: queue.Queue):
    import pystray
    def send(action):
        return lambda _icon, _item: events.put((action, None))
    icon = pystray.Icon('nailong', image, '奶龙桌宠', pystray.Menu(
        pystray.MenuItem('显示桌宠', send('show'), default=True),
        pystray.MenuItem('隐藏桌宠', send('hide')),
        pystray.MenuItem('播放大笑', send('play')),
        pystray.MenuItem('声音开关', send('sound')),
        pystray.MenuItem('退出', send('quit')),
    ))
    def run():
        try:
            icon.run()
        except Exception as exc:
            events.put(('tray_error', str(exc)))
    threading.Thread(target=run, daemon=True).start()
    return icon
