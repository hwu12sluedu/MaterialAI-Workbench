"""Windows desktop launcher for MaterialAI Workbench.

The desktop process owns a private Streamlit backend, waits for it to become
healthy, and then opens the UI in a native pywebview window. Runtime data is
stored below the current user's local application-data directory.
"""

from __future__ import annotations

import argparse
import ctypes
import importlib
import logging
import os
import socket
import subprocess
import sys
import tempfile
import time
import urllib.error
import urllib.request
import webbrowser
from dataclasses import dataclass
from logging.handlers import RotatingFileHandler
from pathlib import Path
from typing import Sequence

APP_NAME = "MaterialAI Workbench"
APP_DIRECTORY = "MaterialAIWorkbench"
HEALTH_PATH = "/_stcore/health"
DEFAULT_STARTUP_TIMEOUT = 120.0
LOGGER = logging.getLogger("materialai.desktop")


class DesktopLaunchError(RuntimeError):
    """Raised when the desktop client cannot start safely."""


class DesktopAlreadyRunning(DesktopLaunchError):
    """Raised when another desktop client instance already owns the mutex."""


@dataclass(frozen=True)
class DesktopPaths:
    """Writable per-user paths used by the packaged desktop client."""

    root: Path
    workspace: Path
    config: Path
    logs: Path
    env_file: Path
    desktop_log: Path
    server_log: Path


def default_app_root() -> Path:
    """Return the per-user application-data directory."""
    local_app_data = os.environ.get("LOCALAPPDATA", "").strip()
    base = Path(local_app_data) if local_app_data else Path.home() / "AppData" / "Local"
    return base / APP_DIRECTORY


def configure_desktop_environment(app_root: Path | None = None) -> DesktopPaths:
    """Create writable folders and expose them to the workbench backend."""
    root = (app_root or default_app_root()).expanduser().resolve()
    workspace = root / "workspace"
    config = root / "config"
    logs = root / "logs"
    for path in (root, workspace, config, logs):
        path.mkdir(parents=True, exist_ok=True)

    paths = DesktopPaths(
        root=root,
        workspace=workspace,
        config=config,
        logs=logs,
        env_file=config / ".env",
        desktop_log=logs / "desktop.log",
        server_log=logs / "streamlit.log",
    )
    os.environ.setdefault("MATERIALAI_WORKSPACE_ROOT", str(paths.workspace))
    os.environ.setdefault("MATERIALAI_ENV_FILE", str(paths.env_file))
    os.environ.setdefault("MATERIALAI_DESKTOP_LOG_DIR", str(paths.logs))
    os.environ.setdefault("STREAMLIT_BROWSER_GATHER_USAGE_STATS", "false")
    os.environ.setdefault("STREAMLIT_SERVER_HEADLESS", "true")
    return paths


def configure_logging(paths: DesktopPaths, *, debug: bool = False) -> None:
    """Configure a rotating log that remains available after GUI failures."""
    LOGGER.setLevel(logging.DEBUG if debug else logging.INFO)
    if any(isinstance(handler, RotatingFileHandler) for handler in LOGGER.handlers):
        return
    handler = RotatingFileHandler(
        paths.desktop_log,
        maxBytes=2 * 1024 * 1024,
        backupCount=3,
        encoding="utf-8",
    )
    handler.setFormatter(logging.Formatter("%(asctime)s %(levelname)s %(message)s"))
    LOGGER.addHandler(handler)
    LOGGER.propagate = False


def find_available_port(requested_port: int | None = None) -> int:
    """Reserve-check a loopback port and return it for the backend process."""
    port = int(requested_port or 0)
    if not 0 <= port <= 65535:
        raise DesktopLaunchError(f"端口超出有效范围：{port}")
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as probe:
        probe.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        try:
            probe.bind(("127.0.0.1", port))
        except OSError as exc:
            raise DesktopLaunchError(
                f"端口 {port} 已被占用，请关闭占用程序或换一个端口。"
            ) from exc
        return int(probe.getsockname()[1])


def streamlit_app_path() -> Path:
    """Locate the Streamlit entry file in source and frozen builds."""
    path = Path(__file__).resolve().with_name("streamlit_app.py")
    if not path.exists():
        raise DesktopLaunchError(f"客户端资源不完整，缺少：{path.name}")
    return path


def backend_command(port: int, *, debug: bool = False) -> list[str]:
    """Build the child command for source and PyInstaller execution."""
    arguments = ["--serve", "--port", str(port)]
    if debug:
        arguments.append("--debug")
    if getattr(sys, "frozen", False):
        return [sys.executable, *arguments]
    return [sys.executable, "-m", "material_ai_workbench.desktop_launcher", *arguments]


def run_streamlit_server(port: int, *, debug: bool = False) -> int:
    """Run the private Streamlit backend in the current process."""
    from streamlit.web import cli as streamlit_cli

    app_path = streamlit_app_path()
    sys.argv = [
        "streamlit",
        "run",
        str(app_path),
        "--global.developmentMode=false",
        f"--server.port={port}",
        "--server.address=127.0.0.1",
        "--server.headless=true",
        "--server.fileWatcherType=none",
        "--server.runOnSave=false",
        "--browser.gatherUsageStats=false",
        "--client.toolbarMode=minimal",
        (
            "--client.showErrorDetails=none"
            if not debug
            else "--client.showErrorDetails=full"
        ),
    ]
    result = streamlit_cli.main()
    return int(result or 0)


def start_backend(
    port: int,
    paths: DesktopPaths,
    *,
    debug: bool = False,
) -> tuple[subprocess.Popen[bytes], object]:
    """Start the backend without displaying a second console window."""
    command = backend_command(port, debug=debug)
    log_handle = paths.server_log.open("ab", buffering=0)
    creation_flags = 0
    if os.name == "nt" and not debug:
        creation_flags |= int(getattr(subprocess, "CREATE_NO_WINDOW", 0))
    LOGGER.info("Starting backend on port %s", port)
    try:
        process = subprocess.Popen(
            command,
            cwd=paths.root,
            env=os.environ.copy(),
            stdin=subprocess.DEVNULL,
            stdout=log_handle,
            stderr=subprocess.STDOUT,
            creationflags=creation_flags,
        )
    except Exception:
        log_handle.close()
        raise
    return process, log_handle


def wait_for_backend(
    process: subprocess.Popen[bytes],
    port: int,
    *,
    timeout_seconds: float = DEFAULT_STARTUP_TIMEOUT,
) -> str:
    """Wait until Streamlit reports healthy or fail with actionable context."""
    url = f"http://127.0.0.1:{port}"
    health_url = url + HEALTH_PATH
    deadline = time.monotonic() + max(1.0, float(timeout_seconds))
    last_error = ""
    while time.monotonic() < deadline:
        return_code = process.poll()
        if return_code is not None:
            raise DesktopLaunchError(f"本地服务提前退出，退出码 {return_code}。")
        try:
            request = urllib.request.Request(
                health_url, headers={"User-Agent": APP_NAME}
            )
            with urllib.request.urlopen(request, timeout=1.5) as response:
                if 200 <= int(response.status) < 300:
                    LOGGER.info("Backend is healthy at %s", url)
                    return url
        except (OSError, urllib.error.URLError) as exc:
            last_error = str(exc)
        time.sleep(0.25)
    detail = f"，最后错误：{last_error}" if last_error else ""
    raise DesktopLaunchError(f"本地服务在 {timeout_seconds:.0f} 秒内没有就绪{detail}")


def stop_backend(process: subprocess.Popen[bytes] | None) -> None:
    """Stop the owned backend and prevent orphaned localhost servers."""
    if process is None or process.poll() is not None:
        return
    LOGGER.info("Stopping backend process %s", process.pid)
    process.terminate()
    try:
        process.wait(timeout=8)
    except subprocess.TimeoutExpired:
        LOGGER.warning("Backend did not terminate in time; killing it")
        process.kill()
        process.wait(timeout=5)


def log_tail(path: Path, *, max_lines: int = 24) -> str:
    """Return the end of a UTF-8 log without failing the error dialog."""
    try:
        lines = path.read_text(encoding="utf-8", errors="replace").splitlines()
    except OSError:
        return ""
    return "\n".join(lines[-max_lines:])


def run_core_self_check(paths: DesktopPaths) -> None:
    """Exercise the packaged numerical stack with a small material-training run."""
    verify_native_window_runtime()
    from material_ai_workbench.pipeline import WorkbenchConfig, run_material_workbench

    LOGGER.info("Starting packaged J2 material-training self-check")
    with tempfile.TemporaryDirectory(prefix="self-check-", dir=paths.root) as temp_dir:
        result = run_material_workbench(
            WorkbenchConfig(
                material_type="j2",
                name="desktop_self_check",
                output_dir=Path(temp_dir),
                n_load_cases=10,
                n_sequence=2,
                calculate_curves=False,
                test_size=20,
                plot_mesh=12,
                random_seed=7,
            )
        )
        required_outputs = (
            result.summary_path,
            result.report_path,
            result.umat_csv,
            result.umat_meta_json,
        )
        if result.support_vectors <= 0 or not all(
            path.is_file() for path in required_outputs
        ):
            raise DesktopLaunchError("材料训练自检没有生成完整结果。")
    LOGGER.info("Packaged J2 material-training self-check passed")


def verify_native_window_runtime() -> None:
    """Load the Windows pywebview backend and its bundled WebView2 assemblies."""

    if os.name != "nt" or not getattr(sys, "frozen", False):
        return
    try:
        importlib.import_module("webview.platforms.winforms")
    except Exception as exc:
        raise DesktopLaunchError(
            "桌面窗口运行库不完整，请重新下载并完整解压客户端。"
        ) from exc
    LOGGER.info("Native WebView runtime self-check passed")


class SingleInstanceGuard:
    """Windows named-mutex guard; a no-op on other platforms."""

    def __init__(self) -> None:
        self._handle: int | None = None

    def __enter__(self) -> "SingleInstanceGuard":
        if os.name != "nt":
            return self
        kernel32 = ctypes.windll.kernel32
        handle = kernel32.CreateMutexW(None, False, f"Local\\{APP_DIRECTORY}.Desktop")
        if not handle:
            raise DesktopLaunchError("无法创建客户端进程锁。")
        self._handle = int(handle)
        if int(kernel32.GetLastError()) == 183:
            kernel32.CloseHandle(handle)
            self._handle = None
            raise DesktopAlreadyRunning("MaterialAI Workbench 已经在运行。")
        return self

    def __exit__(self, exc_type: object, exc: object, traceback: object) -> None:
        if self._handle is not None and os.name == "nt":
            ctypes.windll.kernel32.CloseHandle(self._handle)
            self._handle = None


def open_native_window(url: str, *, debug: bool = False) -> None:
    """Open the workbench URL in a native Windows webview window."""
    try:
        import webview
    except Exception as exc:
        raise DesktopLaunchError(
            "桌面窗口组件加载失败，请查看日志或重新下载完整客户端。"
        ) from exc

    webview.create_window(
        APP_NAME,
        url=url,
        width=1440,
        height=900,
        min_size=(1024, 700),
        background_color="#f4f6f8",
    )
    webview.start(debug=debug)


def run_browser_mode(url: str, process: subprocess.Popen[bytes]) -> None:
    """Open the app in the default browser for development diagnostics."""
    if not webbrowser.open(url):
        raise DesktopLaunchError(f"无法自动打开浏览器，请手动访问 {url}")
    LOGGER.info("Browser mode opened at %s", url)
    try:
        while process.poll() is None:
            time.sleep(0.5)
    except KeyboardInterrupt:
        return


def show_message(title: str, message: str, *, error: bool = False) -> None:
    """Show a native message box when no console is available."""
    if os.name == "nt":
        flags = 0x10 if error else 0x40
        ctypes.windll.user32.MessageBoxW(None, str(message), str(title), flags)
    else:
        stream = sys.stderr if error else sys.stdout
        print(f"{title}: {message}", file=stream)


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="MaterialAI Workbench Windows desktop client"
    )
    parser.add_argument(
        "--port", type=int, default=None, help="use a specific localhost port"
    )
    parser.add_argument(
        "--browser",
        action="store_true",
        help="open in the default browser instead of a native window",
    )
    parser.add_argument(
        "--debug",
        action="store_true",
        help="enable verbose desktop and Streamlit diagnostics",
    )
    parser.add_argument(
        "--smoke-test",
        action="store_true",
        help="check material training and backend health, then exit",
    )
    parser.add_argument(
        "--startup-timeout",
        type=float,
        default=DEFAULT_STARTUP_TIMEOUT,
        help="seconds to wait for the local backend",
    )
    parser.add_argument("--serve", action="store_true", help=argparse.SUPPRESS)
    return parser


def main(argv: Sequence[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    paths = configure_desktop_environment()
    configure_logging(paths, debug=bool(args.debug))

    if args.serve:
        if args.port is None:
            raise SystemExit("--serve requires --port")
        return run_streamlit_server(int(args.port), debug=bool(args.debug))

    process: subprocess.Popen[bytes] | None = None
    server_log_handle: object | None = None
    try:
        with SingleInstanceGuard():
            port = find_available_port(args.port)
            process, server_log_handle = start_backend(
                port, paths, debug=bool(args.debug)
            )
            url = wait_for_backend(
                process, port, timeout_seconds=float(args.startup_timeout)
            )
            if args.smoke_test:
                run_core_self_check(paths)
                LOGGER.info("Desktop smoke test passed")
                return 0
            if args.browser:
                run_browser_mode(url, process)
            else:
                open_native_window(url, debug=bool(args.debug))
            return 0
    except DesktopAlreadyRunning as exc:
        LOGGER.info(str(exc))
        if args.smoke_test:
            print(str(exc), file=sys.stderr)
        else:
            show_message(APP_NAME, str(exc), error=False)
        return 2
    except Exception as exc:
        LOGGER.exception("Desktop startup failed")
        tail = log_tail(paths.server_log)
        details = f"\n\n服务日志：\n{tail}" if tail else ""
        message = f"客户端启动失败：{exc}\n\n日志位置：{paths.logs}{details}"
        if args.smoke_test:
            print(message, file=sys.stderr)
        else:
            show_message(APP_NAME, message, error=True)
        return 1
    finally:
        stop_backend(process)
        if server_log_handle is not None:
            try:
                server_log_handle.close()  # type: ignore[attr-defined]
            except OSError:
                pass


if __name__ == "__main__":
    raise SystemExit(main())
