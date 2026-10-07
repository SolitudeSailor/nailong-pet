@echo off
setlocal
cd /d "%~dp0"

if not exist ".venv\Scripts\pythonw.exe" (
    echo Creating the local Python environment...
    python -m venv .venv || goto :error
)

".venv\Scripts\python.exe" -c "import cv2, PIL, pystray, pygame, imageio_ffmpeg" >nul 2>&1
if errorlevel 1 (
    echo Installing desktop pet dependencies...
    ".venv\Scripts\python.exe" -m pip install -r requirements.txt || goto :error
)

start "" "%~dp0.venv\Scripts\pythonw.exe" "%~dp0launcher.pyw"
exit /b 0

:error
echo.
echo Startup failed. Please install Python 3.11 or newer.
pause
exit /b 1
