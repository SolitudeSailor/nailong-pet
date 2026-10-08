from __future__ import annotations

import argparse
from collections.abc import Callable, Sequence
import queue
import random
import sys
import time
from pathlib import Path
import tkinter as tk
from tkinter import messagebox

import cv2
from PIL import Image, ImageTk
from desktop_services import (Audio, autostart_enabled, load_settings, monitors,
                              place_in_monitor, save_settings, set_autostart, start_tray)
from nailong_pet import (
    APP_NAME,
    DEFAULT_VIDEO,
    FULL_ANIMATION_SECONDS,
    SIDE_EYE_SECONDS,
    TRANSPARENT_COLOR,
)
from nailong_pet.imaging import (
    remove_connected_background,
    resize_transparent_image,
    to_colorkey_image,
)
from nailong_pet.settings import MAX_DISPLAY_WIDTH, MIN_DISPLAY_WIDTH, PetSettings


class DesktopPet:
    """由视频驱动的桌面宠物。"""

    def __init__(
        self,
        root: tk.Tk,
        video_path: Path,
        width: int,
        chroma_tolerance: int,
        display_width: int | None = None,
    ):
        self.root = root
        self.video_path = video_path
        self.target_width = width
        self.display_width = display_width or width
        self.chroma_tolerance = chroma_tolerance
        self.settings = PetSettings.from_mapping(
            load_settings(),
            default_width=self.display_width,
        )
        self.display_width = self.settings.width
        self.events = queue.Queue()
        self.closed = False
        self.hidden = False
        self.last_activity = time.monotonic()
        self.resize_mode = False
        self.save_job = None
        self.sound_enabled = tk.BooleanVar(root, self.settings.sound)
        self.idle_enabled = tk.BooleanVar(root, self.settings.idle)
        self.snap_enabled = tk.BooleanVar(root, self.settings.snap)
        self.autostart = tk.BooleanVar(root, autostart_enabled())
        self.volume = self.settings.volume

        self.capture: cv2.VideoCapture | None = None
        self.first_frame: ImageTk.PhotoImage | None = None
        self.current_frame: ImageTk.PhotoImage | None = None
        self.fps = 30.0
        self.total_frames = 0
        self.frame_index = 0
        self.play_until = 0
        self.play_job: str | None = None
        self.single_click_job: str | None = None
        self.last_click_at = 0.0
        self.double_click_seconds = 0.28

        self.press_x = 0
        self.press_y = 0
        self.window_x = 0
        self.window_y = 0
        self.dragged = False

        self._configure_window()
        self._load_video()
        self._build_ui()
        self._place_near_bottom_right()
        self._show_frame(0)
        self.audio = Audio(self.video_path, self.events)
        self.tray = start_tray(self.tray_image, self.events)
        self.event_job = self.root.after(100, self._poll_events)
        self.idle_job = self.root.after(1000, self._check_idle)
        self.root.protocol('WM_DELETE_WINDOW', self.close)

    def _configure_window(self) -> None:
        self.root.title(APP_NAME)
        self.root.overrideredirect(True)
        self.root.attributes("-topmost", True)
        self.root.configure(bg=TRANSPARENT_COLOR)
        if sys.platform == "win32":
            self.root.wm_attributes("-transparentcolor", TRANSPARENT_COLOR)

    def _load_video(self) -> None:
        self.capture = cv2.VideoCapture(str(self.video_path))
        if not self.capture.isOpened():
            raise RuntimeError(f"无法打开视频：{self.video_path}")

        fps = float(self.capture.get(cv2.CAP_PROP_FPS))
        self.fps = fps if fps > 0 else 30.0
        self.total_frames = int(self.capture.get(cv2.CAP_PROP_FRAME_COUNT))
        ok, bgr = self.capture.read()
        if not ok:
            raise RuntimeError("视频中没有可读取的画面。")
        self.first_bgr = bgr.copy()
        self.first_frame = self._frame_to_photo(bgr)
        self.capture.set(cv2.CAP_PROP_POS_FRAMES, 0)

    def _frame_to_photo(self, bgr) -> ImageTk.PhotoImage:
        height, width = bgr.shape[:2]
        if width != self.target_width:
            target_height = max(1, round(height * self.target_width / width))
            interpolation = cv2.INTER_AREA if self.target_width < width else cv2.INTER_CUBIC
            bgr = cv2.resize(bgr, (self.target_width, target_height), interpolation=interpolation)
        rgba = self._remove_corner_background(bgr)
        image = Image.fromarray(cv2.cvtColor(rgba, cv2.COLOR_BGRA2RGBA))
        if not hasattr(self, 'tray_image'):
            self.tray_image = image.copy()
            self.tray_image.thumbnail((128, 128))
        if self.display_width != self.target_width:
            display_height = max(1, round(image.height * self.display_width / image.width))
            image = self._resize_transparent_image(
                image, (self.display_width, display_height)
            )
        else:
            image = self._to_colorkey_image(image)
        return ImageTk.PhotoImage(image)

    @staticmethod
    def _resize_transparent_image(image: Image.Image, size: tuple[int, int]) -> Image.Image:
        return resize_transparent_image(image, size)

    @staticmethod
    def _to_colorkey_image(image: Image.Image) -> Image.Image:
        return to_colorkey_image(image)

    def _remove_corner_background(self, bgr):
        return remove_connected_background(bgr, self.chroma_tolerance)

    def _build_ui(self) -> None:
        assert self.first_frame is not None
        self.label = tk.Label(
            self.root,
            image=self.first_frame,
            bg=TRANSPARENT_COLOR,
            borderwidth=0,
            highlightthickness=0,
        )
        self.label.pack()
        self.label.bind("<ButtonPress-1>", self._on_press)
        self.label.bind("<B1-Motion>", self._on_drag)
        self.label.bind("<ButtonRelease-1>", self._on_release)
        self.label.bind("<Button-3>", self._show_menu)
        self.label.bind('<MouseWheel>', self._on_wheel)

        self.menu = tk.Menu(self.root, tearoff=False)
        self.menu.add_command(label="播放完整动画", command=self.play_full)
        sizes = tk.Menu(self.menu, tearoff=False)
        for name, width in [('小（90px）', 90), ('中（180px）', 180), ('大（360px）', 360)]:
            sizes.add_command(label=name, command=lambda w=width: self.resize(w))
        self.menu.add_cascade(label='改变大小', menu=sizes)
        self.menu.add_command(label='缩放：Ctrl + 左键拖动 / 滚轮', state='disabled')
        self.menu.add_checkbutton(label='播放视频原声', variable=self.sound_enabled,
                                  command=self._sound_changed)
        volume_menu = tk.Menu(self.menu, tearoff=False)
        for level in (0, 25, 50, 70, 100):
            volume_menu.add_command(label=f'{level}%', command=lambda v=level: self._set_volume(v))
        self.menu.add_cascade(label='音量', menu=volume_menu)
        self.menu.add_checkbutton(label='闲置时偶尔眨眼 / 侧看', variable=self.idle_enabled,
                                  command=self._option_changed)
        self.menu.add_checkbutton(label='吸附屏幕边缘', variable=self.snap_enabled,
                                  command=self._option_changed)
        screens = tk.Menu(self.menu, tearoff=False)
        self.screen_menu = screens
        self.menu.add_cascade(label='移动到显示器', menu=screens)
        self.menu.add_checkbutton(label='开机自启动', variable=self.autostart,
                                  command=self._toggle_autostart)
        self.menu.add_command(label='隐藏到托盘', command=self.hide)
        self.menu.add_command(label='声音状态', command=lambda: messagebox.showinfo('视频原声', self.audio.status))
        self.menu.add_separator()
        self.menu.add_command(label="退出", command=self.close)

    def _place_near_bottom_right(self) -> None:
        self.root.update_idletasks()
        width = self.root.winfo_reqwidth()
        height = self.root.winfo_reqheight()
        x = max(0, self.root.winfo_screenwidth() - width - 40)
        y = max(0, self.root.winfo_screenheight() - height - 80)
        if self.settings.position is not None:
            x, y = self.settings.position
        self._set_position(*place_in_monitor(x, y, width, height))

    def _set_position(self, x, y):
        # Tk 的负号几何偏移代表相对右/下边缘；用 Win32 才能传入真实负屏幕坐标。
        import ctypes
        from ctypes import wintypes
        self.root.update_idletasks()
        user32 = ctypes.windll.user32
        user32.GetParent.argtypes = [wintypes.HWND]
        user32.GetParent.restype = wintypes.HWND
        hwnd = user32.GetParent(self.root.winfo_id()) or self.root.winfo_id()
        user32.SetWindowPos.argtypes = [wintypes.HWND, wintypes.HWND, ctypes.c_int,
                                       ctypes.c_int, ctypes.c_int, ctypes.c_int, wintypes.UINT]
        user32.SetWindowPos(hwnd, None, int(x), int(y), 0, 0, 0x15)

    def _on_press(self, event: tk.Event) -> None:
        self.press_x = event.x_root
        self.press_y = event.y_root
        self.window_x = self.root.winfo_x()
        self.window_y = self.root.winfo_y()
        self.dragged = False
        self.resize_mode = bool(event.state & 0x0004)
        self.press_width = self.display_width
        self.last_activity = time.monotonic()
        if self.single_click_job is not None:
            self.root.after_cancel(self.single_click_job)
            self.single_click_job = None

    def _on_drag(self, event: tk.Event) -> None:
        dx = event.x_root - self.press_x
        dy = event.y_root - self.press_y
        if abs(dx) > 4 or abs(dy) > 4:
            self.dragged = True
        if self.resize_mode:
            self.resize(self.press_width + dx)
        else:
            self._set_position(self.window_x + dx, self.window_y + dy)

    def _on_release(self, _event: tk.Event) -> None:
        self.last_activity = time.monotonic()
        if self.dragged or self.resize_mode:
            self.dragged = False
            self.last_click_at = 0.0
            self._keep_visible(self.snap_enabled.get())
            self._schedule_save()
            return

        now = time.monotonic()
        if now - self.last_click_at <= self.double_click_seconds:
            if self.single_click_job is not None:
                self.root.after_cancel(self.single_click_job)
                self.single_click_job = None
            self.last_click_at = 0.0
            self.play_full()
            return

        self.last_click_at = now
        self.single_click_job = self.root.after(
            round(self.double_click_seconds * 1000), self._confirm_single_click
        )

    def _confirm_single_click(self) -> None:
        self.single_click_job = None
        self.last_click_at = 0.0
        self.play_side_eye()

    def _show_menu(self, event: tk.Event) -> None:
        self.last_activity = time.monotonic()
        self.screen_menu.delete(0, 'end')
        for index, area in enumerate(monitors()):
            self.screen_menu.add_command(label=f'显示器 {index + 1}',
                                          command=lambda a=area: self._move_to_screen(a))
        try:
            self.menu.tk_popup(event.x_root, event.y_root)
        finally:
            self.menu.grab_release()

    def resize(self, width):
        new_width = max(60, min(720, int(width)))
        if new_width == self.display_width:
            return
        self.display_width = new_width
        self.first_frame = self._frame_to_photo(self.first_bgr)
        if self.play_job is None:
            self._show_first_frame()
        self._keep_visible(False)
        self.last_activity = time.monotonic()
        self._schedule_save()

    def _on_wheel(self, event):
        if self.single_click_job is not None:
            self.root.after_cancel(self.single_click_job)
            self.single_click_job = None
        self.last_click_at = 0.0
        if event.delta:
            self.resize(self.display_width + (12 if event.delta > 0 else -12))
        return 'break'

    def _keep_visible(self, snap=False):
        self.root.update_idletasks()
        self._set_position(*place_in_monitor(self.root.winfo_x(), self.root.winfo_y(),
                            self.display_width, self.first_frame.height(), snap))

    def _move_to_screen(self, area):
        left, top, right, bottom = area
        self._set_position(right - self.display_width - 30,
                           bottom - self.first_frame.height() - 30)
        self._keep_visible()
        self._schedule_save()

    def _schedule_save(self):
        if self.save_job is not None:
            self.root.after_cancel(self.save_job)
        self.save_job = self.root.after(300, self._save)

    def _save(self):
        self.save_job = None
        settings = PetSettings(
            width=self.display_width,
            position=(self.root.winfo_x(), self.root.winfo_y()),
            sound=self.sound_enabled.get(),
            volume=self.volume,
            idle=self.idle_enabled.get(),
            snap=self.snap_enabled.get(),
        )
        save_settings(settings.to_mapping())

    def _option_changed(self):
        self.last_activity = time.monotonic()
        self._schedule_save()

    def _sound_changed(self):
        if not self.sound_enabled.get():
            self.audio.stop()
        self._option_changed()

    def _set_volume(self, volume):
        self.volume = volume
        self.audio.set_volume(volume / 100)
        self._schedule_save()

    def _toggle_autostart(self):
        try:
            set_autostart(self.autostart.get())
        except OSError as exc:
            self.autostart.set(autostart_enabled())
            messagebox.showerror('开机自启动', str(exc))

    def hide(self):
        self.hidden = True
        self.audio.stop()
        self.root.withdraw()

    def show(self):
        self.hidden = False
        self.root.deiconify()
        self._keep_visible()
        self.last_activity = time.monotonic()

    def _poll_events(self):
        try:
            while True:
                action, value = self.events.get_nowait()
                if action == 'quit':
                    self.close()
                    return
                if action == 'show':
                    self.show()
                elif action == 'hide':
                    self.hide()
                elif action == 'play':
                    self.show()
                    self.play_full()
                elif action == 'sound':
                    self.sound_enabled.set(not self.sound_enabled.get())
                    self._sound_changed()
                elif action == 'audio':
                    self.audio.status = value
                elif action == 'tray_error':
                    self.show()
                    messagebox.showerror('托盘不可用', value)
        except queue.Empty:
            pass
        self.event_job = self.root.after(100, self._poll_events)

    def _check_idle(self):
        if (self.idle_enabled.get() and not self.hidden and not self.dragged
                and self.play_job is None and self.single_click_job is None
                and time.monotonic() - self.last_activity > 30):
            self._start_playback(round(self.fps * random.choice((0.8, 1.7))))
        self.idle_job = self.root.after(1000, self._check_idle)

    def play_side_eye(self) -> None:
        side_eye_frames = max(
            1, min(self.total_frames, round(self.fps * SIDE_EYE_SECONDS))
        )
        self._start_playback(side_eye_frames)

    def play_full(self) -> None:
        eight_seconds = max(
            1, min(self.total_frames, round(self.fps * FULL_ANIMATION_SECONDS))
        )
        self._start_playback(eight_seconds, sound=True)

    def _start_playback(self, frame_count: int, sound=False) -> None:
        self.last_activity = time.monotonic()
        self.audio.stop()
        if sound and self.sound_enabled.get():
            self.audio.play(self.volume / 100)
        if self.play_job is not None:
            self.root.after_cancel(self.play_job)
            self.play_job = None
        self.frame_index = 0
        self.play_until = frame_count
        assert self.capture is not None
        self.capture.set(cv2.CAP_PROP_POS_FRAMES, 0)
        self.play_started = time.monotonic()
        self._play_next_frame()

    def _play_next_frame(self) -> None:
        # 按真实播放时间追帧，避免慢机器上每帧处理延迟累计，导致音画不同步。
        expected = int((time.monotonic() - self.play_started) * self.fps)
        assert self.capture is not None
        while self.frame_index < min(expected, self.play_until):
            if not self.capture.grab():
                self.frame_index = self.play_until
                break
            self.frame_index += 1
        if self.frame_index >= self.play_until:
            self.play_job = None
            self.audio.stop()
            self._show_frame(0)
            return

        assert self.capture is not None
        ok, bgr = self.capture.read()
        if not ok:
            self.play_job = None
            self.audio.stop()
            self._show_first_frame()
            return
        self.current_frame = self._frame_to_photo(bgr)
        self.label.configure(image=self.current_frame)
        self.frame_index += 1
        due = self.play_started + self.frame_index / self.fps
        self.play_job = self.root.after(max(1, round((due - time.monotonic()) * 1000)),
                                        self._play_next_frame)

    def _show_frame(self, index: int) -> None:
        if index != 0:
            raise ValueError("静止状态仅支持显示第一帧")
        self._show_first_frame()

    def _show_first_frame(self) -> None:
        self.current_frame = self.first_frame
        self.label.configure(image=self.first_frame)

    def close(self) -> None:
        if self.closed:
            return
        self.closed = True
        pending_save = self.save_job
        self._save()
        for job in (self.event_job, self.idle_job, pending_save):
            if job is not None:
                self.root.after_cancel(job)
        self.audio.close()
        self.tray.stop()
        if self.play_job is not None:
            self.root.after_cancel(self.play_job)
        if self.single_click_job is not None:
            self.root.after_cancel(self.single_click_job)
        if self.capture is not None:
            self.capture.release()
        self.root.destroy()


def integer_in_range(
    name: str,
    minimum: int,
    maximum: int,
) -> Callable[[str], int]:
    """创建带明确错误信息的 argparse 整数校验器。"""
    def parse(value: str) -> int:
        try:
            number = int(value)
        except ValueError as exc:
            raise argparse.ArgumentTypeError(f"{name} 必须是整数") from exc
        if not minimum <= number <= maximum:
            raise argparse.ArgumentTypeError(
                f"{name} 必须在 {minimum}–{maximum} 之间"
            )
        return number

    return parse


def parse_args(argv: Sequence[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=APP_NAME)
    parser.add_argument("--video", type=Path, default=Path(__file__).with_name(DEFAULT_VIDEO))
    parser.add_argument(
        "--width",
        type=integer_in_range("内部渲染宽度", MIN_DISPLAY_WIDTH, 4096),
        default=720,
        help="内部渲染宽度（像素，60–4096）",
    )
    parser.add_argument(
        "--display-width",
        type=integer_in_range("桌面显示宽度", MIN_DISPLAY_WIDTH, MAX_DISPLAY_WIDTH),
        default=180,
        help="桌面实际显示宽度（像素，60–720）",
    )
    parser.add_argument(
        "--chroma-tolerance",
        type=integer_in_range("背景饱和度阈值", 0, 255),
        default=55,
        help="背景最大饱和度（0–255），越大去除的灰白背景越多",
    )
    return parser.parse_args(argv)


def main() -> None:
    args = parse_args()
    root = tk.Tk()
    try:
        DesktopPet(
            root,
            args.video.resolve(),
            args.width,
            args.chroma_tolerance,
            args.display_width,
        )
    except Exception as exc:
        root.withdraw()
        messagebox.showerror(f"{APP_NAME}启动失败", str(exc))
        root.destroy()
        raise SystemExit(1) from exc
    root.mainloop()


if __name__ == "__main__":
    main()
