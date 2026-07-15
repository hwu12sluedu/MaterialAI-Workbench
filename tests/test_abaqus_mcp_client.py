from __future__ import annotations

import json
import socketserver
import threading
from pathlib import Path

from material_ai_workbench.abaqus_mcp_client import (
    AbaqusMcpConfig,
    create_session_snapshot,
    execute_kernel_code,
    ping_bridge,
    request_bridge,
)


class _FakeBridgeHandler(socketserver.BaseRequestHandler):
    def handle(self) -> None:
        data = b""
        while not data.endswith(b"\n"):
            data += self.request.recv(4096)
        payload = json.loads(data.decode("utf-8"))
        method = payload["method"]

        if method == "ping":
            result = {
                "abaqus_version": "fake-2026",
                "models": ["Model-1"],
                "viewports": ["Viewport: 1"],
                "bridge": {"processed": 3},
            }
        elif method == "execute":
            result = {
                "ok": True,
                "return_value": {"value": 42},
                "stdout": "",
                "stderr": "",
            }
        else:
            self.request.sendall(
                json.dumps(
                    {
                        "id": payload["id"],
                        "ok": False,
                        "error": {"message": "unknown method"},
                    }
                ).encode("utf-8")
                + b"\n"
            )
            return

        self.request.sendall(
            json.dumps({"id": payload["id"], "ok": True, "result": result}).encode(
                "utf-8"
            )
            + b"\n"
        )


class _ReusableTcpServer(socketserver.ThreadingTCPServer):
    allow_reuse_address = True
    daemon_threads = True


def _start_fake_bridge() -> tuple[_ReusableTcpServer, AbaqusMcpConfig]:
    server = _ReusableTcpServer(("127.0.0.1", 0), _FakeBridgeHandler)
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    host, port = server.server_address
    return server, AbaqusMcpConfig(host=host, port=port, timeout_seconds=2)


def test_request_bridge_round_trip() -> None:
    server, config = _start_fake_bridge()
    try:
        result = request_bridge("ping", config=config)
    finally:
        server.shutdown()
        server.server_close()

    assert result["abaqus_version"] == "fake-2026"
    assert result["models"] == ["Model-1"]


def test_ping_bridge_status() -> None:
    server, config = _start_fake_bridge()
    try:
        status = ping_bridge(config)
    finally:
        server.shutdown()
        server.server_close()

    assert status.connected is True
    assert "fake-2026" in status.message


def test_execute_kernel_code_returns_execution_payload() -> None:
    server, config = _start_fake_bridge()
    try:
        result = execute_kernel_code("result = {'value': 42}", config)
    finally:
        server.shutdown()
        server.server_close()

    assert result["ok"] is True
    assert result["return_value"]["value"] == 42


def test_session_snapshot_uses_explicit_writable_root(tmp_path: Path) -> None:
    server, config = _start_fake_bridge()
    try:
        snapshot = create_session_snapshot(
            config=config,
            capture_image=False,
            output_root=tmp_path,
        )
    finally:
        server.shutdown()
        server.server_close()

    assert snapshot.snapshot_dir.parent == tmp_path.resolve()
    assert snapshot.summary_path.is_file()
    assert snapshot.report_path.is_file()
    assert "桌面客户端" in snapshot.report_path.read_text(encoding="utf-8")
