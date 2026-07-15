from __future__ import annotations

import json
from pathlib import Path

from jsonschema import Draft202012Validator

import material_ai_workbench.abaqus_diagnostics as diagnostics
from material_ai_workbench.abaqus_diagnostics import (
    AbaqusDiagnosticConfig,
    run_abaqus_diagnostics,
)
from material_ai_workbench.abaqus_mcp_client import AbaqusMcpConfig, AbaqusMcpStatus


def _status(connected: bool) -> AbaqusMcpStatus:
    return AbaqusMcpStatus(
        connected=connected,
        endpoint="127.0.0.1:48152",
        checked_at="2026-07-15T12:00:00",
        message="connected" if connected else "disconnected",
        telemetry={"models": ["Model-1"]} if connected else None,
        error=None if connected else "connection refused",
    )


def test_diagnostics_separates_batch_and_mcp_readiness(
    tmp_path: Path, monkeypatch
) -> None:
    abaqus_bat = tmp_path / "abaqus.bat"
    smapython = tmp_path / "SMAPython.exe"
    abaqus_bat.write_text("stub", encoding="ascii")
    smapython.write_text("stub", encoding="ascii")
    monkeypatch.setattr(diagnostics, "ping_bridge", lambda _config: _status(False))

    report = run_abaqus_diagnostics(
        AbaqusDiagnosticConfig(
            abaqus_bat=abaqus_bat,
            smapython=smapython,
            workspace_root=tmp_path / "workspace",
            output_root=tmp_path / "diagnostics",
            mcp=AbaqusMcpConfig(timeout_seconds=0.1),
            include_live_context=False,
        )
    )

    assert report.overall_status == "partial"
    assert report.batch_ready is True
    assert report.mcp_ready is False
    assert report.json_path.is_file()
    assert report.markdown_path.is_file()
    payload = json.loads(report.json_path.read_text(encoding="utf-8"))
    schema = json.loads(
        Path("schemas/diagnostics.schema.json").read_text(encoding="utf-8")
    )
    Draft202012Validator(schema).validate(payload)
    assert payload["schema_version"] == "1.0"
    assert any(
        item["key"] == "mcp_bridge" and item["status"] == "warn"
        for item in payload["checks"]
    )


def test_diagnostics_is_blocked_when_batch_paths_and_mcp_are_unavailable(
    tmp_path: Path, monkeypatch
) -> None:
    monkeypatch.setattr(diagnostics, "ping_bridge", lambda _config: _status(False))
    report = run_abaqus_diagnostics(
        AbaqusDiagnosticConfig(
            abaqus_bat=tmp_path / "missing-abaqus.bat",
            smapython=tmp_path / "missing-SMAPython.exe",
            workspace_root=tmp_path / "workspace",
            output_root=tmp_path / "diagnostics",
            include_live_context=False,
        )
    )

    assert report.overall_status == "blocked"
    assert report.batch_ready is False
    assert report.mcp_ready is False
    assert any("MATERIALAI_ABAQUS_BAT" in item for item in report.next_actions)


def test_live_context_is_recorded_when_bridge_is_connected(
    tmp_path: Path, monkeypatch
) -> None:
    abaqus_bat = tmp_path / "abaqus.bat"
    smapython = tmp_path / "SMAPython.exe"
    abaqus_bat.write_text("stub", encoding="ascii")
    smapython.write_text("stub", encoding="ascii")
    monkeypatch.setattr(diagnostics, "ping_bridge", lambda _config: _status(True))
    monkeypatch.setattr(
        diagnostics,
        "get_model_info",
        lambda _config: {
            "models": {"Acceptance": {}},
            "current_viewport": "Viewport: 1",
        },
    )
    monkeypatch.setattr(
        diagnostics, "list_jobs", lambda _config: [{"name": "plate_job"}]
    )

    report = run_abaqus_diagnostics(
        AbaqusDiagnosticConfig(
            abaqus_bat=abaqus_bat,
            smapython=smapython,
            workspace_root=tmp_path / "workspace",
            output_root=tmp_path / "diagnostics",
            include_live_context=True,
        )
    )

    check = next(item for item in report.checks if item.key == "live_context")
    assert report.overall_status == "ready"
    assert check.status == "pass"
    assert check.evidence["models"] == ["Acceptance"]
    assert check.evidence["jobs"] == ["plate_job"]


def test_ping_only_does_not_claim_mcp_execution_readiness(
    tmp_path: Path, monkeypatch
) -> None:
    abaqus_bat = tmp_path / "abaqus.bat"
    smapython = tmp_path / "SMAPython.exe"
    abaqus_bat.write_text("stub", encoding="ascii")
    smapython.write_text("stub", encoding="ascii")
    monkeypatch.setattr(diagnostics, "ping_bridge", lambda _config: _status(True))
    monkeypatch.setattr(
        diagnostics,
        "get_model_info",
        lambda _config: (_ for _ in ()).throw(
            ValueError("params.code must be a non-empty string")
        ),
    )

    report = run_abaqus_diagnostics(
        AbaqusDiagnosticConfig(
            abaqus_bat=abaqus_bat,
            smapython=smapython,
            workspace_root=tmp_path / "workspace",
            output_root=tmp_path / "diagnostics",
            include_live_context=True,
        )
    )

    assert report.overall_status == "partial"
    assert report.batch_ready is True
    assert report.mcp_ready is False
    assert any("内核执行" in item for item in report.next_actions)


def test_console_json_is_safe_for_windows_gbk_parent_process() -> None:
    rendered = diagnostics._console_json({"message": "Abaqus 版本探测 \ufffd"})

    assert rendered.encode("ascii")
    assert "\\ufffd" in rendered
