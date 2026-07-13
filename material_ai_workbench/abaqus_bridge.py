"""Prepare and optionally run Abaqus UMAT verification for a Workbench run."""

from __future__ import annotations

import argparse
import csv
import json
import os
import re
import shutil
import stat
import subprocess
from dataclasses import asdict, dataclass
from datetime import datetime
from pathlib import Path
from typing import Any

from material_ai_workbench.config import ABAQUS_BAT as DEFAULT_ABAQUS_BAT


PACKAGE_ROOT = Path(__file__).resolve().parent
REPO_ROOT = PACKAGE_ROOT.parent
_SOURCE_UMAT_TEMPLATE_DIR = REPO_ROOT / "examples" / "UMAT"
_PACKAGED_UMAT_TEMPLATE_DIR = PACKAGE_ROOT / "resources" / "umat"
UMAT_TEMPLATE_DIR = (
    _SOURCE_UMAT_TEMPLATE_DIR
    if _SOURCE_UMAT_TEMPLATE_DIR.exists()
    else _PACKAGED_UMAT_TEMPLATE_DIR
)


@dataclass
class AbaqusBridgeConfig:
    run_dir: Path
    output_dir: Path | None = None
    material_name: str | None = None
    abaqus_bat: Path = DEFAULT_ABAQUS_BAT
    max_load_cases: int = 1
    run: bool = False
    timeout_seconds: int = 1800


@dataclass
class AbaqusBridgeResult:
    work_dir: Path
    material_name: str
    prepared: bool
    ran: bool
    return_code: int | None
    log_path: Path | None
    result_csv: Path | None
    result_meta_json: Path | None
    summary_path: Path
    status: str


def prepare_abaqus_verification(config: AbaqusBridgeConfig) -> AbaqusBridgeResult:
    run_dir = config.run_dir.resolve()
    summary = _load_summary(run_dir)
    material_name = config.material_name or summary["ml_material"]["name"]
    work_dir = (config.output_dir or (run_dir / "abaqus_verification")).resolve()

    if work_dir.exists():
        shutil.rmtree(work_dir, onerror=_remove_readonly)
    (work_dir / "models").mkdir(parents=True)
    (work_dir / "results").mkdir()
    (work_dir / "logs").mkdir()

    for filename in ("femBlock.inp", "ml_umat.f"):
        try:
            shutil.copy2(UMAT_TEMPLATE_DIR / filename, work_dir / filename)
        except FileNotFoundError as exc:
            raise FileNotFoundError(f"Required Abaqus template file is missing: {UMAT_TEMPLATE_DIR / filename}") from exc

    calc_text = (UMAT_TEMPLATE_DIR / "calc_properties.py").read_text(encoding="utf-8")
    calc_text = _patch_calc_properties(calc_text)
    (work_dir / "calc_properties.py").write_text(calc_text, encoding="utf-8")

    model_csv, model_meta = _find_model_files(run_dir, summary, material_name)
    try:
        shutil.copy2(model_csv, work_dir / "models" / f"abq_{material_name}-svm.csv")
        shutil.copy2(model_meta, work_dir / "models" / f"abq_{material_name}-svm_meta.json")
    except FileNotFoundError as exc:
        raise FileNotFoundError(f"Required exported model file is missing: {exc.filename}") from exc

    _write_run_script(work_dir, config, material_name)
    summary_path = work_dir / "bridge_summary.json"
    bridge_summary = _base_summary(config, work_dir, material_name)
    bridge_summary["status"] = "prepared"
    summary_path.write_text(json.dumps(bridge_summary, indent=2), encoding="utf-8")
    _write_markdown_report(work_dir, bridge_summary)

    return AbaqusBridgeResult(
        work_dir=work_dir,
        material_name=material_name,
        prepared=True,
        ran=False,
        return_code=None,
        log_path=None,
        result_csv=None,
        result_meta_json=None,
        summary_path=summary_path,
        status="prepared",
    )


def run_abaqus_verification(config: AbaqusBridgeConfig) -> AbaqusBridgeResult:
    prepared = prepare_abaqus_verification(config)
    work_dir = prepared.work_dir
    log_path = work_dir / "logs" / "abaqus_python.log"
    command = [
        str(config.abaqus_bat),
        "python",
        "calc_properties.py",
        prepared.material_name,
    ]
    env = None
    if config.abaqus_bat:
        env = os.environ.copy()
        env["MATERIAL_AI_ABAQUS_CMD"] = str(config.abaqus_bat)
        env["MATERIAL_AI_MAX_LOAD_CASES"] = str(config.max_load_cases)

    try:
        completed = subprocess.run(
            command,
            cwd=work_dir,
            env=env,
            stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT,
            text=True,
            timeout=config.timeout_seconds,
            check=False,
        )
        return_code = completed.returncode
        log_text = completed.stdout or ""
        status = "completed" if return_code == 0 else "failed"
    except subprocess.TimeoutExpired as exc:
        return_code = None
        timeout_stdout = exc.stdout.decode("utf-8", errors="replace") if isinstance(exc.stdout, bytes) else (exc.stdout or "")
        log_text = timeout_stdout + "\nTIMEOUT: Abaqus verification exceeded timeout.\n"
        status = "timeout"

    log_path.write_text(log_text, encoding="utf-8", errors="replace")
    result_csv = work_dir / "results" / f"abq_{prepared.material_name}-res.csv"
    result_meta_json = work_dir / "results" / f"abq_{prepared.material_name}-res_meta.json"
    if status == "completed" and not result_csv.exists():
        status = "completed_no_result_csv"
    result_stats = None
    result_plot_png = None
    if result_csv.exists():
        result_stats, result_plot_png = _postprocess_result_csv(result_csv, work_dir)

    bridge_summary = _base_summary(config, work_dir, prepared.material_name)
    bridge_summary.update(
        {
            "status": status,
            "return_code": return_code,
            "log_path": str(log_path),
            "result_csv": str(result_csv) if result_csv.exists() else None,
            "result_meta_json": str(result_meta_json) if result_meta_json.exists() else None,
            "result_plot_png": str(result_plot_png) if result_plot_png else None,
            "result_stats": result_stats,
        }
    )
    summary_path = work_dir / "bridge_summary.json"
    summary_path.write_text(json.dumps(bridge_summary, indent=2), encoding="utf-8")
    _write_markdown_report(work_dir, bridge_summary)

    return AbaqusBridgeResult(
        work_dir=work_dir,
        material_name=prepared.material_name,
        prepared=True,
        ran=True,
        return_code=return_code,
        log_path=log_path,
        result_csv=result_csv if result_csv.exists() else None,
        result_meta_json=result_meta_json if result_meta_json.exists() else None,
        summary_path=summary_path,
        status=status,
    )


def main() -> None:
    args = _parse_args()
    config = AbaqusBridgeConfig(
        run_dir=args.run_dir,
        output_dir=args.output_dir,
        material_name=args.material_name,
        abaqus_bat=args.abaqus_bat,
        max_load_cases=args.max_load_cases,
        run=args.run,
        timeout_seconds=args.timeout_seconds,
    )
    result = run_abaqus_verification(config) if args.run else prepare_abaqus_verification(config)
    print("Abaqus bridge finished.")
    print(f"Status: {result.status}")
    print(f"Work folder: {result.work_dir}")
    print(f"Summary: {result.summary_path}")
    if result.log_path:
        print(f"Log: {result.log_path}")
    if result.result_csv:
        print(f"Result CSV: {result.result_csv}")


def _parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Prepare and optionally run Abaqus UMAT verification for a MaterialAI run."
    )
    parser.add_argument("--run-dir", type=Path, required=True)
    parser.add_argument("--output-dir", type=Path, default=None)
    parser.add_argument("--material-name", default=None)
    parser.add_argument("--abaqus-bat", type=Path, default=DEFAULT_ABAQUS_BAT)
    parser.add_argument("--max-load-cases", type=int, default=1)
    parser.add_argument("--timeout-seconds", type=int, default=1800)
    parser.add_argument("--run", action="store_true")
    return parser.parse_args()


def _load_summary(run_dir: Path) -> dict[str, Any]:
    summary_path = run_dir / "summary.json"
    if not summary_path.exists():
        raise FileNotFoundError(f"summary.json not found in {run_dir}")
    return json.loads(summary_path.read_text(encoding="utf-8"))


def _find_model_files(
    run_dir: Path,
    summary: dict[str, Any],
    material_name: str,
) -> tuple[Path, Path]:
    outputs = summary.get("outputs", {})
    csv_path = Path(outputs.get("umat_csv", ""))
    meta_path = Path(outputs.get("umat_meta_json", ""))
    if not csv_path.is_absolute():
        csv_path = REPO_ROOT / csv_path
    if not meta_path.is_absolute():
        meta_path = REPO_ROOT / meta_path
    fallback_csv = run_dir / "models" / f"abq_{material_name}-svm.csv"
    fallback_meta = run_dir / "models" / f"abq_{material_name}-svm_meta.json"
    if not csv_path.exists():
        csv_path = fallback_csv
    if not meta_path.exists():
        meta_path = fallback_meta
    if not csv_path.exists():
        raise FileNotFoundError(f"UMAT CSV not found: {csv_path}")
    if not meta_path.exists():
        raise FileNotFoundError(f"UMAT meta JSON not found: {meta_path}")
    return csv_path, meta_path


def _patch_calc_properties(text: str) -> str:
    had_crlf = "\r\n" in text
    text = text.replace("\r\n", "\n")
    if "import sys" not in text:
        text = re.sub(r"import os\n", "import os\nimport sys\n", text, count=1)
    if "import subprocess" not in text:
        text = re.sub(r"import os\n", "import os\nimport subprocess\n", text, count=1)

    # Replace os.system('abaqus job=...') with subprocess.check_call, preserving indentation
    os_system_pat = re.compile(
        r"^(\s*)os\.system\('abaqus job=\\{0\\} user=\\{1\\} cpus=\\{2\\} int'\.format\(abq_job,\s*abq_umat,\s*ncpu\)\)\s*$",
        re.MULTILINE,
    )
    match = os_system_pat.search(text)
    if match:
        indent = match.group(1)
        new_block = (
            f"{indent}abaqus_cmd = os.environ.get('MATERIAL_AI_ABAQUS_CMD', 'abaqus')\n"
            f"{indent}subprocess.check_call([abaqus_cmd, 'job={{0}}'.format(abq_job),\n"
            f"{indent}                       'user={{0}}'.format(abq_umat),\n"
            f"{indent}                       'cpus={{0}}'.format(ncpu), 'interactive'])\n"
        )
        text = text[:match.start()] + new_block + text[match.end():]

    if "MATERIAL_AI_MAX_LOAD_CASES" not in text:
        marker = (
            "lc = [[1., 0., 0.], [0., 1., 0.], [1., 1., 0.], [-1., 1., 0.], \\\n"
            "      [0., 0., 1.], [0., 1., 1.], [1., 0., 1.], [0., -1., 1.],[1., 0., -1.]]"
        )
        patched = marker + "\nmax_lc = int(os.environ.get('MATERIAL_AI_MAX_LOAD_CASES', '0') or '0')\nif max_lc > 0:\n    lc = lc[:max_lc]"
        text = text.replace(marker, patched)
    return text.replace("\n", "\r\n") if had_crlf else text


def _write_run_script(work_dir: Path, config: AbaqusBridgeConfig, material_name: str) -> None:
    abaqus_bat = _ps_single_quote(config.abaqus_bat)
    material_arg = _ps_single_quote(material_name)
    script = f"""$env:MATERIAL_AI_ABAQUS_CMD = '{abaqus_bat}'
$env:MATERIAL_AI_MAX_LOAD_CASES = '{config.max_load_cases}'
& '{abaqus_bat}' python calc_properties.py '{material_arg}'
"""
    (work_dir / "run_abaqus_verification.ps1").write_text(script, encoding="utf-8")


def _base_summary(
    config: AbaqusBridgeConfig,
    work_dir: Path,
    material_name: str,
) -> dict[str, Any]:
    return {
        "created_at": datetime.now().isoformat(timespec="seconds"),
        "material_name": material_name,
        "source_run_dir": str(config.run_dir),
        "work_dir": str(work_dir),
        "abaqus_bat": str(config.abaqus_bat),
        "max_load_cases": config.max_load_cases,
        "config": _json_ready(asdict(config)),
    }


def _write_markdown_report(work_dir: Path, summary: dict[str, Any]) -> None:
    result_csv = summary.get("result_csv")
    result_plot = summary.get("result_plot_png")
    result_stats = summary.get("result_stats") or {}
    log_path = summary.get("log_path")
    body = f"""# Abaqus UMAT 验算桥接报告

## 状态

- 状态：`{summary.get("status")}`
- 材料名：`{summary.get("material_name")}`
- Abaqus 命令：`{summary.get("abaqus_bat")}`
- 本轮载荷工况数：`{summary.get("max_load_cases")}`

## 工作目录

`{summary.get("work_dir")}`

## 输出

- Abaqus 日志：`{log_path or "尚未运行"}`
- 结果 CSV：`{result_csv or "尚未生成"}`
- 结果曲线图：`{result_plot or "尚未生成"}`

## 结果摘要

- 数据行数：`{result_stats.get("row_count", "N/A")}`
- 最大 Mises 应力：`{_fmt(result_stats.get("max_mises_mpa"))} MPa`
- 最大 PEEQ：`{_fmt(result_stats.get("max_peeq"))}`
- 最大 S11：`{_fmt(result_stats.get("max_s11_mpa"))} MPa`

## 说明

本目录由 MaterialAI Workbench 自动生成，包含 `femBlock.inp`、`ml_umat.f`、修补后的 `calc_properties.py` 和当前材料的 SVM 参数文件。默认先用少量载荷工况做 sanity check，完整验算可把 `--max-load-cases` 设为 `0` 或更大的数量。
"""
    (work_dir / "abaqus_verification_report.md").write_text(body, encoding="utf-8")


def _postprocess_result_csv(result_csv: Path, work_dir: Path) -> tuple[dict[str, float | int | None], Path]:
    import matplotlib

    matplotlib.use("Agg", force=True)
    import matplotlib.pyplot as plt

    rows: list[dict[str, str]] = []
    with result_csv.open("r", encoding="utf-8") as handle:
        reader = csv.DictReader(handle, delimiter=";")
        for row in reader:
            rows.append(row)

    available = {name.upper(): name for name in (rows[0].keys() if rows else [])}
    peeq = [_to_float(row.get(available.get("PEEQ", ""), "")) for row in rows] if "PEEQ" in available else []
    mises = [_to_float(row.get(available.get("MISES", ""), "")) for row in rows] if "MISES" in available else []
    e11 = [_to_float(row.get(available.get("E11", ""), "")) for row in rows] if "E11" in available else []
    s11 = [_to_float(row.get(available.get("S11", ""), "")) for row in rows] if "S11" in available else []

    fig, ax1 = plt.subplots(figsize=(8, 5))
    if peeq and mises:
        ax1.plot(peeq, mises, color="#b00020", marker="o", markersize=3, label="Mises vs. PEEQ")
        ax1.set_xlabel("Equivalent plastic strain PEEQ")
        ax1.set_ylabel("Mises stress (MPa)")
    else:
        x_values = list(range(1, len(rows) + 1))
        y_values = mises or peeq or [0.0 for _ in rows]
        ax1.plot(x_values, y_values, color="#b00020", marker="o", markersize=3, label="available result")
        ax1.set_xlabel("Row")
        ax1.set_ylabel("Available result value")
    ax1.grid(True, alpha=0.25)
    lines = ax1.get_lines()
    if e11 and s11:
        ax2 = ax1.twinx()
        ax2.plot(e11, s11, color="#1f5fbf", marker="s", markersize=3, linestyle="--", label="S11 vs. E11")
        ax2.set_ylabel("S11 stress (MPa)")
        lines += ax2.get_lines()
    labels = [line.get_label() for line in lines]
    ax1.legend(lines, labels, loc="lower right", fontsize=8)
    fig.subplots_adjust(left=0.1, right=0.88, top=0.92, bottom=0.12)
    plot_path = work_dir / "results" / "abaqus_stress_strain_check.png"
    try:
        fig.savefig(str(plot_path), dpi=200)
    except Exception:
        pass
    plt.close(fig)

    stats = {
        "row_count": len(rows),
        "max_mises_mpa": max(mises) if mises else None,
        "max_peeq": max(peeq) if peeq else None,
        "max_s11_mpa": max(s11) if s11 else None,
        "max_e11": max(e11) if e11 else None,
    }
    return stats, plot_path


def _to_float(value: str) -> float:
    return float(value.strip()) if value is not None and value.strip() else 0.0


def _ps_single_quote(value: Any) -> str:
    return str(value).replace("'", "''")


def _remove_readonly(func: Any, path: str, _exc_info: Any) -> None:
    try:
        os.chmod(path, stat.S_IWRITE)
        func(path)
    except Exception:
        raise


def _fmt(value: Any) -> str:
    if value is None:
        return "N/A"
    if isinstance(value, (int, float)):
        return f"{value:.6g}"
    return str(value)


def _json_ready(value: Any) -> Any:
    if isinstance(value, Path):
        return str(value)
    if isinstance(value, dict):
        return {key: _json_ready(item) for key, item in value.items()}
    if isinstance(value, list):
        return [_json_ready(item) for item in value]
    return value


if __name__ == "__main__":
    main()
