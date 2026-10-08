[CmdletBinding()]
param()

$ErrorActionPreference = 'Stop'
$ProjectDir = $PSScriptRoot
$Python = Join-Path $ProjectDir '.venv\Scripts\python.exe'
$BuildDir = Join-Path $ProjectDir 'build'
$AppName = -join ([char[]](0x5976, 0x9F99, 0x684C, 0x5BA0))
$VideoName = (-join ([char[]](0x5976, 0x9F99, 0x5927, 0x7B11))) + '_video.mp4'
$Video = Join-Path $ProjectDir $VideoName
$Icon = Join-Path $ProjectDir 'assets\nailong.ico'
$InnoCompiler = Join-Path $env:LOCALAPPDATA 'Programs\Inno Setup 6\ISCC.exe'

if (-not (Test-Path -LiteralPath $Python)) {
    throw "Project Python was not found: $Python"
}
if (-not (Test-Path -LiteralPath $InnoCompiler)) {
    throw 'Inno Setup 6 was not found.'
}

Push-Location $ProjectDir
try {
    & $Python -m unittest discover -s tests -v
    if ($LASTEXITCODE -ne 0) { throw 'Tests failed; build stopped.' }

    & $Python -m PyInstaller `
        --noconfirm `
        --clean `
        --onedir `
        --windowed `
        --name $AppName `
        --icon $Icon `
        --distpath build `
        --workpath build\pyinstaller-work `
        --specpath build `
        --add-data "$Video;." `
        --collect-all imageio_ffmpeg `
        --collect-all pygame `
        --hidden-import pystray._win32 `
        app.py
    if ($LASTEXITCODE -ne 0) { throw 'PyInstaller build failed.' }

    & $InnoCompiler (Join-Path $ProjectDir 'packaging\nailong.iss')
    if ($LASTEXITCODE -ne 0) { throw 'Inno Setup packaging failed.' }
}
finally {
    Pop-Location
}
