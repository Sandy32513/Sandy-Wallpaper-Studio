[CmdletBinding()]
param(
    [string]$PythonPath = "",
    [switch]$SkipDependencyInstall,
    [switch]$SkipPreBuildChecks
)

$ErrorActionPreference = "Stop"
$repoRoot = [IO.Path]::GetFullPath((Join-Path $PSScriptRoot ".."))
$specPath = Join-Path $repoRoot "packaging\SandyWallpaperStudio.spec"
if (-not (Test-Path -LiteralPath (Join-Path $repoRoot "pyproject.toml")) -or
    -not (Test-Path -LiteralPath $specPath)) {
    throw "Run this script from a valid Sandy Wallpaper Studio checkout."
}
if ($env:OS -ne "Windows_NT") {
    throw "A Windows x64 host is required to build the Windows executable."
}

if ([string]::IsNullOrWhiteSpace($PythonPath)) {
    $PythonPath = Join-Path $repoRoot ".venv\Scripts\python.exe"
}
if (-not (Test-Path -LiteralPath $PythonPath -PathType Leaf)) {
    throw "Python interpreter not found at '$PythonPath'. Create the project .venv or pass -PythonPath."
}
$PythonPath = (Resolve-Path -LiteralPath $PythonPath).Path

function Invoke-Checked {
    param(
        [Parameter(Mandatory = $true)][string]$Executable,
        [Parameter(Mandatory = $true)][string[]]$Arguments,
        [Parameter(Mandatory = $true)][string]$Label
    )
    & $Executable @Arguments
    if ($LASTEXITCODE -ne 0) {
        throw "$Label failed with exit code $LASTEXITCODE."
    }
}

Push-Location $repoRoot
try {
    $pythonInfoText = & $PythonPath -c "import json, platform, struct, sys; print(json.dumps({'version': list(sys.version_info[:3]), 'is_venv': sys.prefix != sys.base_prefix, 'machine': platform.machine(), 'bits': struct.calcsize('P') * 8}))"
    if ($LASTEXITCODE -ne 0) {
        throw "Could not inspect the selected Python interpreter."
    }
    $pythonInfo = $pythonInfoText | ConvertFrom-Json
    if ($pythonInfo.version[0] -ne 3 -or $pythonInfo.version[1] -ne 12 -or
        -not $pythonInfo.is_venv -or $pythonInfo.bits -ne 64) {
        throw "Use a 64-bit Python 3.12 virtual environment; selected interpreter was $pythonInfoText."
    }

    $projectMetadata = Get-Content -LiteralPath (Join-Path $repoRoot "pyproject.toml") -Raw
    $metadataVersionMatch = [regex]::Match($projectMetadata, '(?m)^version\s*=\s*"([^"]+)"')
    if (-not $metadataVersionMatch.Success) {
        throw "Could not read the project version from pyproject.toml."
    }
    $pyinstallerMatch = [regex]::Match($projectMetadata, 'pyinstaller==([0-9]+\.[0-9]+\.[0-9]+)')
    if (-not $pyinstallerMatch.Success) {
        throw "pyproject.toml must pin the packaging PyInstaller version."
    }
    $expectedPyInstaller = $pyinstallerMatch.Groups[1].Value

    if (-not $SkipDependencyInstall) {
        Invoke-Checked $PythonPath @("-m", "pip", "install", "-e", ".[dev,packaging]") "Install declared development and packaging dependencies"
    }
    Invoke-Checked $PythonPath @("-m", "pip", "check") "Dependency consistency check"

    $pyinstallerVersion = (& $PythonPath -m PyInstaller --version).Trim()
    if ($LASTEXITCODE -ne 0 -or $pyinstallerVersion -ne $expectedPyInstaller) {
        throw "Expected PyInstaller $expectedPyInstaller; found '$pyinstallerVersion'."
    }

    $appVersion = (& $PythonPath -c "from app.constants import APP_VERSION; print(APP_VERSION)").Trim()
    if ($LASTEXITCODE -ne 0) {
        throw "Could not read APP_VERSION from app.constants."
    }
    if ($appVersion -ne $metadataVersionMatch.Groups[1].Value) {
        throw "pyproject.toml and app.constants disagree on the application version."
    }
    $versionMatch = [regex]::Match($appVersion, '^(\d+)\.(\d+)\.(\d+)(?:-[A-Za-z0-9.-]+)?$')
    if (-not $versionMatch.Success) {
        throw "APP_VERSION '$appVersion' cannot be encoded as Windows numeric version metadata."
    }
    $major = [int]$versionMatch.Groups[1].Value
    $minor = [int]$versionMatch.Groups[2].Value
    $patch = [int]$versionMatch.Groups[3].Value
    foreach ($component in @($major, $minor, $patch)) {
        if ($component -gt 65535) {
            throw "Windows version components must fit in unsigned 16-bit fields."
        }
    }
    $numericVersion = "$major.$minor.$patch.0"

    $buildParent = [IO.Path]::GetFullPath((Join-Path $repoRoot "build"))
    $outputRoot = [IO.Path]::GetFullPath((Join-Path $buildParent "phase 12"))
    $ownerToken = "SandyWallpaperStudio Phase12 generated output v1"
    New-Item -ItemType Directory -Path $buildParent -Force | Out-Null
    if ((Get-Item -LiteralPath $buildParent).Attributes -band [IO.FileAttributes]::ReparsePoint) {
        throw "The repository build directory is a reparse point; refusing to write through it."
    }
    if (Test-Path -LiteralPath $outputRoot) {
        if ((Get-Item -LiteralPath $outputRoot).Attributes -band [IO.FileAttributes]::ReparsePoint) {
            throw "The existing packaging output is a reparse point; preserving it."
        }
        $markerPath = Join-Path $outputRoot ".sws-packaging-owner"
        if (-not (Test-Path -LiteralPath $markerPath -PathType Leaf) -or
            (Get-Content -LiteralPath $markerPath -Raw).Trim() -ne $ownerToken) {
            throw "The build output '$outputRoot' exists without this script's ownership marker; preserving it."
        }
        if ((Get-Item -LiteralPath $markerPath).Attributes -band [IO.FileAttributes]::ReparsePoint) {
            throw "The packaging output ownership marker is a reparse point; preserving the output."
        }

        $separator = [IO.Path]::DirectorySeparatorChar
        $buildParentPrefix = $buildParent.TrimEnd($separator) + $separator
        if (-not $outputRoot.StartsWith($buildParentPrefix, [StringComparison]::OrdinalIgnoreCase) -or
            $outputRoot -eq $buildParent) {
            throw "Refusing to move a packaging output outside the repository build directory."
        }
        $archiveName = "phase 12-preserved-" + (Get-Date -Format "yyyyMMdd-HHmmss-fff")
        $archivePath = [IO.Path]::GetFullPath((Join-Path $buildParent $archiveName))
        if (-not $archivePath.StartsWith($buildParentPrefix, [StringComparison]::OrdinalIgnoreCase) -or
            (Test-Path -LiteralPath $archivePath)) {
            throw "Could not safely preserve the previous packaging output."
        }
        Move-Item -LiteralPath $outputRoot -Destination $archivePath
        Write-Host "Preserved previous generated build output at $archivePath"
    }

    New-Item -ItemType Directory -Path $outputRoot | Out-Null
    Set-Content -LiteralPath (Join-Path $outputRoot ".sws-packaging-owner") -Value $ownerToken -Encoding utf8
    $versionInfoPath = Join-Path $outputRoot "version_info.txt"
    $versionInfo = @"
VSVersionInfo(
  ffi=FixedFileInfo(
    filevers=($major, $minor, $patch, 0),
    prodvers=($major, $minor, $patch, 0),
    mask=0x3f,
    flags=0x0,
    OS=0x4,
    fileType=0x1,
    subtype=0x0,
    date=(0, 0)
  ),
  kids=[
    StringFileInfo([
      StringTable('040904B0', [
        StringStruct('CompanyName', 'Sandy'),
        StringStruct('FileDescription', 'Sandy Wallpaper Studio desktop application'),
        StringStruct('FileVersion', '$numericVersion'),
        StringStruct('InternalName', 'SandyWallpaperStudio'),
        StringStruct('OriginalFilename', 'SandyWallpaperStudio.exe'),
        StringStruct('ProductName', 'Sandy Wallpaper Studio'),
        StringStruct('ProductVersion', '$appVersion'),
      ])
    ]),
    VarFileInfo([VarStruct('Translation', [1033, 1200])])
  ]
)
"@
    Set-Content -LiteralPath $versionInfoPath -Value $versionInfo -Encoding utf8

    if (-not $SkipPreBuildChecks) {
        Invoke-Checked $PythonPath @("-m", "app", "--version") "Module version check"
        $consoleEntry = Join-Path (Split-Path $PythonPath -Parent) "sandy-wallpaper-studio.exe"
        if (-not (Test-Path -LiteralPath $consoleEntry -PathType Leaf)) {
            throw "The declared console entry point is missing from the selected environment."
        }
        $consoleVersion = (& $consoleEntry --version | Out-String).Trim()
        if ($LASTEXITCODE -ne 0 -or $consoleVersion -notmatch [regex]::Escape($appVersion)) {
            throw "The console entry point did not report APP_VERSION '$appVersion'."
        }

        $oldQtPlatform = $env:QT_QPA_PLATFORM
        try {
            $env:QT_QPA_PLATFORM = "offscreen"
            Invoke-Checked $PythonPath @("-m", "pytest", "-q") "Full test suite"
        }
        finally {
            if ($null -eq $oldQtPlatform) {
                Remove-Item Env:QT_QPA_PLATFORM -ErrorAction SilentlyContinue
            }
            else {
                $env:QT_QPA_PLATFORM = $oldQtPlatform
            }
        }
        Invoke-Checked $PythonPath @("-m", "ruff", "check", ".") "Ruff"
        Invoke-Checked $PythonPath @("-m", "mypy", "app") "mypy"
    }

    $oldVersionInfo = $env:SWS_VERSION_FILE
    try {
        $env:SWS_VERSION_FILE = $versionInfoPath
        $distPath = Join-Path $outputRoot "dist"
        $workPath = Join-Path $outputRoot "work"
        Invoke-Checked $PythonPath @(
            "-m", "PyInstaller", "--noconfirm",
            "--distpath", $distPath,
            "--workpath", $workPath,
            $specPath
        ) "PyInstaller build"
    }
    finally {
        if ($null -eq $oldVersionInfo) {
            Remove-Item Env:SWS_VERSION_FILE -ErrorAction SilentlyContinue
        }
        else {
            $env:SWS_VERSION_FILE = $oldVersionInfo
        }
    }

    $bundlePath = Join-Path $outputRoot "dist\SandyWallpaperStudio"
    $executablePath = Join-Path $bundlePath "SandyWallpaperStudio.exe"
    if (-not (Test-Path -LiteralPath $executablePath -PathType Leaf)) {
        throw "Expected executable was not created: $executablePath"
    }
    $executable = Get-Item -LiteralPath $executablePath
    if ($executable.Length -lt 100KB) {
        throw "The executable is unexpectedly small ($($executable.Length) bytes)."
    }
    $qtCore = Get-ChildItem -LiteralPath $bundlePath -Filter "Qt6Core.dll" -File -Recurse | Select-Object -First 1
    $qtPlatform = Get-ChildItem -LiteralPath $bundlePath -Filter "qwindows.dll" -File -Recurse | Select-Object -First 1
    if ($null -eq $qtCore -or $null -eq $qtPlatform) {
        throw "The bundle is missing required Qt runtime or Windows platform plug-in files."
    }
    $productVersion = $executable.VersionInfo.ProductVersion
    if ($productVersion -ne $appVersion) {
        throw "Executable ProductVersion '$productVersion' does not match APP_VERSION '$appVersion'."
    }
    $fileVersion = $executable.VersionInfo.FileVersion
    if ($fileVersion -notmatch [regex]::Escape($numericVersion)) {
        throw "Executable FileVersion '$fileVersion' does not match '$numericVersion'."
    }

    $workingTreeStatus = @(& git status --porcelain)
    if ($LASTEXITCODE -ne 0) {
        throw "Could not inspect the working tree for the local build manifest."
    }
    $manifest = [ordered]@{
        app_version = $appVersion
        file_version = $numericVersion
        pyinstaller_version = $pyinstallerVersion
        python_version = ($pythonInfo.version -join ".")
        architecture = "Windows x64"
        build_mode = "onedir, windowed, unsigned"
        executable_path = $executablePath
        executable_bytes = $executable.Length
        bundle_bytes = (Get-ChildItem -LiteralPath $bundlePath -File -Recurse | Measure-Object -Property Length -Sum).Sum
        qt_core = $qtCore.FullName
        qt_windows_platform_plugin = $qtPlatform.FullName
        source_commit = (& git rev-parse HEAD).Trim()
        source_tree_dirty = ($workingTreeStatus.Count -gt 0)
    }
    $manifestPath = Join-Path $outputRoot "build-manifest.json"
    $manifest | ConvertTo-Json -Depth 4 | Set-Content -LiteralPath $manifestPath -Encoding utf8

    $validatorPath = Join-Path $repoRoot "scripts\validate_packaged_windows.ps1"
    & $validatorPath -BundlePath $bundlePath -PythonPath $PythonPath -RequirePathWithSpaces

    Write-Host "Build complete"
    Write-Host "APP_VERSION: $appVersion"
    Write-Host "PyInstaller: $pyinstallerVersion"
    Write-Host "Executable: $executablePath ($($executable.Length) bytes)"
    Write-Host "Bundle size: $($manifest.bundle_bytes) bytes"
    Write-Host "Manifest: $manifestPath"
    Write-Host "Packaged GUI first-run and shutdown smoke test passed."
}
finally {
    Pop-Location
}
