param(
    [switch]$SkipSmokeTest,
    [string]$Python = "",
    [int]$SmokeTimeoutSeconds = 240
)

$ErrorActionPreference = "Stop"
$RepoRoot = (Resolve-Path (Join-Path $PSScriptRoot "..\..")).Path
Set-Location $RepoRoot

function Assert-ChildPath {
    param(
        [Parameter(Mandatory = $true)][string]$Path,
        [Parameter(Mandatory = $true)][string]$Parent
    )

    $fullPath = [IO.Path]::GetFullPath($Path)
    $fullParent = [IO.Path]::GetFullPath($Parent).TrimEnd(
        [IO.Path]::DirectorySeparatorChar,
        [IO.Path]::AltDirectorySeparatorChar
    )
    if (-not $fullPath.StartsWith($fullParent + [IO.Path]::DirectorySeparatorChar, [StringComparison]::OrdinalIgnoreCase)) {
        throw "Unsafe generated-artifact path: $fullPath"
    }
    return $fullPath
}

if ([string]::IsNullOrWhiteSpace($Python)) {
    $Python = if ($env:CONDA_PREFIX -and (Test-Path -LiteralPath (Join-Path $env:CONDA_PREFIX "python.exe"))) {
        Join-Path $env:CONDA_PREFIX "python.exe"
    }
    else {
        "python"
    }
}

$PythonCommand = if (Test-Path -LiteralPath $Python) {
    (Resolve-Path -LiteralPath $Python).Path
}
else {
    (Get-Command $Python -ErrorAction Stop).Source
}

$versionOutput = & $PythonCommand -c "import tomllib; print(tomllib.load(open('pyproject.toml','rb'))['project']['version'])"
if ($LASTEXITCODE -ne 0) {
    throw "Unable to read the project version with $PythonCommand (exit code $LASTEXITCODE)."
}
$version = ($versionOutput | Select-Object -Last 1).Trim()
if ([string]::IsNullOrWhiteSpace($version)) {
    throw "The project version is empty."
}

$pythonBaseOutput = & $PythonCommand -c "import sys; print(sys.base_prefix)"
if ($LASTEXITCODE -ne 0) {
    throw "Unable to read the Python base prefix with $PythonCommand (exit code $LASTEXITCODE)."
}
$pythonBase = ($pythonBaseOutput | Select-Object -Last 1).Trim()
$runtimeSearchPaths = @(
    (Join-Path $pythonBase "Library\bin"),
    (Join-Path $pythonBase "DLLs"),
    $pythonBase
) | Where-Object { Test-Path -LiteralPath $_ }
if ($runtimeSearchPaths.Count -gt 0) {
    $env:PATH = (($runtimeSearchPaths -join [IO.Path]::PathSeparator) + [IO.Path]::PathSeparator + $env:PATH)
}

$DistRoot = Assert-ChildPath -Path (Join-Path $RepoRoot "dist") -Parent $RepoRoot
$AppDir = Assert-ChildPath -Path (Join-Path $DistRoot "MaterialAIWorkbench") -Parent $DistRoot
$BuildDir = Assert-ChildPath -Path (Join-Path $RepoRoot "build\MaterialAIWorkbench") -Parent $RepoRoot
$ZipName = "MaterialAI-Workbench-Windows-x64-v$version.zip"
$ZipPath = Assert-ChildPath -Path (Join-Path $DistRoot $ZipName) -Parent $DistRoot
$checksumPath = Assert-ChildPath -Path "$ZipPath.sha256" -Parent $DistRoot

foreach ($generatedPath in @($AppDir, $BuildDir)) {
    if (Test-Path -LiteralPath $generatedPath) {
        Remove-Item -LiteralPath $generatedPath -Recurse -Force
    }
}
foreach ($generatedFile in @($ZipPath, $checksumPath)) {
    if (Test-Path -LiteralPath $generatedFile) {
        Remove-Item -LiteralPath $generatedFile -Force
    }
}

& $PythonCommand -m PyInstaller --clean --noconfirm packaging/windows/MaterialAIWorkbench.spec
if ($LASTEXITCODE -ne 0) {
    throw "PyInstaller failed with exit code $LASTEXITCODE. No portable archive was produced."
}

$ExePath = Join-Path $AppDir "MaterialAIWorkbench.exe"
if (-not (Test-Path -LiteralPath $ExePath)) {
    throw "Desktop executable was not created: $ExePath"
}

$exeVersion = (Get-Item -LiteralPath $ExePath).VersionInfo.ProductVersion
if ($exeVersion -ne $version) {
    throw "Executable version mismatch: expected $version, found $exeVersion."
}

# PyInstaller hooks for Arrow and scikit-learn collect upstream test fixtures
# that are not used by the desktop client. Keep the public ZIP free of them.
$developmentArtifactDirs = @(
    (Join-Path $AppDir "_internal\pyarrow\tests"),
    (Join-Path $AppDir "_internal\sklearn\datasets\tests")
)
foreach ($developmentArtifactDir in $developmentArtifactDirs) {
    $safeArtifactDir = Assert-ChildPath -Path $developmentArtifactDir -Parent $AppDir
    if (Test-Path -LiteralPath $safeArtifactDir) {
        Remove-Item -LiteralPath $safeArtifactDir -Recurse -Force
    }
}

Copy-Item -LiteralPath "packaging\windows\README-START.txt" -Destination $AppDir -Force
Copy-Item -LiteralPath "LICENSE" -Destination $AppDir -Force
Copy-Item -LiteralPath "NOTICE.md" -Destination $AppDir -Force
Copy-Item -LiteralPath "THIRD_PARTY_LICENSES" -Destination $AppDir -Force

$appSizeBytes = (Get-ChildItem -LiteralPath $AppDir -Recurse -File | Measure-Object -Property Length -Sum).Sum
$appSizeMb = [math]::Round($appSizeBytes / 1MB, 1)
if ($appSizeMb -gt 700) {
    throw "Portable client is unexpectedly large ($appSizeMb MB); inspect PyInstaller collection rules."
}

Compress-Archive -LiteralPath $AppDir -DestinationPath $ZipPath -CompressionLevel Optimal

if (-not $SkipSmokeTest) {
    $SmokeRoot = [IO.Path]::GetFullPath((Join-Path $RepoRoot "dist\_portable_archive_smoke"))
    if (-not $SmokeRoot.StartsWith($DistRoot + [IO.Path]::DirectorySeparatorChar, [StringComparison]::OrdinalIgnoreCase)) {
        throw "Unsafe archive smoke-test path: $SmokeRoot"
    }
    if (Test-Path -LiteralPath $SmokeRoot) {
        Remove-Item -LiteralPath $SmokeRoot -Recurse -Force
    }
    try {
        Expand-Archive -LiteralPath $ZipPath -DestinationPath $SmokeRoot
        $ExtractedExe = Join-Path $SmokeRoot "MaterialAIWorkbench\MaterialAIWorkbench.exe"
        if (-not (Test-Path -LiteralPath $ExtractedExe)) {
            throw "Portable archive does not contain MaterialAIWorkbench\MaterialAIWorkbench.exe"
        }
        $process = Start-Process -FilePath $ExtractedExe -ArgumentList @("--smoke-test", "--startup-timeout", "180") -PassThru
        if (-not $process.WaitForExit([Math]::Max(1, $SmokeTimeoutSeconds) * 1000)) {
            & taskkill.exe /PID $process.Id /T /F | Out-Null
            throw "Extracted portable client smoke test timed out after $SmokeTimeoutSeconds seconds."
        }
        if ($process.ExitCode -ne 0) {
            throw "Extracted portable client smoke test failed with exit code $($process.ExitCode)"
        }
    }
    catch {
        foreach ($failedArtifact in @($ZipPath, $checksumPath)) {
            if (Test-Path -LiteralPath $failedArtifact) {
                Remove-Item -LiteralPath $failedArtifact -Force
            }
        }
        throw
    }
    finally {
        if (Test-Path -LiteralPath $SmokeRoot) {
            Remove-Item -LiteralPath $SmokeRoot -Recurse -Force
        }
    }
}

$hash = (Get-FileHash -LiteralPath $ZipPath -Algorithm SHA256).Hash.ToLowerInvariant()
Set-Content -LiteralPath $checksumPath -Value "$hash  $ZipName" -Encoding ascii

Write-Host "Portable client: $ZipPath"
Write-Host "SHA256: $checksumPath"
Write-Host "Uncompressed size: $appSizeMb MB"
