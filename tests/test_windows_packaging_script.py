from pathlib import Path

SCRIPT = Path("packaging/windows/build_portable.ps1")


def test_portable_builder_rejects_failed_pyinstaller_process() -> None:
    source = SCRIPT.read_text(encoding="utf-8")

    invocation = source.index("-m PyInstaller")
    exit_guard = source.index("if ($LASTEXITCODE -ne 0)", invocation)
    archive = source.index("Compress-Archive")

    assert invocation < exit_guard < archive
    assert "No portable archive was produced" in source


def test_portable_builder_cannot_relabel_a_stale_executable() -> None:
    source = SCRIPT.read_text(encoding="utf-8")

    cleanup = source.index("foreach ($generatedPath")
    invocation = source.index("-m PyInstaller")
    version_check = source.index("Executable version mismatch")
    archive = source.index("Compress-Archive")

    assert cleanup < invocation < version_check < archive
    assert "Assert-ChildPath" in source


def test_portable_builder_bounds_smoke_time_and_removes_failed_archive() -> None:
    source = SCRIPT.read_text(encoding="utf-8")

    assert "$SmokeTimeoutSeconds = 240" in source
    assert "WaitForExit([Math]::Max(1, $SmokeTimeoutSeconds) * 1000)" in source
    assert "taskkill.exe /PID $process.Id /T /F" in source
    assert "foreach ($failedArtifact in @($ZipPath, $checksumPath))" in source


def test_portable_builder_prefers_the_selected_python_runtime_dlls() -> None:
    source = SCRIPT.read_text(encoding="utf-8")

    assert "import sys; print(sys.base_prefix)" in source
    assert 'Join-Path $pythonBase "Library\\bin"' in source
    assert "$env:PATH =" in source


def test_portable_builder_removes_upstream_test_fixtures_before_archiving() -> None:
    source = SCRIPT.read_text(encoding="utf-8")

    cleanup = source.index("$developmentArtifactDirs")
    archive = source.index("Compress-Archive")

    assert cleanup < archive
    assert '"_internal\\pyarrow\\tests"' in source
    assert '"_internal\\sklearn\\datasets\\tests"' in source
    assert "Assert-ChildPath -Path $developmentArtifactDir -Parent $AppDir" in source
