param(
    [switch]$SkipSmokeTest,
    [string]$Python = "python"
)

$ErrorActionPreference = "Stop"
$RepoRoot = (Resolve-Path (Join-Path $PSScriptRoot "..\..")).Path
Set-Location $RepoRoot

& $Python -m PyInstaller --clean --noconfirm packaging/windows/MaterialAIWorkbench.spec

$AppDir = Join-Path $RepoRoot "dist\MaterialAIWorkbench"
$ExePath = Join-Path $AppDir "MaterialAIWorkbench.exe"
if (-not (Test-Path -LiteralPath $ExePath)) {
    throw "Desktop executable was not created: $ExePath"
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

$version = & $Python -c "import tomllib; print(tomllib.load(open('pyproject.toml','rb'))['project']['version'])"
$ZipName = "MaterialAI-Workbench-Windows-x64-v$version.zip"
$ZipPath = Join-Path $RepoRoot "dist\$ZipName"
if (Test-Path -LiteralPath $ZipPath) {
    Remove-Item -LiteralPath $ZipPath -Force
}
Compress-Archive -LiteralPath $AppDir -DestinationPath $ZipPath -CompressionLevel Optimal

if (-not $SkipSmokeTest) {
    $SmokeRoot = [IO.Path]::GetFullPath((Join-Path $RepoRoot "dist\_portable_archive_smoke"))
    $DistRoot = [IO.Path]::GetFullPath((Join-Path $RepoRoot "dist"))
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
        $process = Start-Process -FilePath $ExtractedExe -ArgumentList @("--smoke-test", "--startup-timeout", "180") -PassThru -Wait
        if ($process.ExitCode -ne 0) {
            throw "Extracted portable client smoke test failed with exit code $($process.ExitCode)"
        }
    }
    finally {
        if (Test-Path -LiteralPath $SmokeRoot) {
            Remove-Item -LiteralPath $SmokeRoot -Recurse -Force
        }
    }
}

$hash = (Get-FileHash -LiteralPath $ZipPath -Algorithm SHA256).Hash.ToLowerInvariant()
$checksumPath = "$ZipPath.sha256"
Set-Content -LiteralPath $checksumPath -Value "$hash  $ZipName" -Encoding ascii

Write-Host "Portable client: $ZipPath"
Write-Host "SHA256: $checksumPath"
Write-Host "Uncompressed size: $appSizeMb MB"
