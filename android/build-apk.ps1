param(
    [string]$JavaHome = $env:JAVA_HOME,
    [string]$AndroidSdk = $env:ANDROID_HOME
)
$ErrorActionPreference = 'Stop'
$taskRoot = Split-Path -Parent $PSScriptRoot
$toolsRoot = Join-Path $taskRoot '.tools'
if (-not $JavaHome) {
    $jdkFolder = Get-ChildItem -LiteralPath $toolsRoot -Directory -Filter 'jdk-*' | Where-Object { Test-Path (Join-Path $_.FullName 'bin\javac.exe') } | Select-Object -First 1
    if ($jdkFolder) { $JavaHome = $jdkFolder.FullName }
}
if (-not $AndroidSdk) { $AndroidSdk = Join-Path $toolsRoot 'sdk' }
$java = Join-Path $JavaHome 'bin\java.exe'
$javac = Join-Path $JavaHome 'bin\javac.exe'
$keytool = Join-Path $JavaHome 'bin\keytool.exe'
$buildTools = Join-Path $AndroidSdk 'build-tools\35.0.0'
$platform = Join-Path $AndroidSdk 'platforms\android-35\android.jar'
foreach ($toolPath in @($java, $javac, $platform, (Join-Path $buildTools 'aapt2.exe'))) {
    if (-not (Test-Path -LiteralPath $toolPath)) { throw "Missing Android build dependency: $toolPath" }
}
function Invoke-Checked([string]$Exe, [string[]]$Arguments) {
    & $Exe @Arguments
    if ($LASTEXITCODE -ne 0) { throw "Build command failed: $Exe" }
}
$build = Join-Path ([System.IO.Path]::GetTempPath()) ('StudySchedule-android-build-' + [guid]::NewGuid().ToString('N'))
# aapt2 on Windows cannot reliably read resource paths containing Chinese characters.
# Keep the transient resource inputs and outputs in an ASCII-only staging directory.
if ($build -match '[^\x00-\x7F]') { throw 'Please set TEMP to an ASCII-only directory before building.' }
$classes = Join-Path $build 'classes'
$generated = Join-Path $build 'generated'
$dex = Join-Path $build 'dex'
New-Item -ItemType Directory -Force $build, $classes, $generated, $dex | Out-Null
$stagedSource = Join-Path $build 'source'
New-Item -ItemType Directory -Force $stagedSource | Out-Null
Copy-Item -Path (Join-Path $PSScriptRoot 'app\src\main\*') -Destination $stagedSource -Recurse -Force
$stagedPlatform = Join-Path $build 'android.jar'
Copy-Item -LiteralPath $platform -Destination $stagedPlatform -Force
$resources = Join-Path $build 'resources.zip'
Invoke-Checked (Join-Path $buildTools 'aapt2.exe') @('compile', '--dir', (Join-Path $stagedSource 'res'), '-o', $resources)
$unsigned = Join-Path $build 'unsigned.apk'
$manifest = [xml](Get-Content -LiteralPath (Join-Path $PSScriptRoot 'app\src\main\AndroidManifest.xml') -Raw -Encoding UTF8)
$manifest.DocumentElement.SetAttribute('package', 'cn.local.studyschedule')
$manifestPath = Join-Path $build 'AndroidManifest.xml'
$manifest.Save($manifestPath)
Invoke-Checked (Join-Path $buildTools 'aapt2.exe') @('link', '-o', $unsigned, '-I', $stagedPlatform, '--manifest', $manifestPath, '--java', $generated, '--min-sdk-version', '26', '--target-sdk-version', '35', '--version-code', '3', '--version-name', '1.2', $resources)
$sourceFiles = @(Get-ChildItem (Join-Path $stagedSource 'java'), $generated -Recurse -Filter '*.java' | Select-Object -ExpandProperty FullName)
Invoke-Checked $javac (@('-encoding', 'UTF-8', '--release', '17', '-classpath', $platform, '-d', $classes) + $sourceFiles)
$classFiles = @(Get-ChildItem -LiteralPath $classes -Recurse -Filter '*.class' | Select-Object -ExpandProperty FullName)
Invoke-Checked $java (@('-cp', (Join-Path $buildTools 'lib\d8.jar'), 'com.android.tools.r8.D8', '--lib', $platform, '--min-api', '26', '--output', $dex) + $classFiles)
Add-Type -AssemblyName System.IO.Compression
Add-Type -AssemblyName System.IO.Compression.FileSystem
$zip = [System.IO.Compression.ZipFile]::Open($unsigned, [System.IO.Compression.ZipArchiveMode]::Update)
try {
    Get-ChildItem -LiteralPath $dex -Filter '*.dex' | ForEach-Object {
        [System.IO.Compression.ZipFileExtensions]::CreateEntryFromFile($zip, $_.FullName, $_.Name) | Out-Null
    }
} finally { $zip.Dispose() }
$aligned = Join-Path $build 'aligned.apk'
Invoke-Checked (Join-Path $buildTools 'zipalign.exe') @('-f', '-p', '4', $unsigned, $aligned)
$keystore = Join-Path $PSScriptRoot 'local-debug.keystore'
if (-not (Test-Path -LiteralPath $keystore)) {
    Invoke-Checked $keytool @('-genkeypair', '-keystore', $keystore, '-storepass', 'android', '-keypass', 'android', '-alias', 'androiddebugkey', '-keyalg', 'RSA', '-keysize', '2048', '-validity', '10000', '-dname', 'CN=Study Schedule Local Debug')
}
$outputFolder = Join-Path $taskRoot 'dist'
New-Item -ItemType Directory -Force $outputFolder | Out-Null
$apk = Join-Path $outputFolder 'StudySchedule-android.apk'
Invoke-Checked $java @('-jar', (Join-Path $buildTools 'lib\apksigner.jar'), 'sign', '--ks', $keystore, '--ks-pass', 'pass:android', '--ks-key-alias', 'androiddebugkey', '--key-pass', 'pass:android', '--out', $apk, $aligned)
Invoke-Checked $java @('-jar', (Join-Path $buildTools 'lib\apksigner.jar'), 'verify', '--verbose', $apk)
$hash = (Get-FileHash -LiteralPath $apk -Algorithm SHA256).Hash.ToLowerInvariant()
[System.IO.File]::WriteAllText((Join-Path $outputFolder 'SHA256.txt'), "$hash  StudySchedule-android.apk`r`n", [System.Text.Encoding]::ASCII)
Write-Host "APK ready: $apk"
