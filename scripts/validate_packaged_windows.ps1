[CmdletBinding()]
param(
    [Parameter(Mandatory = $true)][string]$BundlePath,
    [string]$PythonPath = "",
    [switch]$RequirePathWithSpaces
)

$ErrorActionPreference = "Stop"
$repoRoot = [IO.Path]::GetFullPath((Join-Path $PSScriptRoot ".."))
$BundlePath = [IO.Path]::GetFullPath($BundlePath)
$executablePath = Join-Path $BundlePath "SandyWallpaperStudio.exe"
if (-not (Test-Path -LiteralPath $executablePath -PathType Leaf)) {
    throw "Packaged executable not found: $executablePath"
}
if ($RequirePathWithSpaces -and $BundlePath -notmatch "\s") {
    throw "Path-with-spaces validation requires the bundle to be in a directory containing spaces."
}
if ([string]::IsNullOrWhiteSpace($PythonPath)) {
    $PythonPath = Join-Path $repoRoot ".venv\Scripts\python.exe"
}
if (-not (Test-Path -LiteralPath $PythonPath -PathType Leaf)) {
    throw "The project Python interpreter is required after the isolated executable smoke test to inspect its temporary SQLite database."
}

$appVersion = (& $PythonPath -c "from app.constants import APP_VERSION; print(APP_VERSION)").Trim()
if ($LASTEXITCODE -ne 0) {
    throw "Could not read APP_VERSION from the project interpreter."
}
$versionInfo = (Get-Item -LiteralPath $executablePath).VersionInfo
if ($versionInfo.ProductVersion -ne $appVersion) {
    throw "Executable ProductVersion '$($versionInfo.ProductVersion)' does not match APP_VERSION '$appVersion'."
}

$tempRoot = [IO.Path]::GetFullPath([IO.Path]::GetTempPath())
$separator = [IO.Path]::DirectorySeparatorChar
$tempPrefix = $tempRoot.TrimEnd($separator) + $separator
$profileName = "Sandy Wallpaper Studio QA " + [Guid]::NewGuid().ToString("N")
$profilePath = [IO.Path]::GetFullPath((Join-Path $tempRoot $profileName))
if (-not $profilePath.StartsWith($tempPrefix, [StringComparison]::OrdinalIgnoreCase) -or
    (Test-Path -LiteralPath $profilePath)) {
    throw "Could not allocate a new isolated temporary profile directory."
}
$profileMarker = ".sws-packaged-smoke-profile"
$profileToken = "SandyWallpaperStudio isolated packaging smoke test v1"
$profileTemp = Join-Path $profilePath "Temp"
$profileAppData = Join-Path $profilePath "AppData\Roaming"
$profileLocalAppData = Join-Path $profilePath "AppData\Local"
$nativeTypeName = "SwsPackageSmokeNativeMethods"
if (-not ($nativeTypeName -as [type])) {
    $nativeInteropSource = @"
using System;
using System.Runtime.InteropServices;
using System.Text;
public static class SwsPackageSmokeNativeMethods {
    [DllImport("user32.dll", SetLastError = true)]
    public static extern bool PostMessage(IntPtr hWnd, UInt32 message, IntPtr wParam, IntPtr lParam);
    [DllImport("user32.dll", SetLastError = true)]
    public static extern IntPtr GetDlgItem(IntPtr hDlg, int nIDDlgItem);
    [DllImport("user32.dll", CharSet = CharSet.Unicode, SetLastError = true)]
    public static extern int GetWindowText(IntPtr hWnd, StringBuilder text, int count);
}
"@
}

$process = $null
$runtimeProcess = $null
$success = $false
$databasePath = Join-Path $profilePath "Pictures\SandyWallpaperStudio\wallpapers.db"
$settingsPath = Join-Path $profilePath "Pictures\SandyWallpaperStudio\settings.json"
$logPath = Join-Path $profilePath "Pictures\SandyWallpaperStudio\Logs\app.log"
$windowTitle = ""
$databaseIntegrity = "not checked"
$runtimeCheck = "not run"
$failureReason = ""
try {
    New-Item -ItemType Directory -Path $profilePath | Out-Null
    Set-Content -LiteralPath (Join-Path $profilePath $profileMarker) -Value $profileToken -Encoding utf8
    New-Item -ItemType Directory -Path $profileTemp, $profileAppData, $profileLocalAppData | Out-Null
    if (-not ($nativeTypeName -as [type])) {
        Add-Type $nativeInteropSource
    }

    $startInfo = New-Object System.Diagnostics.ProcessStartInfo
    $startInfo.FileName = $executablePath
    $startInfo.UseShellExecute = $false
    $startInfo.CreateNoWindow = $true
    $startInfo.WorkingDirectory = $BundlePath

    $envVars = $startInfo.EnvironmentVariables
    $envVars["USERPROFILE"] = $profilePath
    $envVars["HOME"] = $profilePath
    $envVars["APPDATA"] = $profileAppData
    $envVars["LOCALAPPDATA"] = $profileLocalAppData
    $envVars["TEMP"] = $profileTemp
    $envVars["TMP"] = $profileTemp
    $envVars["PATH"] = (Join-Path $env:WINDIR "System32") + ";" + $env:WINDIR
    foreach ($name in @(
        "PYTHONHOME", "PYTHONPATH", "VIRTUAL_ENV", "CONDA_PREFIX",
        "QT_PLUGIN_PATH", "QT_QPA_PLATFORM_PLUGIN_PATH", "QT_QPA_PLATFORM"
    )) {
        $envVars.Remove($name)
    }

    $versionStartInfo = New-Object System.Diagnostics.ProcessStartInfo
    $versionStartInfo.FileName = $executablePath
    $versionStartInfo.Arguments = "--version"
    $versionStartInfo.UseShellExecute = $false
    $versionStartInfo.CreateNoWindow = $true
    $versionStartInfo.WorkingDirectory = $BundlePath
    $versionEnv = $versionStartInfo.EnvironmentVariables
    $versionEnv["USERPROFILE"] = $profilePath
    $versionEnv["HOME"] = $profilePath
    $versionEnv["PATH"] = (Join-Path $env:WINDIR "System32") + ";" + $env:WINDIR
    foreach ($name in @("PYTHONHOME", "PYTHONPATH", "VIRTUAL_ENV", "CONDA_PREFIX", "QT_PLUGIN_PATH", "QT_QPA_PLATFORM_PLUGIN_PATH")) {
        $versionEnv.Remove($name)
    }
    $versionProcess = [Diagnostics.Process]::Start($versionStartInfo)
    try {
        $versionDeadline = (Get-Date).AddSeconds(15)
        $versionText = ""
        $versionDialogHandle = [IntPtr]::Zero
        while ((Get-Date) -lt $versionDeadline) {
            $versionProcess.Refresh()
            if ($versionProcess.HasExited) {
                throw "The packaged --version command exited without presenting its version."
            }
            $versionDialogHandle = $versionProcess.MainWindowHandle
            if ($versionDialogHandle -ne [IntPtr]::Zero) {
                $messageHandle = [SwsPackageSmokeNativeMethods]::GetDlgItem($versionDialogHandle, 0xFFFF)
                if ($messageHandle -ne [IntPtr]::Zero) {
                    $messageBuilder = New-Object Text.StringBuilder 512
                    [void][SwsPackageSmokeNativeMethods]::GetWindowText($messageHandle, $messageBuilder, $messageBuilder.Capacity)
                    $versionText = $messageBuilder.ToString()
                }
                if (-not [string]::IsNullOrWhiteSpace($versionText)) {
                    break
                }
            }
            Start-Sleep -Milliseconds 200
        }
        if (-not $versionText.Contains($appVersion)) {
            throw "Packaged --version dialog did not report APP_VERSION '$appVersion'."
        }
        [void][SwsPackageSmokeNativeMethods]::PostMessage($versionDialogHandle, 0x0010, [IntPtr]::Zero, [IntPtr]::Zero)
        if (-not $versionProcess.WaitForExit(10000) -or $versionProcess.ExitCode -ne 0) {
            throw "The packaged --version dialog did not close with exit code 0."
        }
    }
    finally {
        if ($null -ne $versionProcess) {
            $versionProcess.Refresh()
            if (-not $versionProcess.HasExited -and $versionProcess.MainWindowHandle -ne [IntPtr]::Zero) {
                [void][SwsPackageSmokeNativeMethods]::PostMessage($versionProcess.MainWindowHandle, 0x0010, [IntPtr]::Zero, [IntPtr]::Zero)
                [void]$versionProcess.WaitForExit(5000)
            }
            if ($versionProcess.HasExited) {
                $versionProcess.Dispose()
            }
        }
    }

    $runtimeStartInfo = New-Object System.Diagnostics.ProcessStartInfo
    $runtimeStartInfo.FileName = $executablePath
    $runtimeStartInfo.Arguments = "--validate-runtime"
    $runtimeStartInfo.UseShellExecute = $false
    $runtimeStartInfo.CreateNoWindow = $true
    $runtimeStartInfo.WorkingDirectory = $BundlePath
    foreach ($name in $startInfo.EnvironmentVariables.Keys) {
        $runtimeStartInfo.EnvironmentVariables[$name] = $startInfo.EnvironmentVariables[$name]
    }
    $runtimeProcess = [Diagnostics.Process]::Start($runtimeStartInfo)
    if ($null -eq $runtimeProcess) {
        throw "Could not start the packaged runtime validation command."
    }
    $runtimeDeadline = (Get-Date).AddSeconds(45)
    $runtimeDialogHandle = [IntPtr]::Zero
    $runtimeText = ""
    while ((Get-Date) -lt $runtimeDeadline) {
        $runtimeProcess.Refresh()
        if ($runtimeProcess.HasExited) {
            throw "Packaged runtime validation exited without presenting its result (code $($runtimeProcess.ExitCode))."
        }
        $runtimeDialogHandle = $runtimeProcess.MainWindowHandle
        if ($runtimeDialogHandle -ne [IntPtr]::Zero) {
            $runtimeMessageHandle = [SwsPackageSmokeNativeMethods]::GetDlgItem($runtimeDialogHandle, 0xFFFF)
            if ($runtimeMessageHandle -ne [IntPtr]::Zero) {
                $runtimeMessageBuilder = New-Object Text.StringBuilder 1024
                [void][SwsPackageSmokeNativeMethods]::GetWindowText($runtimeMessageHandle, $runtimeMessageBuilder, $runtimeMessageBuilder.Capacity)
                $runtimeText = $runtimeMessageBuilder.ToString()
            }
            if (-not [string]::IsNullOrWhiteSpace($runtimeText)) {
                break
            }
        }
        Start-Sleep -Milliseconds 200
    }
    if (-not $runtimeText.Contains("Runtime check passed") -or
        -not $runtimeText.Contains("pHash") -or
        -not $runtimeText.Contains($appVersion)) {
        throw "Packaged runtime validation did not report all image/hash/storage checks."
    }
    [void][SwsPackageSmokeNativeMethods]::PostMessage($runtimeDialogHandle, 0x0010, [IntPtr]::Zero, [IntPtr]::Zero)
    if (-not $runtimeProcess.WaitForExit(10000) -or $runtimeProcess.ExitCode -ne 0) {
        throw "Packaged runtime validation did not close with exit code 0."
    }
    $runtimeProcess.Dispose()
    $runtimeProcess = $null
    $runtimeCheck = "PNG metadata, SHA-256, pHash, thumbnail, settings schema, SQLite integrity: passed"

    $process = [Diagnostics.Process]::Start($startInfo)
    if ($null -eq $process) {
        throw "Could not start the packaged GUI."
    }
    $deadline = (Get-Date).AddSeconds(40)
    while ((Get-Date) -lt $deadline) {
        $process.Refresh()
        if ($process.HasExited) {
            throw "The packaged GUI exited during startup with code $($process.ExitCode)."
        }
        if ($process.MainWindowHandle -ne [IntPtr]::Zero -and
            -not [string]::IsNullOrWhiteSpace($process.MainWindowTitle)) {
            $windowTitle = $process.MainWindowTitle
            break
        }
        Start-Sleep -Milliseconds 500
    }
    if ([string]::IsNullOrWhiteSpace($windowTitle)) {
        throw "The packaged GUI did not expose a main window within 40 seconds."
    }
    if (-not $windowTitle.Contains($appVersion)) {
        throw "Main window title '$windowTitle' did not report APP_VERSION '$appVersion'."
    }

    $windowHandle = $process.MainWindowHandle
    [void][SwsPackageSmokeNativeMethods]::PostMessage($windowHandle, 0x0010, [IntPtr]::Zero, [IntPtr]::Zero)
    if (-not $process.WaitForExit(15000)) {
        throw "The packaged GUI did not shut down within 15 seconds after WM_CLOSE."
    }
    if ($process.ExitCode -ne 0) {
        throw "The packaged GUI returned exit code $($process.ExitCode) after shutdown."
    }
    $process.Dispose()
    $process = $null

    foreach ($path in @($settingsPath, $databasePath, $logPath)) {
        if (-not (Test-Path -LiteralPath $path -PathType Leaf)) {
            throw "First-run initialization did not create expected file '$path'."
        }
    }
    $settings = Get-Content -LiteralPath $settingsPath -Raw | ConvertFrom-Json
    if ($settings.config_schema_version -ne 2) {
        throw "First-run settings did not persist schema version 2."
    }
    foreach ($directory in @("Library", "Cache", "Temp", "Logs", "Exports", "Duplicates")) {
        if (-not (Test-Path -LiteralPath (Join-Path (Split-Path $databasePath -Parent) $directory) -PathType Container)) {
            throw "First-run directory '$directory' was not created under the isolated profile."
        }
    }
    $logText = Get-Content -LiteralPath $logPath -Raw
    if ($logText -notmatch "initialized successfully" -or $logText -notmatch "shutdown") {
        throw "The isolated first-run log does not show successful initialization and shutdown."
    }

    $sqliteCheck = @'
import json
import sqlite3
import sys
from pathlib import Path

profile = Path(sys.argv[1])
database = profile / 'Pictures' / 'SandyWallpaperStudio' / 'wallpapers.db'
with sqlite3.connect(database.as_uri() + '?mode=ro', uri=True) as connection:
    integrity = connection.execute('PRAGMA integrity_check').fetchone()[0]
    tables = sorted(row[0] for row in connection.execute('SELECT name FROM sqlite_master WHERE type=\'table\''))
print(json.dumps({'integrity': integrity, 'table_count': len(tables)}))
'@
    $databaseReportText = & $PythonPath -c $sqliteCheck $profilePath
    if ($LASTEXITCODE -ne 0) {
        throw "Could not inspect the packaged first-run database."
    }
    $databaseReport = $databaseReportText | ConvertFrom-Json
    $databaseIntegrity = $databaseReport.integrity
    if ($databaseIntegrity -ne "ok" -or $databaseReport.table_count -lt 1) {
        throw "Packaged first-run SQLite validation failed: $databaseReportText"
    }
    $success = $true
}
catch {
    $failureReason = $_.Exception.Message
    throw
}
finally {
    if ($null -ne $runtimeProcess) {
        $runtimeProcess.Refresh()
        if (-not $runtimeProcess.HasExited -and $runtimeProcess.MainWindowHandle -ne [IntPtr]::Zero) {
            [void][SwsPackageSmokeNativeMethods]::PostMessage($runtimeProcess.MainWindowHandle, 0x0010, [IntPtr]::Zero, [IntPtr]::Zero)
            [void]$runtimeProcess.WaitForExit(5000)
        }
        if ($runtimeProcess.HasExited) {
            $runtimeProcess.Dispose()
        }
    }
    if ($null -ne $process) {
        $process.Refresh()
        if (-not $process.HasExited -and $process.MainWindowHandle -ne [IntPtr]::Zero) {
            [void][SwsPackageSmokeNativeMethods]::PostMessage($process.MainWindowHandle, 0x0010, [IntPtr]::Zero, [IntPtr]::Zero)
            [void]$process.WaitForExit(5000)
        }
        if ($process.HasExited) {
            $process.Dispose()
        }
    }
    $manifestRoot = Split-Path (Split-Path $BundlePath -Parent) -Parent
    if (Test-Path -LiteralPath $manifestRoot -PathType Container) {
        $report = [ordered]@{
            result = if ($success) { "PASS" } else { "FAIL" }
            app_version = $appVersion
            product_version = $versionInfo.ProductVersion
            executable_path = $executablePath
            tested_from_path_with_spaces = ($BundlePath -match "\s")
            sanitized_process_path = $true
            isolated_profile = $true
            gui_window_title = $windowTitle
            first_run_settings_and_directories = (Test-Path -LiteralPath $settingsPath)
            runtime_validation = $runtimeCheck
            sqlite_integrity = $databaseIntegrity
            startup_log_path = if (Test-Path -LiteralPath $logPath) { "<isolated temporary profile>\Pictures\SandyWallpaperStudio\Logs\app.log" } else { "not created" }
            failure = $failureReason
        }
        $report | ConvertTo-Json -Depth 4 | Set-Content -LiteralPath (Join-Path $manifestRoot "validation-result.json") -Encoding utf8
    }

    if ($success -and (Test-Path -LiteralPath $profilePath)) {
        $markerPath = Join-Path $profilePath $profileMarker
        if ((Get-Item -LiteralPath $profilePath).Attributes -band [IO.FileAttributes]::ReparsePoint -or
            -not (Test-Path -LiteralPath $markerPath -PathType Leaf) -or
            (Get-Content -LiteralPath $markerPath -Raw).Trim() -ne $profileToken) {
            throw "Validation passed but the temporary profile could not be verified as script-owned; preserving it at '$profilePath'."
        }
        $profileFullPath = [IO.Path]::GetFullPath($profilePath)
        if (-not $profileFullPath.StartsWith($tempPrefix, [StringComparison]::OrdinalIgnoreCase) -or
            $profileFullPath -eq $tempRoot) {
            throw "Refusing to remove a path outside the generated temporary profile directory."
        }
        Remove-Item -LiteralPath $profileFullPath -Recurse -Force
    }
    elseif (Test-Path -LiteralPath $profilePath) {
        Write-Warning "Validation did not pass; preserving the isolated profile and diagnostics at '$profilePath'."
    }
}

Write-Host "Packaged Windows smoke test passed."
Write-Host "Product version: $($versionInfo.ProductVersion)"
Write-Host "Packaged runtime: $runtimeCheck"
Write-Host "Main window title: $windowTitle"
Write-Host "First-run SQLite integrity: $databaseIntegrity"
Write-Host "The process used an isolated temporary profile and a sanitized PATH without the development venv."
