[CmdletBinding()]
param(
    [string]$InnoCompiler = ''
)

$ErrorActionPreference = 'Stop'
$ProjectDir = $PSScriptRoot
$Python = Join-Path $ProjectDir '.venv\Scripts\python.exe'
$AppName = -join ([char[]](0x5976, 0x9F99, 0x684C, 0x5BA0))
$VideoName = (-join ([char[]](0x5976, 0x9F99, 0x5927, 0x7B11))) + '_video.mp4'
$Video = Join-Path $ProjectDir $VideoName
$Icon = Join-Path $ProjectDir 'assets\nailong.ico'
$InstallerScript = Join-Path $ProjectDir 'packaging\nailong.iss'

if (-not $InnoCompiler) {
    $InnoCandidates = @(
        (Join-Path $env:LOCALAPPDATA 'Programs\Inno Setup 6\ISCC.exe')
        (Join-Path ${env:ProgramFiles(x86)} 'Inno Setup 6\ISCC.exe')
        (Join-Path $env:ProgramFiles 'Inno Setup 6\ISCC.exe')
    )
    $InnoCompiler = $InnoCandidates |
        Where-Object { Test-Path -LiteralPath $_ } |
        Select-Object -First 1
}

if (-not (Test-Path -LiteralPath $Python)) {
    throw "Project Python was not found: $Python"
}
if (-not (Test-Path -LiteralPath $Video)) {
    throw "Bundled video was not found: $Video"
}
if (-not (Test-Path -LiteralPath $Icon)) {
    throw "Application icon was not found: $Icon"
}
if (-not (Test-Path -LiteralPath $InstallerScript)) {
    throw "Inno Setup script was not found: $InstallerScript"
}
if (-not (Test-Path -LiteralPath $InnoCompiler)) {
    throw 'Inno Setup 6 was not found. Install it or pass -InnoCompiler <path>.'
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
        --hidden-import pystray._win32 `
        app.py
    if ($LASTEXITCODE -ne 0) { throw 'PyInstaller build failed.' }

    & $InnoCompiler $InstallerScript
    if ($LASTEXITCODE -ne 0) { throw 'Inno Setup packaging failed.' }
}
finally {
    Pop-Location
}
