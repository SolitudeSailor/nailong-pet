[CmdletBinding()]
param()

$ErrorActionPreference = 'Stop'
$ProjectDir = $PSScriptRoot
$Python = Join-Path $ProjectDir '.venv\Scripts\python.exe'
$BuildDir = Join-Path $ProjectDir 'build'
$Video = Join-Path $ProjectDir '奶龙大笑_video.mp4'
$Icon = Join-Path $ProjectDir 'assets\nailong.ico'
$InnoCompiler = Join-Path $env:LOCALAPPDATA 'Programs\Inno Setup 6\ISCC.exe'

if (-not (Test-Path -LiteralPath $Python)) {
    throw "找不到项目 Python：$Python"
}
if (-not (Test-Path -LiteralPath $InnoCompiler)) {
    throw '找不到 Inno Setup 6，请先安装 JRSoftware.InnoSetup。'
}

Push-Location $ProjectDir
try {
    & $Python -m unittest discover -s tests -v
    if ($LASTEXITCODE -ne 0) { throw '测试失败，已停止构建。' }

    & $Python -m PyInstaller `
        --noconfirm `
        --clean `
        --onedir `
        --windowed `
        --name nailong `
        --icon $Icon `
        --distpath build `
        --workpath build\pyinstaller-work `
        --specpath build `
        --add-data "$Video;." `
        --collect-all imageio_ffmpeg `
        --collect-all pygame `
        --hidden-import pystray._win32 `
        app.py
    if ($LASTEXITCODE -ne 0) { throw 'PyInstaller 构建失败。' }

    & $InnoCompiler (Join-Path $ProjectDir 'packaging\nailong.iss')
    if ($LASTEXITCODE -ne 0) { throw 'Inno Setup 封装失败。' }
}
finally {
    Pop-Location
}
