"""Abaqus installation, batch runtime and MCP bridge diagnostics.

The diagnostic workflow is deliberately read-only. It records evidence without
opening a model, consuming a solver token or submitting a job.
"""

from __future__ import annotations

import argparse
import json
import os
import subprocess
from dataclasses import asdict, dataclass, field
from datetime import datetime
from pathlib import Path
from typing import Any

from material_ai_workbench.abaqus_mcp_client import (
    AbaqusMcpConfig,
    get_model_info,
    list_jobs,
    ping_bridge,
)
from material_ai_workbench.config import (
    ABAQUS_BAT,
    ABAQUS_SMAPYTHON,
    DIAGNOSTICS_ROOT,
    WORKSPACE_ROOT,
)

CHECK_STATUSES = {"pass", "warn", "fail", "not_run"}


@dataclass
class DiagnosticCheck:
    key: str
    label: str
    status: str
    message: str
    evidence: dict[str, Any] = field(default_factory=dict)

    def __post_init__(self) -> None:
        if self.status not in CHECK_STATUSES:
            raise ValueError(f"Unsupported diagnostic status: {self.status}")


@dataclass
class AbaqusDiagnosticConfig:
    abaqus_bat: Path | str = ABAQUS_BAT
    smapython: Path | str = ABAQUS_SMAPYTHON
    workspace_root: Path | str = WORKSPACE_ROOT
    output_root: Path | str = DIAGNOSTICS_ROOT
    mcp: AbaqusMcpConfig = field(default_factory=AbaqusMcpConfig)
    probe_commands: bool = False
    include_live_context: bool = True
    probe_timeout_seconds: float = 30.0


@dataclass
class AbaqusDiagnosticReport:
    created_at: str
    overall_status: str
    batch_ready: bool
    mcp_ready: bool
    checks: list[DiagnosticCheck]
    next_actions: list[str]
    report_dir: Path
    json_path: Path
    markdown_path: Path

    def to_dict(self) -> dict[str, Any]:
        return {
            "schema_version": "1.0",
            "created_at": self.created_at,
            "overall_status": self.overall_status,
            "batch_ready": self.batch_ready,
            "mcp_ready": self.mcp_ready,
            "checks": [asdict(check) for check in self.checks],
            "next_actions": self.next_actions,
            "artifacts": {
                "report_dir": str(self.report_dir),
                "json": str(self.json_path),
                "markdown": str(self.markdown_path),
            },
        }


def run_abaqus_diagnostics(
    config: AbaqusDiagnosticConfig | None = None,
) -> AbaqusDiagnosticReport:
    """Run read-only diagnostics and persist JSON plus Markdown evidence."""

    cfg = config or AbaqusDiagnosticConfig()
    abaqus_bat = Path(cfg.abaqus_bat).expanduser().resolve()
    smapython = Path(cfg.smapython).expanduser().resolve()
    workspace_root = Path(cfg.workspace_root).expanduser().resolve()
    output_root = Path(cfg.output_root).expanduser().resolve()
    report_dir = _unique_report_dir(output_root)
    json_path = report_dir / "diagnostics.json"
    markdown_path = report_dir / "diagnostics_report.md"

    checks: list[DiagnosticCheck] = []
    checks.append(_check_writable_workspace(workspace_root))
    checks.append(_check_executable("abaqus_bat", "Abaqus 命令", abaqus_bat))
    checks.append(_check_executable("smapython", "Abaqus SMAPython", smapython))

    if cfg.probe_commands and checks[-2].status == "pass":
        checks.append(
            _run_command_probe(
                "abaqus_release_probe",
                "Abaqus 版本探测",
                [str(abaqus_bat), "information=release"],
                cfg.probe_timeout_seconds,
            )
        )
    else:
        checks.append(
            DiagnosticCheck(
                key="abaqus_release_probe",
                label="Abaqus 版本探测",
                status="not_run",
                message="本次未执行命令探测。",
            )
        )

    if cfg.probe_commands and checks[-2].status == "pass":
        checks.append(
            _run_command_probe(
                "smapython_probe",
                "SMAPython 运行时探测",
                [str(smapython), "-c", "import sys; print(sys.version)"],
                cfg.probe_timeout_seconds,
            )
        )
    else:
        checks.append(
            DiagnosticCheck(
                key="smapython_probe",
                label="SMAPython 运行时探测",
                status="not_run",
                message="本次未执行命令探测。",
            )
        )

    mcp_status = ping_bridge(cfg.mcp)
    checks.append(
        DiagnosticCheck(
            key="mcp_bridge",
            label="Abaqus MCP Socket Bridge",
            status="pass" if mcp_status.connected else "warn",
            message=mcp_status.message,
            evidence={
                "endpoint": mcp_status.endpoint,
                "checked_at": mcp_status.checked_at,
                "telemetry": mcp_status.telemetry,
                "error": mcp_status.error,
            },
        )
    )

    if mcp_status.connected and cfg.include_live_context:
        checks.append(_check_live_context(cfg.mcp))
    else:
        checks.append(
            DiagnosticCheck(
                key="live_context",
                label="当前 Abaqus 模型与 Job 上下文",
                status="not_run",
                message=(
                    "本次未请求读取当前 CAE 上下文。"
                    if mcp_status.connected
                    else "读取当前 CAE 上下文需要先连接 MCP Bridge。"
                ),
            )
        )

    workspace_ok = _status(checks, "workspace_writable") == "pass"
    abaqus_ok = _status(checks, "abaqus_bat") == "pass"
    smapython_ok = _status(checks, "smapython") == "pass"
    probe_ok = all(
        _status(checks, key) != "fail"
        for key in ("abaqus_release_probe", "smapython_probe")
    )
    batch_ready = workspace_ok and abaqus_ok and smapython_ok and probe_ok
    mcp_ready = mcp_status.connected and (
        not cfg.include_live_context or _status(checks, "live_context") == "pass"
    )
    if not workspace_ok:
        overall_status = "blocked"
    elif batch_ready and mcp_ready:
        overall_status = "ready"
    elif batch_ready or mcp_ready:
        overall_status = "partial"
    else:
        overall_status = "blocked"

    next_actions = _next_actions(checks, cfg)
    report = AbaqusDiagnosticReport(
        created_at=datetime.now().isoformat(timespec="seconds"),
        overall_status=overall_status,
        batch_ready=batch_ready,
        mcp_ready=mcp_ready,
        checks=checks,
        next_actions=next_actions,
        report_dir=report_dir,
        json_path=json_path,
        markdown_path=markdown_path,
    )
    payload = report.to_dict()
    json_path.write_text(
        json.dumps(payload, indent=2, ensure_ascii=False), encoding="utf-8"
    )
    markdown_path.write_text(_markdown_report(payload), encoding="utf-8")
    return report


def _check_writable_workspace(path: Path) -> DiagnosticCheck:
    marker = path / ".materialai_write_test"
    try:
        path.mkdir(parents=True, exist_ok=True)
        marker.write_text("ok", encoding="ascii")
        marker.unlink()
    except OSError as exc:
        return DiagnosticCheck(
            key="workspace_writable",
            label="可写工作区",
            status="fail",
            message="配置的工作区不可写。",
            evidence={"path": str(path), "error": str(exc)},
        )
    return DiagnosticCheck(
        key="workspace_writable",
        label="可写工作区",
        status="pass",
        message="配置的工作区可正常写入。",
        evidence={"path": str(path)},
    )


def _check_executable(key: str, label: str, path: Path) -> DiagnosticCheck:
    exists = path.is_file()
    return DiagnosticCheck(
        key=key,
        label=label,
        status="pass" if exists else "fail",
        message="执行文件路径存在。" if exists else "执行文件路径不存在。",
        evidence={"path": str(path)},
    )


def _run_command_probe(
    key: str,
    label: str,
    command: list[str],
    timeout_seconds: float,
) -> DiagnosticCheck:
    env = os.environ.copy()
    env.setdefault("PYTHONIOENCODING", "utf-8")
    try:
        completed = subprocess.run(
            command,
            capture_output=True,
            text=True,
            timeout=max(1.0, float(timeout_seconds)),
            env=env,
        )
    except subprocess.TimeoutExpired as exc:
        return DiagnosticCheck(
            key=key,
            label=label,
            status="fail",
            message=f"命令探测在 {timeout_seconds:g} 秒后超时。",
            evidence={"command": command, "error": str(exc)},
        )
    except OSError as exc:
        return DiagnosticCheck(
            key=key,
            label=label,
            status="fail",
            message="命令探测无法启动。",
            evidence={"command": command, "error": str(exc)},
        )

    status = "pass" if completed.returncode == 0 else "fail"
    return DiagnosticCheck(
        key=key,
        label=label,
        status=status,
        message=(
            "命令探测完成。"
            if status == "pass"
            else f"命令探测返回码为 {completed.returncode}。"
        ),
        evidence={
            "command": command,
            "returncode": completed.returncode,
            "stdout_tail": (completed.stdout or "")[-4000:],
            "stderr_tail": (completed.stderr or "")[-4000:],
        },
    )


def _check_live_context(config: AbaqusMcpConfig) -> DiagnosticCheck:
    try:
        model_info = get_model_info(config)
        jobs = list_jobs(config)
    except Exception as exc:
        return DiagnosticCheck(
            key="live_context",
            label="当前 Abaqus 模型与 Job 上下文",
            status="warn",
            message="Bridge 心跳已连接，但读取当前模型与 Job 失败。",
            evidence={"error": str(exc)},
        )

    models = list((model_info.get("models") or {}).keys())
    return DiagnosticCheck(
        key="live_context",
        label="当前 Abaqus 模型与 Job 上下文",
        status="pass",
        message=f"已读取 {len(models)} 个模型和 {len(jobs)} 个 Job。",
        evidence={
            "models": models,
            "jobs": [item.get("name") for item in jobs],
            "current_viewport": model_info.get("current_viewport"),
        },
    )


def _status(checks: list[DiagnosticCheck], key: str) -> str:
    for check in checks:
        if check.key == key:
            return check.status
    return "not_run"


def _next_actions(
    checks: list[DiagnosticCheck], config: AbaqusDiagnosticConfig
) -> list[str]:
    actions: list[str] = []
    if _status(checks, "workspace_writable") == "fail":
        actions.append("将 MATERIALAI_WORKSPACE_ROOT 修改为可写目录。")
    if _status(checks, "abaqus_bat") == "fail":
        actions.append("将 MATERIALAI_ABAQUS_BAT 设置为本机 abaqus.bat 的完整路径。")
    if _status(checks, "smapython") == "fail":
        actions.append(
            "将 MATERIALAI_ABAQUS_SMAPYTHON 设置为本机 SMAPython.exe 的完整路径。"
        )
    if _status(checks, "mcp_bridge") != "pass":
        actions.append(
            "打开 Abaqus/CAE，执行 Plug-ins > Abaqus MCP > Start Socket Bridge，"
            f"并确认端点为 {config.mcp.host}:{config.mcp.port}。"
        )
    elif config.include_live_context and _status(checks, "live_context") != "pass":
        actions.append(
            "MCP 心跳正常但内核执行不可用。请更新或重载 Abaqus MCP 插件，然后重新读取 CAE 上下文。"
        )
    if not config.probe_commands and _status(checks, "abaqus_bat") == "pass":
        actions.append("第一次真实 Abaqus 验收求解前，建议执行版本探测。")
    return actions or ["当前无阻断项。"]


def _unique_report_dir(root: Path) -> Path:
    root.mkdir(parents=True, exist_ok=True)
    stem = datetime.now().strftime("%Y%m%d_%H%M%S_%f")[:-3] + "_abaqus_diagnostics"
    candidate = root / stem
    index = 2
    while candidate.exists():
        candidate = root / f"{stem}_{index}"
        index += 1
    candidate.mkdir(parents=True, exist_ok=False)
    return candidate


def _markdown_report(payload: dict[str, Any]) -> str:
    rows = []
    for check in payload["checks"]:
        rows.append(
            f"| `{check['key']}` | {check['label']} | `{check['status']}` | {check['message']} |"
        )
    action_lines = "\n".join(
        f"{index}. {item}" for index, item in enumerate(payload["next_actions"], 1)
    )
    return f"""# Abaqus 环境诊断报告

- 生成时间：`{payload['created_at']}`
- 总体状态：`{payload['overall_status']}`
- Abaqus 批处理可用：`{payload['batch_ready']}`
- Abaqus MCP 实时连接可用：`{payload['mcp_ready']}`

## 检查结果

| ID | 检查项 | 状态 | 结论 |
|---|---|---|---|
{chr(10).join(rows)}

## 后续动作

{action_lines}

## 说明

该诊断只读取路径、运行时版本和 MCP 状态，不打开模型、不提交 Job，也不声称生成了求解结果。
完整证据见同目录下的 `diagnostics.json`。
"""


def _console_json(payload: dict[str, Any]) -> str:
    """Render machine-readable JSON that survives Windows GBK parent consoles."""

    return json.dumps(payload, indent=2, ensure_ascii=True)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Run read-only Abaqus diagnostics.")
    parser.add_argument("--abaqus-bat", default=str(ABAQUS_BAT))
    parser.add_argument("--smapython", default=str(ABAQUS_SMAPYTHON))
    parser.add_argument("--workspace-root", default=str(WORKSPACE_ROOT))
    parser.add_argument("--output-root", default=str(DIAGNOSTICS_ROOT))
    parser.add_argument("--host", default=AbaqusMcpConfig().host)
    parser.add_argument("--port", type=int, default=AbaqusMcpConfig().port)
    parser.add_argument(
        "--timeout", type=float, default=AbaqusMcpConfig().timeout_seconds
    )
    parser.add_argument("--probe-commands", action="store_true")
    parser.add_argument("--no-live-context", action="store_true")
    args = parser.parse_args(argv)

    report = run_abaqus_diagnostics(
        AbaqusDiagnosticConfig(
            abaqus_bat=args.abaqus_bat,
            smapython=args.smapython,
            workspace_root=args.workspace_root,
            output_root=args.output_root,
            mcp=AbaqusMcpConfig(
                host=args.host, port=args.port, timeout_seconds=args.timeout
            ),
            probe_commands=args.probe_commands,
            include_live_context=not args.no_live_context,
        )
    )
    print(_console_json(report.to_dict()))
    return 2 if report.overall_status == "blocked" else 0


if __name__ == "__main__":
    raise SystemExit(main())
