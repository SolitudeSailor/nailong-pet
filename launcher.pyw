from __future__ import annotations

import ctypes
import os
import traceback
from pathlib import Path

from nailong_pet import APP_NAME


PROJECT_DIR = Path(__file__).resolve().parent
ERROR_LOG = PROJECT_DIR / "desktop_pet_error.log"


def show_error(message: str) -> None:
    ctypes.windll.user32.MessageBoxW(0, message, f"{APP_NAME}启动失败", 0x10)


try:
    os.chdir(PROJECT_DIR)
    from app import main

    main()
except SystemExit as exc:
    if exc.code not in (None, 0):
        ERROR_LOG.write_text(traceback.format_exc(), encoding="utf-8")
except BaseException:
    details = traceback.format_exc()
    ERROR_LOG.write_text(details, encoding="utf-8")
    show_error(f"无法启动桌宠。\n\n详细信息已保存到：\n{ERROR_LOG}")
