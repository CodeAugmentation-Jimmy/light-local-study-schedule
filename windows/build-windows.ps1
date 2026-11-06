param(
    [string]$Python = '',
    [string]$ISCC = ''
)
$ErrorActionPreference = 'Stop'
$projectRoot = Split-Path -Parent $PSScriptRoot
if (-not $Python) { $Python = Join-Path $projectRoot '.tools\windows-venv\Scripts\python.exe' }
if (-not $ISCC) { $ISCC = Join-Path $projectRoot '.tools\windows\inno\ISCC.exe' }
if (-not (Test-Path -LiteralPath $Python)) { throw 'Please create a Python venv and install PyInstaller, then pass -Python.' }
if (-not (Test-Path -LiteralPath $ISCC)) { throw 'Please install Inno Setup 6, then pass -ISCC.' }
$env:PYINSTALLER_CONFIG_DIR = Join-Path $projectRoot '.tools\windows\pyinstaller-cache'
Push-Location $projectRoot
try {
    & $Python (Join-Path $PSScriptRoot 'build_assets.py')
    if ($LASTEXITCODE -ne 0) { throw 'Could not create the application icon.' }
    & $Python -m PyInstaller --noconfirm --onedir --windowed --noupx --name StudySchedule `
        --icon (Join-Path $PSScriptRoot 'assets\app.ico') `
        --version-file (Join-Path $PSScriptRoot 'version_info.txt') `
        --add-data ((Join-Path $PSScriptRoot 'assets\app.ico') + ';.') `
        --distpath (Join-Path $projectRoot 'build\windows\app') `
        --workpath (Join-Path $projectRoot 'build\windows\pyinstaller') `
        --specpath $PSScriptRoot (Join-Path $projectRoot '日程程序.py')
    if ($LASTEXITCODE -ne 0) { throw 'PyInstaller failed.' }
    & $ISCC /Q (Join-Path $PSScriptRoot 'installer.iss')
    if ($LASTEXITCODE -ne 0) { throw 'Inno Setup failed.' }
    $installer = Join-Path $projectRoot 'dist\StudySchedule-Setup-1.2.3.exe'
    $hash = (Get-FileHash -LiteralPath $installer -Algorithm SHA256).Hash.ToLowerInvariant()
    Set-Content -LiteralPath ($installer + '.sha256') -Value ($hash + '  StudySchedule-Setup-1.2.3.exe') -Encoding ASCII
    Write-Host "Installer ready: $installer"
} finally { Pop-Location }
