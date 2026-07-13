"""Batch simulation planning and execution for MaterialAI Workbench."""

from __future__ import annotations

import csv
import json
import traceback
from dataclasses import dataclass
from datetime import datetime, timedelta
from pathlib import Path
from typing import Any

from material_ai_workbench.abaqus_bridge import AbaqusBridgeConfig, DEFAULT_ABAQUS_BAT, run_abaqus_verification
from material_ai_workbench.case_library import append_odb_extraction, append_odb_frame_series, load_case_summary, save_case_summary, scan_case_folder
from material_ai_workbench.config import BATCHES_ROOT
from material_ai_workbench.dataset_export import export_case_dataset
from material_ai_workbench.odb_postprocess import run_case_odb_extraction, run_case_odb_frame_series_extraction
from material_ai_workbench.pipeline import WorkbenchConfig, run_material_workbench
from material_ai_workbench.surrogate_model import DEFAULT_TARGET, surrogate_comparison_rows, train_surrogate_from_dataset


BATCH_ROOT = BATCHES_ROOT
STALE_RUNNING_TIMEOUT = timedelta(hours=4)
DEFAULT_YIELD_STRENGTHS = (50.0, 60.0, 70.0)
DEFAULT_HILL_RATIOS = (1.2, 1.0, 0.8, 1.0, 1.0, 1.0)
SAMPLE_COLUMNS = [
    "sample_id",
    "status",
    "material_type",
    "yield_strength",
    "youngs_modulus",
    "poisson_ratio",
    "run_dir",
    "abaqus_status",
    "max_mises_mpa",
    "max_peeq",
    "case_dir",
    "error",
    "postprocess_error",
]


@dataclass
class BatchPlan:
    plan_dir: Path
    plan_path: Path
    report_path: Path
    summary_csv: Path
    data: dict[str, Any]

    @property
    def samples(self) -> list[dict[str, Any]]:
        samples = self.data.get("samples", [])
        return samples if isinstance(samples, list) else []


def create_parameter_sweep_plan(
    *,
    name: str = "batch_j2_sweep",
    material_type: str = "j2",
    yield_strengths: list[float] | tuple[float, ...] = DEFAULT_YIELD_STRENGTHS,
    youngs_modulus: float = 200_000.0,
    poisson_ratio: float = 0.3,
    hill_ratios: tuple[float, float, float, float, float, float] = DEFAULT_HILL_RATIOS,
    c_value: float = 1.0,
    gamma: float = 1.0,
    n_load_cases: int = 32,
    n_sequence: int = 3,
    test_size: int = 60,
    plot_mesh: int = 40,
    max_abaqus_load_cases: int = 1,
    output_root: Path = BATCH_ROOT,
) -> BatchPlan:
    """Create a small batch plan for material-parameter sample expansion."""

    material = _normalize_material_type(material_type)
    values = [float(item) for item in yield_strengths]
    if not values:
        raise ValueError("yield_strengths must contain at least one value.")

    plan_dir = _unique_plan_dir(output_root, name)
    plan_dir.mkdir(parents=True, exist_ok=False)
    samples = []
    for idx, sy in enumerate(values, start=1):
        sample_id = f"{idx:03d}_{material}_sy{_safe_number(sy)}"
        samples.append(
            {
                "sample_id": sample_id,
                "status": "pending",
                "material_type": material,
                "name": f"{_safe_name(name)}_{sample_id}",
                "youngs_modulus": float(youngs_modulus),
                "poisson_ratio": float(poisson_ratio),
                "yield_strength": sy,
                "hill_ratios": list(hill_ratios),
                "c_value": float(c_value),
                "gamma": float(gamma),
                "n_load_cases": int(n_load_cases),
                "n_sequence": int(n_sequence),
                "test_size": int(test_size),
                "plot_mesh": int(plot_mesh),
                "random_seed": 42 + idx,
                "run_dir": "",
                "abaqus_work_dir": "",
                "abaqus_status": "",
                "case_dir": "",
                "error": "",
            }
        )

    data = {
        "created_at": datetime.now().isoformat(timespec="seconds"),
        "updated_at": datetime.now().isoformat(timespec="seconds"),
        "name": name,
        "plan_dir": str(plan_dir),
        "settings": {
            "max_abaqus_load_cases": int(max_abaqus_load_cases),
            "output_root": str(output_root),
        },
        "samples": samples,
        "outputs": {},
    }
    plan = _plan_from_data(plan_dir, data)
    save_batch_plan(plan)
    return plan


def load_batch_plan(plan_dir: Path | str) -> BatchPlan:
    """Load a batch plan folder or batch_plan.json file."""

    path = Path(plan_dir).expanduser().resolve()
    plan_path = path if path.name == "batch_plan.json" else path / "batch_plan.json"
    data = json.loads(plan_path.read_text(encoding="utf-8"))
    return _plan_from_data(plan_path.parent, data)


def save_batch_plan(plan: BatchPlan) -> None:
    plan.data["updated_at"] = datetime.now().isoformat(timespec="seconds")
    trend_path = _write_batch_trend_plot(plan)
    if trend_path:
        plan.data.setdefault("outputs", {})["batch_trend_png"] = str(trend_path)
    plan.plan_path.write_text(json.dumps(plan.data, indent=2, ensure_ascii=False), encoding="utf-8")
    _write_summary_csv(plan)
    plan.report_path.write_text(_batch_report(plan.data), encoding="utf-8")


def list_batch_plans(root: Path = BATCH_ROOT) -> list[Path]:
    """Return batch plan folders, newest first."""

    if not root.exists():
        return []
    plans = [path for path in root.iterdir() if path.is_dir() and (path / "batch_plan.json").exists()]
    return sorted(plans, key=lambda path: path.stat().st_mtime, reverse=True)


def run_batch_plan(
    plan_dir: Path | str,
    *,
    run_abaqus: bool = False,
    archive_cases: bool = False,
    postprocess_odb: bool = False,
    export_dataset_after: bool = False,
    train_surrogate_after: bool = False,
    max_samples: int | None = None,
    timeout_seconds: int = 1800,
) -> BatchPlan:
    """Run pending/failed samples in a batch plan.

    The default mode runs material training only. Abaqus and ODB post-processing
    stay explicit because they can take time and require local solver licenses.
    """

    plan = load_batch_plan(plan_dir)
    _reset_stale_running_samples(plan)
    processed = 0
    for sample in plan.data.get("samples", []):
        if max_samples is not None and processed >= max_samples:
            break
        if sample.get("status") not in {"pending", "failed", "material_completed", "abaqus_failed"}:
            continue
        _run_one_sample(plan, sample, run_abaqus=run_abaqus, archive_cases=archive_cases, postprocess_odb=postprocess_odb, timeout_seconds=timeout_seconds)
        processed += 1
        save_batch_plan(plan)

    if export_dataset_after:
        _sync_batch_case_parameters(plan)
        dataset = export_case_dataset(
            name=f"{_safe_name(plan.data.get('name', 'batch'))}_dataset",
            case_dirs=_batch_case_dirs(plan),
        )
        plan.data.setdefault("outputs", {})["dataset_dir"] = str(dataset.export_dir)
        plan.data["outputs"]["dataset_csv"] = str(dataset.dataset_csv)

    if train_surrogate_after:
        dataset_dir = plan.data.get("outputs", {}).get("dataset_dir")
        if not dataset_dir:
            _sync_batch_case_parameters(plan)
            dataset = export_case_dataset(
                name=f"{_safe_name(plan.data.get('name', 'batch'))}_dataset",
                case_dirs=_batch_case_dirs(plan),
            )
            dataset_dir = str(dataset.export_dir)
            plan.data.setdefault("outputs", {})["dataset_dir"] = dataset_dir
            plan.data["outputs"]["dataset_csv"] = str(dataset.dataset_csv)
        surrogate = train_surrogate_from_dataset(dataset_dir, target_column=DEFAULT_TARGET, model_kind="random_forest")
        plan.data.setdefault("outputs", {})["surrogate_run"] = str(surrogate.run_dir)

    save_batch_plan(plan)
    return plan


def batch_sample_table_rows(plan: BatchPlan | dict[str, Any]) -> list[dict[str, Any]]:
    """Return compact rows for Streamlit and reports."""

    data = plan.data if isinstance(plan, BatchPlan) else plan
    rows = []
    for sample in data.get("samples", []):
        result_stats = sample.get("result_stats") or {}
        rows.append(
            {
                "sample_id": sample.get("sample_id", ""),
                "status": sample.get("status", ""),
                "material": sample.get("material_type", ""),
                "sy": sample.get("yield_strength", ""),
                "Abaqus": sample.get("abaqus_status", ""),
                "Max Mises": result_stats.get("max_mises_mpa"),
                "Max PEEQ": result_stats.get("max_peeq"),
                "run_dir": sample.get("run_dir", ""),
                "case_dir": sample.get("case_dir", ""),
                "error": sample.get("error", ""),
            }
        )
    return rows


def _run_one_sample(
    plan: BatchPlan,
    sample: dict[str, Any],
    *,
    run_abaqus: bool,
    archive_cases: bool,
    postprocess_odb: bool,
    timeout_seconds: int,
) -> None:
    sample["started_at"] = datetime.now().isoformat(timespec="seconds")
    sample["status"] = "running"
    sample["error"] = ""
    save_batch_plan(plan)
    try:
        if not sample.get("run_dir"):
            config = WorkbenchConfig(
                material_type=sample["material_type"],
                name=sample["name"],
                output_dir=plan.plan_dir / "runs",
                youngs_modulus=float(sample["youngs_modulus"]),
                poisson_ratio=float(sample["poisson_ratio"]),
                yield_strength=float(sample["yield_strength"]),
                hill_ratios=tuple(float(value) for value in sample.get("hill_ratios", DEFAULT_HILL_RATIOS)),
                c_value=float(sample["c_value"]),
                gamma=float(sample["gamma"]),
                n_load_cases=int(sample["n_load_cases"]),
                n_sequence=int(sample["n_sequence"]),
                test_size=int(sample["test_size"]),
                plot_mesh=int(sample["plot_mesh"]),
                random_seed=int(sample["random_seed"]),
            )
            result = run_material_workbench(config)
            sample["run_dir"] = str(result.run_dir)
            sample["material_metrics"] = result.metrics
            sample["support_vectors"] = result.support_vectors
        sample["status"] = "material_completed"

        if run_abaqus:
            bridge = run_abaqus_verification(
                AbaqusBridgeConfig(
                    run_dir=Path(sample["run_dir"]),
                    max_load_cases=int(plan.data.get("settings", {}).get("max_abaqus_load_cases", 1)),
                    abaqus_bat=DEFAULT_ABAQUS_BAT,
                    timeout_seconds=int(timeout_seconds),
                )
            )
            sample["abaqus_work_dir"] = str(bridge.work_dir)
            sample["abaqus_status"] = bridge.status
            bridge_summary = _load_json(bridge.summary_path)
            sample["result_stats"] = bridge_summary.get("result_stats", {})
            if bridge.status == "completed":
                sample["status"] = "abaqus_completed"
            else:
                sample["status"] = "abaqus_failed"

        if archive_cases and sample.get("run_dir"):
            source = Path(sample.get("abaqus_work_dir") or sample["run_dir"])
            if not source or str(source) == "." or not source.exists():
                sample["postprocess_error"] = f"Archive source is not available: {source}"
                sample["status"] = "archive_failed"
                return
            case = scan_case_folder(
                source,
                title=f"Batch sample {sample['sample_id']}",
                tags=["batch", sample["material_type"], "MaterialAI"],
                description=f"自动批量样本：{sample['sample_id']}，yield_strength={sample['yield_strength']} MPa。",
                status="success" if sample.get("status") in {"material_completed", "abaqus_completed"} else "needs_review",
                parameters=_sample_parameters(plan, sample),
            )
            sample["case_dir"] = case.case_dir
            if postprocess_odb:
                odb_path = _find_latest_odb(source)
                if odb_path:
                    try:
                        extraction = run_case_odb_extraction(case, odb_path, backend="auto")
                        case = append_odb_extraction(case, extraction)
                        series = run_case_odb_frame_series_extraction(case, odb_path, fields=["S", "U"])
                        case = append_odb_frame_series(case, series)
                        sample["case_dir"] = case.case_dir
                        sample["postprocess_status"] = "completed"
                        sample["postprocess_error"] = ""
                        sample["status"] = "postprocessed"
                    except Exception as exc:
                        sample["postprocess_status"] = "failed"
                        sample["postprocess_error"] = f"{type(exc).__name__}: {exc}"
                        if sample.get("status") == "abaqus_completed":
                            sample["status"] = "postprocess_failed"

        sample["completed_at"] = datetime.now().isoformat(timespec="seconds")
    except Exception as exc:
        sample["status"] = "failed"
        sample["error"] = f"{type(exc).__name__}: {exc}"
        sample["traceback"] = traceback.format_exc()
        sample["completed_at"] = datetime.now().isoformat(timespec="seconds")


def _plan_from_data(plan_dir: Path, data: dict[str, Any]) -> BatchPlan:
    return BatchPlan(
        plan_dir=plan_dir,
        plan_path=plan_dir / "batch_plan.json",
        report_path=plan_dir / "batch_report.md",
        summary_csv=plan_dir / "batch_summary.csv",
        data=data,
    )


def _write_summary_csv(plan: BatchPlan) -> None:
    rows = []
    for sample in plan.data.get("samples", []):
        result_stats = sample.get("result_stats") or {}
        rows.append(
            {
                "sample_id": sample.get("sample_id", ""),
                "status": sample.get("status", ""),
                "material_type": sample.get("material_type", ""),
                "yield_strength": sample.get("yield_strength", ""),
                "youngs_modulus": sample.get("youngs_modulus", ""),
                "poisson_ratio": sample.get("poisson_ratio", ""),
                "run_dir": sample.get("run_dir", ""),
                "abaqus_status": sample.get("abaqus_status", ""),
                "max_mises_mpa": result_stats.get("max_mises_mpa", ""),
                "max_peeq": result_stats.get("max_peeq", ""),
                "case_dir": sample.get("case_dir", ""),
                "error": sample.get("error", ""),
                "postprocess_error": sample.get("postprocess_error", ""),
            }
        )
    with plan.summary_csv.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=SAMPLE_COLUMNS)
        writer.writeheader()
        writer.writerows([{key: row.get(key, "") for key in SAMPLE_COLUMNS} for row in rows])


def _reset_stale_running_samples(plan: BatchPlan) -> None:
    now = datetime.now()
    changed = False
    for sample in plan.samples:
        if sample.get("status") != "running":
            continue
        started_at = _parse_datetime(sample.get("started_at"))
        if started_at is None or now - started_at > STALE_RUNNING_TIMEOUT:
            sample["status"] = "pending"
            sample["error"] = "Recovered stale running sample after timeout."
            changed = True
    if changed:
        save_batch_plan(plan)


def _parse_datetime(value: Any) -> datetime | None:
    if not value:
        return None
    try:
        return datetime.fromisoformat(str(value))
    except ValueError:
        return None


def _write_batch_trend_plot(plan: BatchPlan) -> Path | None:
    points: list[tuple[float, float, str]] = []
    for sample in plan.data.get("samples", []):
        result_stats = sample.get("result_stats") or {}
        sy = _to_float_or_none(sample.get("yield_strength"))
        mises = _to_float_or_none(result_stats.get("max_mises_mpa"))
        if sy is not None and mises is not None:
            points.append((sy, mises, str(sample.get("sample_id", ""))))
    if len(points) < 2:
        return None

    points.sort(key=lambda item: item[0])
    import matplotlib

    matplotlib.use("Agg", force=True)
    import matplotlib.pyplot as plt

    sy_values = [item[0] for item in points]
    mises_values = [item[1] for item in points]
    fig, ax = plt.subplots(figsize=(7, 4.5))
    ax.plot(sy_values, mises_values, marker="o", color="#1f5fbf", linewidth=2)
    ax.set_xlabel("Yield strength sy (MPa)")
    ax.set_ylabel("Abaqus max Mises (MPa)")
    ax.set_title("Batch trend: material strength vs. Abaqus response")
    ax.grid(True, alpha=0.25)
    for sy, mises, sample_id in points:
        ax.annotate(sample_id.split("_")[0], (sy, mises), textcoords="offset points", xytext=(5, 5), fontsize=8)
    fig.tight_layout()
    plot_path = plan.plan_dir / "batch_trend.png"
    try:
        fig.savefig(str(plot_path), dpi=180)
    except Exception:
        pass
    plt.close(fig)
    return plot_path


def _batch_report(data: dict[str, Any]) -> str:
    rows = batch_sample_table_rows(data)
    table = "\n".join(
        f"| `{row['sample_id']}` | {row['status']} | {row['material']} | {row['sy']} | {row['Abaqus']} | {row['Max Mises']} | `{row['run_dir']}` |"
        for row in rows
    )
    counts: dict[str, int] = {}
    for sample in data.get("samples", []):
        counts[sample.get("status", "unknown")] = counts.get(sample.get("status", "unknown"), 0) + 1
    trend_png = (data.get("outputs") or {}).get("batch_trend_png", "")
    trend_section = f"\n## 趋势图\n\n![Batch trend]({trend_png})\n" if trend_png else ""
    surrogate_section = _batch_surrogate_section(data)
    return f"""# 批量样本计划报告

## 基本信息

- 名称：`{data.get("name")}`
- 创建时间：`{data.get("created_at")}`
- 更新时间：`{data.get("updated_at")}`
- 样本数：`{len(data.get("samples", []))}`
- 状态统计：`{counts}`

## 样本表

| Sample | 状态 | 材料 | sy(MPa) | Abaqus | Max Mises | Run |
|---|---|---|---:|---|---:|---|
{table}

{trend_section}

{surrogate_section}

## 工程说明

这个批量计划用于把单个闭环样本扩展为多样本训练集。第一版优先保证任务可追踪、可恢复、可后处理；Abaqus 求解和 ODB 深度后处理均保持显式开关，避免长时间任务误触发。
"""


def _batch_surrogate_section(data: dict[str, Any]) -> str:
    outputs = data.get("outputs") or {}
    runs = outputs.get("surrogate_runs") or {}
    if not runs:
        single_run = outputs.get("surrogate_run")
        runs = {"random_forest": single_run} if single_run else {}
    rows = surrogate_comparison_rows(runs.values()) if runs else []
    if not rows:
        return ""
    table = "\n".join(
        (
            f"| {row.get('model_kind', '')} | {row.get('target_column', '')} | {row.get('sample_count', '')} | "
            f"{row.get('evaluation_mode', '')} | {row.get('mae', '')} | {row.get('rmse', '')} | "
            f"{row.get('r2', '')} | `{row.get('run_dir', '')}` |"
        )
        for row in rows
    )
    return f"""## 代理模型对比

| 模型 | 目标 | 样本数 | 评估方式 | MAE | RMSE | R2 | Run |
|---|---|---:|---|---:|---:|---:|---|
{table}
"""


def summarize_batch_with_llm(batch_dir: Path | str) -> str | None:
    """Generate an optional LLM summary for a batch plan."""

    from material_ai_workbench.llm_adapter import _chat_completion, _llm_available

    if not _llm_available():
        return None
    summary_csv = Path(batch_dir) / "batch_summary.csv"
    if not summary_csv.exists():
        return None
    rows = []
    with summary_csv.open("r", encoding="utf-8", newline="") as handle:
        for row in csv.DictReader(handle):
            rows.append(row)
    if not rows:
        return None
    lines = ["sample_id,yield_strength,max_mises_mpa,status"]
    for row in rows[:30]:
        lines.append(
            f"{row.get('sample_id', '')},{row.get('yield_strength', '')},"
            f"{row.get('max_mises_mpa', '')},{row.get('status', '')}"
        )
    prompt = (
        "以下是批量材料参数扫描结果。请用2-3段中文总结："
        "(1) 屈服强度与最大 Mises 应力的关系是否合理；"
        "(2) 是否有异常样本；"
        "(3) 建议下一步扫描范围。\n\n"
        + "\n".join(lines)
    )
    return _chat_completion("你是仿真验证工程师，请简洁总结批量仿真结果。", prompt)


def _load_json(path: Path) -> dict[str, Any]:
    if not path.exists():
        return {}
    return json.loads(path.read_text(encoding="utf-8"))


def _batch_case_dirs(plan: BatchPlan) -> list[Path]:
    case_dirs: list[Path] = []
    for sample in plan.data.get("samples", []):
        if sample.get("status") not in {"postprocessed", "abaqus_completed", "postprocess_failed"}:
            continue
        case_dir = sample.get("case_dir")
        if case_dir and Path(case_dir).exists():
            case_dirs.append(Path(case_dir))
    return case_dirs


def _sync_batch_case_parameters(plan: BatchPlan) -> None:
    for sample in plan.data.get("samples", []):
        case_dir = sample.get("case_dir")
        if not case_dir or not Path(case_dir).exists():
            continue
        summary = load_case_summary(case_dir)
        summary.parameters.update(_sample_parameters(plan, sample))
        save_case_summary(summary)


def _sample_parameters(plan: BatchPlan, sample: dict[str, Any]) -> dict[str, Any]:
    settings = plan.data.get("settings", {})
    return {
        "batch_plan_name": plan.data.get("name", ""),
        "batch_sample_id": sample.get("sample_id", ""),
        "material_type": sample.get("material_type", ""),
        "yield_strength": sample.get("yield_strength", ""),
        "youngs_modulus": sample.get("youngs_modulus", ""),
        "poisson_ratio": sample.get("poisson_ratio", ""),
        "n_load_cases": sample.get("n_load_cases", ""),
        "n_sequence": sample.get("n_sequence", ""),
        "max_abaqus_load_cases": settings.get("max_abaqus_load_cases", ""),
    }


def _find_latest_odb(root: Path) -> Path | None:
    if not root.exists():
        return None
    candidates = sorted(root.rglob("*.odb"), key=lambda path: path.stat().st_mtime, reverse=True)
    return candidates[0] if candidates else None


def _normalize_material_type(value: str) -> str:
    material = str(value or "j2").strip().lower()
    if material not in {"j2", "hill"}:
        raise ValueError("material_type must be 'j2' or 'hill'.")
    return material


def _unique_plan_dir(output_root: Path, name: str) -> Path:
    stamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    base = output_root / f"{stamp}_{_safe_name(name)}"
    if not base.exists():
        return base
    idx = 2
    while True:
        candidate = output_root / f"{stamp}_{_safe_name(name)}_{idx}"
        if not candidate.exists():
            return candidate
        idx += 1


def _safe_name(value: str) -> str:
    return "".join(ch if ch.isalnum() or ch in ("-", "_") else "_" for ch in str(value)).strip("_") or "batch"


def _safe_number(value: float) -> str:
    return str(float(value)).replace(".", "p").replace("-", "m")


def _to_float_or_none(value: Any) -> float | None:
    try:
        if value in ("", None):
            return None
        return float(value)
    except (TypeError, ValueError):
        return None
