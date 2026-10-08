r"""运行：.venv\Scripts\python.exe -m unittest discover -s tests -v"""
import tempfile
import time
import tkinter as tk
import unittest
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import Mock, patch

from PIL import Image

import app
import desktop_services as services


class PetInteractions(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.patches = [
            patch.object(services, 'SETTINGS_PATH', Path(self.temp.name) / 'settings.json'),
            patch.object(app, 'Audio', return_value=Mock(status='测试原声')),
            patch.object(app, 'start_tray', return_value=Mock()),
        ]
        for item in self.patches:
            item.start()
        self.root = tk.Tk()
        self.pet = app.DesktopPet(self.root, Path(app.DEFAULT_VIDEO).resolve(), 720, 55, 180)

    def tearDown(self):
        self.pet.close()
        for item in reversed(self.patches):
            item.stop()
        self.temp.cleanup()

    def event(self, x=100, y=100, state=0, delta=0):
        return SimpleNamespace(x_root=x, y_root=y, state=state, delta=delta)

    def test_ctrl_drag_and_wheel_do_not_trigger_animation(self):
        self.pet._on_press(self.event(state=4))
        self.pet._on_drag(self.event(x=150, state=4))
        self.pet._on_release(self.event(x=150, state=4))
        self.assertEqual(self.pet.display_width, 230)
        self.assertIsNone(self.pet.single_click_job)
        self.assertIsNone(self.pet.play_job)
        self.pet._on_wheel(self.event(delta=-120))
        self.assertEqual(self.pet.display_width, 218)
        self.pet.resize(10)
        self.assertEqual(self.pet.display_width, 60)
        self.pet.resize(1000)
        self.assertEqual(self.pet.display_width, 720)

    def test_double_click_cancels_single_and_uses_full_clip(self):
        with patch.object(self.pet, 'play_full') as full, patch.object(self.pet, 'play_side_eye') as single:
            for _ in range(2):
                self.pet._on_press(self.event())
                self.pet._on_release(self.event())
            self.assertIsNone(self.pet.single_click_job)
            full.assert_called_once()
            single.assert_not_called()
        self.pet.play_full()
        self.assertEqual(self.pet.play_until, 240)
        self.pet.audio.play.assert_called_once_with(0.7)

    def test_save_restore_and_tray_events(self):
        self.pet.resize(240)
        self.pet.idle_enabled.set(True)
        self.pet._save()
        saved = services.load_settings()
        self.assertEqual(saved['width'], 240)
        self.assertTrue(saved['idle'])
        self.pet.events.put(('hide', None))
        self.pet.events.put(('sound', None))
        self.root.after_cancel(self.pet.event_job)
        self.pet._poll_events()
        self.assertTrue(self.pet.hidden)
        self.assertFalse(self.pet.sound_enabled.get())
        self.pet.show()
        self.assertFalse(self.pet.hidden)
        self.pet.close()
        self.root = tk.Tk()
        self.pet = app.DesktopPet(self.root, Path(app.DEFAULT_VIDEO).resolve(), 720, 55, 180)
        self.assertEqual(self.pet.display_width, 240)
        self.assertTrue(self.pet.idle_enabled.get())

    def test_idle_respects_hidden_and_disabled(self):
        self.pet.last_activity = time.monotonic() - 40
        with patch.object(self.pet, '_start_playback') as play:
            self.root.after_cancel(self.pet.idle_job)
            self.pet._check_idle()
            play.assert_not_called()
            self.pet.idle_enabled.set(True)
            self.root.after_cancel(self.pet.idle_job)
            self.pet._check_idle()
            self.assertIn(play.call_args.args[0], (24, 51))
            play.reset_mock()
            self.pet.hidden = True
            self.root.after_cancel(self.pet.idle_job)
            self.pet._check_idle()
            play.assert_not_called()

    def test_animation_returns_to_first_frame(self):
        self.pet.play_side_eye()
        self.assertEqual(self.pet.play_until, 51)
        deadline = time.monotonic() + 2.5
        while self.pet.play_job is not None and time.monotonic() < deadline:
            self.root.update()
            time.sleep(0.005)
        self.assertIsNone(self.pet.play_job)
        self.assertIs(self.pet.current_frame, self.pet.first_frame)


class MonitorTests(unittest.TestCase):
    def test_compiled_autostart_points_to_installed_executable(self):
        installed = r'C:\Users\Tester\AppData\Local\Programs\nailong\nailong.exe'
        with patch.object(services, 'IS_COMPILED', True), \
                patch.object(services.sys, 'executable', installed):
            self.assertEqual(services.autostart_command(), f'"{installed}"')

    def test_opaque_magenta_is_not_confused_with_transparent_colorkey(self):
        image = Image.new('RGBA', (2, 1))
        image.putdata(((255, 0, 255, 255), (0, 0, 0, 0)))

        keyed = app.DesktopPet._to_colorkey_image(image)

        self.assertEqual(keyed.getpixel((0, 0)), (254, 0, 255))
        self.assertEqual(keyed.getpixel((1, 0)), (255, 0, 255))

    def test_transparent_resize_outputs_rgb_colorkey_pixels(self):
        image = Image.new('RGBA', (4, 1))
        image.putdata((
            (255, 255, 255, 255),
            (0, 0, 0, 0),
            (0, 0, 0, 0),
            (0, 0, 0, 0),
        ))

        resized = app.DesktopPet._resize_transparent_image(image, (2, 1))

        self.assertEqual(resized.mode, 'RGB')
        self.assertEqual(resized.getpixel((1, 0)), (255, 0, 255))
        # 50% Alpha 边界在二值化后保留，预乘缩放不应混入黑色或色键紫。
        self.assertEqual(resized.getpixel((0, 0)), (255, 255, 255))

    def test_autostart_only_changes_own_named_value(self):
        import winreg
        from unittest.mock import MagicMock
        context = MagicMock()
        key = context.__enter__.return_value
        with patch.object(winreg, 'CreateKey', return_value=context), \
                patch.object(winreg, 'SetValueEx') as write, \
                patch.object(winreg, 'DeleteValue') as delete:
            services.set_autostart(True)
            write.assert_called_once_with(key, services.RUN_NAME, 0, winreg.REG_SZ,
                                          services.autostart_command())
            services.set_autostart(False)
            delete.assert_called_once_with(key, services.RUN_NAME)

    def test_negative_monitor_coordinates_and_snap(self):
        with patch.object(services, 'monitors', return_value=[(-1920, 0, 0, 1040), (0, 0, 1920, 1040)]):
            self.assertEqual(services.place_in_monitor(-1910, 10, 180, 176, True), (-1920, 0))
            self.assertEqual(services.place_in_monitor(4000, 2000, 180, 176), (1740, 864))


if __name__ == '__main__':
    unittest.main()
