from __future__ import annotations

import os
import socket
from pathlib import Path

import pytest

from material_ai_workbench.desktop_launcher import (
    DesktopLaunchError,
    backend_command,
    configure_desktop_environment,
    find_available_port,
    log_tail,
    verify_native_window_runtime,
)


def test_configure_desktop_environment_uses_writable_user_paths(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    for name in (
        "MATERIALAI_WORKSPACE_ROOT",
        "MATERIALAI_ENV_FILE",
        "MATERIALAI_DESKTOP_LOG_DIR",
    ):
        monkeypatch.delenv(name, raising=False)

    paths = configure_desktop_environment(tmp_path / "client")

    assert paths.workspace.is_dir()
    assert paths.config.is_dir()
    assert paths.logs.is_dir()
    assert Path(os.environ["MATERIALAI_WORKSPACE_ROOT"]) == paths.workspace
    assert Path(os.environ["MATERIALAI_ENV_FILE"]) == paths.env_file
    assert Path(os.environ["MATERIALAI_DESKTOP_LOG_DIR"]) == paths.logs


def test_find_available_port_returns_bindable_loopback_port() -> None:
    port = find_available_port()
    assert 1 <= port <= 65535
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as probe:
        probe.bind(("127.0.0.1", port))


def test_requested_busy_port_is_rejected() -> None:
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as listener:
        listener.bind(("127.0.0.1", 0))
        port = int(listener.getsockname()[1])
        with pytest.raises(DesktopLaunchError, match="已被占用"):
            find_available_port(port)


def test_source_backend_command_uses_module_entrypoint(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.delattr("sys.frozen", raising=False)
    command = backend_command(50123)
    assert command[1:4] == ["-m", "material_ai_workbench.desktop_launcher", "--serve"]
    assert command[-2:] == ["--port", "50123"]


def test_log_tail_limits_output(tmp_path: Path) -> None:
    log = tmp_path / "server.log"
    log.write_text("\n".join(f"line-{index}" for index in range(30)), encoding="utf-8")
    tail = log_tail(log, max_lines=3)
    assert tail.splitlines() == ["line-27", "line-28", "line-29"]


def test_native_window_runtime_failure_is_actionable(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr("material_ai_workbench.desktop_launcher.os.name", "nt")
    monkeypatch.setattr(
        "material_ai_workbench.desktop_launcher.sys.frozen", True, raising=False
    )

    def fail_import(name: str) -> None:
        raise FileNotFoundError("Microsoft.Web.WebView2.Core.dll")

    monkeypatch.setattr(
        "material_ai_workbench.desktop_launcher.importlib.import_module", fail_import
    )

    with pytest.raises(DesktopLaunchError, match="桌面窗口运行库不完整"):
        verify_native_window_runtime()


def test_source_mode_skips_native_window_runtime_probe(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr("material_ai_workbench.desktop_launcher.os.name", "nt")
    monkeypatch.delattr(
        "material_ai_workbench.desktop_launcher.sys.frozen", raising=False
    )

    def fail_import(name: str) -> None:
        raise AssertionError(f"source mode must not import {name}")

    monkeypatch.setattr(
        "material_ai_workbench.desktop_launcher.importlib.import_module", fail_import
    )

    verify_native_window_runtime()
