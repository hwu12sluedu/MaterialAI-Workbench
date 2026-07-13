"""Closed-loop validation report utilities for MaterialAI Workbench."""

from __future__ import annotations

import argparse
import json
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from typing import Any

from material_ai_workbench.case_library import CaseSummary, list_cases, load_case_summary
from material_ai_workbench.config import CLOSED_LOOP_ROOT as DEFAULT_CLOSED_LOOP_ROOT
from material_ai_workbench.config import RUNS_ROOT as DEFAULT_RUNS_ROOT
from material_ai_workbench.dataset_export import DATASETS_ROOT
from material_ai_workbench.surrogate_model import SURROGATES_ROOT, list_dataset_exports, surrogate_comparison_rows
from material_ai_workbench.batch_simulation import BATCH_ROOT, list_batch_plans, load_batch_plan


RUNS_ROOT = DEFAULT_RUNS_ROOT
CLOSED_LOOP_ROOT = DEFAULT_CLOSED_LOOP_ROOT


@dataclass
class ClosedLoopReport:
    report_dir: Path
    report_path: Path
    manifest_path: Path
    manifest: dict[str, Any]


def generate_closed_loop_report(
    *,
    material_run: Path | str | None = None,
    case_dir: Path | str | None = None,
    dataset_dir: Path | str | None = None,
    surrogate_run: Path | str | None = None,
    batch_plan: Path | str | None = None,
    output_root: Path = CLOSED_LOOP_ROOT,
) -> ClosedLoopReport:
    """Generate a Markdown report that links the MVP CAE + AI loop together."""

    batch_context = _resolve_batch_context(
        batch_plan=batch_plan,
        use_latest=not any([material_run, case_dir, dataset_dir, surrogate_run]),
    )
    selected_material_run = _resolve_optional_dir(material_run) or batch_context.get("material_run") or _latest_material_run()
    selected_case_dir = _resolve_optional_dir(case_dir) or batch_context.get("case_dir") or _latest_case_dir()
    selected_dataset_dir = _resolve_optional_dir(dataset_dir) or batch_context.get("dataset_dir") or _latest_dataset_dir()
    selected_surrogate_run = _resolve_optional_dir(surrogate_run) or batch_context.get("surrogate_run") or _latest_surrogate_run()

    material_summary = _load_json_if_exists(selected_material_run / "summary.json" if selected_material_run else None)
    abaqus_summary = _load_json_if_exists(selected_material_run / "abaqus_verification" / "bridge_summary.json" if selected_material_run else None)
    case_summary = _load_case_if_exists(selected_case_dir)
    dataset_manifest = _load_json_if_exists(selected_dataset_dir / "dataset_manifest.json" if selected_dataset_dir else None)
    surrogate_metrics = _load_json_if_exists(selected_surrogate_run / "surrogate_metrics.json" if selected_surrogate_run else None)

    checks = _status_checks(
        selected_material_run=selected_material_run,
        material_summary=material_summary,
        abaqus_summary=abaqus_summary,
        selected_case_dir=selected_case_dir,
        case_summary=case_summary,
        selected_dataset_dir=selected_dataset_dir,
        dataset_manifest=dataset_manifest,
        selected_surrogate_run=selected_surrogate_run,
        surrogate_metrics=surrogate_metrics,
    )
    if batch_context.get("summary"):
        checks.insert(
            0,
            _check(
                "批量仿真计划",
                batch_context["summary"].get("completed_sample_count", 0) > 0,
                batch_context.get("plan_path"),
                note=str(batch_context["summary"].get("status_counts", {})),
            ),
        )
    manifest = _build_manifest(
        selected_material_run=selected_material_run,
        selected_case_dir=selected_case_dir,
        selected_dataset_dir=selected_dataset_dir,
        selected_surrogate_run=selected_surrogate_run,
        material_summary=material_summary,
        abaqus_summary=abaqus_summary,
        case_summary=case_summary,
        dataset_manifest=dataset_manifest,
        surrogate_metrics=surrogate_metrics,
        checks=checks,
        batch_context=batch_context,
    )

    report_dir = _unique_report_dir(output_root)
    report_dir.mkdir(parents=True, exist_ok=False)
    manifest_path = report_dir / "closed_loop_manifest.json"
    report_path = report_dir / "closed_loop_validation_report.md"
    manifest_path.write_text(json.dumps(manifest, indent=2, ensure_ascii=False), encoding="utf-8")
    report_path.write_text(_markdown_report(manifest), encoding="utf-8")
    return ClosedLoopReport(report_dir=report_dir, report_path=report_path, manifest_path=manifest_path, manifest=manifest)


def list_closed_loop_reports(root: Path = CLOSED_LOOP_ROOT) -> list[Path]:
    """Return generated closed-loop report folders, newest first."""

    if not root.exists():
        return []
    reports = [path for path in root.iterdir() if path.is_dir() and (path / "closed_loop_manifest.json").exists()]
    return sorted(reports, key=lambda path: path.stat().st_mtime, reverse=True)


def _build_manifest(
    *,
    selected_material_run: Path | None,
    selected_case_dir: Path | None,
    selected_dataset_dir: Path | None,
    selected_surrogate_run: Path | None,
    material_summary: dict[str, Any],
    abaqus_summary: dict[str, Any],
    case_summary: CaseSummary | None,
    dataset_manifest: dict[str, Any],
    surrogate_metrics: dict[str, Any],
    checks: list[dict[str, Any]],
    batch_context: dict[str, Any],
) -> dict[str, Any]:
    material_config = material_summary.get("config", {})
    ml = material_summary.get("ml_material", {})
    metrics = material_summary.get("metrics", {})
    abaqus_stats = abaqus_summary.get("result_stats") or {}
    completed = sum(1 for item in checks if item["status"] == "complete")
    return {
        "created_at": datetime.now().isoformat(timespec="seconds"),
        "title": "MaterialAI Workbench 最小闭环验证报告",
        "paths": {
            "material_run": str(selected_material_run) if selected_material_run else "",
            "case_dir": str(selected_case_dir) if selected_case_dir else "",
            "dataset_dir": str(selected_dataset_dir) if selected_dataset_dir else "",
            "surrogate_run": str(selected_surrogate_run) if selected_surrogate_run else "",
            "batch_plan": str(batch_context.get("plan_dir", "")),
        },
        "batch_plan": batch_context.get("summary", {}),
        "material_training": {
            "name": ml.get("name", ""),
            "material_type": material_config.get("material_type", ""),
            "accuracy": metrics.get("accuracy"),
            "f1": metrics.get("f1"),
            "support_vectors": ml.get("support_vectors"),
        },
        "abaqus_validation": {
            "status": abaqus_summary.get("status", "missing") if abaqus_summary else "missing",
            "max_mises_mpa": abaqus_stats.get("max_mises_mpa"),
            "max_peeq": abaqus_stats.get("max_peeq"),
            "row_count": abaqus_stats.get("row_count"),
        },
        "case_library": {
            "case_id": case_summary.case_id if case_summary else "",
            "title": case_summary.title if case_summary else "",
            "status": case_summary.status if case_summary else "",
            "file_count": len(case_summary.files) if case_summary else 0,
            "odb_extraction_count": len(case_summary.odb_extractions) if case_summary else 0,
            "frame_series_count": len(case_summary.odb_frame_series) if case_summary else 0,
        },
        "dataset_export": {
            "case_count": dataset_manifest.get("case_count"),
            "row_count": dataset_manifest.get("row_count"),
            "frame_series_count": dataset_manifest.get("frame_series_count"),
            "dataset_csv": dataset_manifest.get("dataset_csv", ""),
            "frame_series_index_csv": dataset_manifest.get("frame_series_index_csv", ""),
        },
        "surrogate_model": {
            "target_column": surrogate_metrics.get("target_column", ""),
            "model_kind": surrogate_metrics.get("model_kind", ""),
            "sample_count": surrogate_metrics.get("sample_count"),
            "evaluation_mode": surrogate_metrics.get("evaluation_mode", ""),
            "mae": surrogate_metrics.get("mae"),
            "rmse": surrogate_metrics.get("rmse"),
            "r2": surrogate_metrics.get("r2"),
            "quality_note": surrogate_metrics.get("quality_note", ""),
        },
        "surrogate_comparison": _surrogate_comparison_from_context(batch_context, selected_surrogate_run),
        "checks": checks,
        "completion": {
            "complete_steps": completed,
            "total_steps": len(checks),
            "status": "complete" if completed == len(checks) else "partial",
        },
    }


def _status_checks(
    *,
    selected_material_run: Path | None,
    material_summary: dict[str, Any],
    abaqus_summary: dict[str, Any],
    selected_case_dir: Path | None,
    case_summary: CaseSummary | None,
    selected_dataset_dir: Path | None,
    dataset_manifest: dict[str, Any],
    selected_surrogate_run: Path | None,
    surrogate_metrics: dict[str, Any],
) -> list[dict[str, Any]]:
    return [
        _check("材料模型训练", bool(material_summary), selected_material_run / "summary.json" if selected_material_run else None),
        _check(
            "Abaqus 验算",
            bool(abaqus_summary) and abaqus_summary.get("status") == "completed",
            selected_material_run / "abaqus_verification" / "bridge_summary.json" if selected_material_run else None,
            note=str(abaqus_summary.get("status", "missing") if abaqus_summary else "missing"),
        ),
        _check("案例库归档", bool(case_summary), selected_case_dir / "case_summary.json" if selected_case_dir else None),
        _check(
            "ODB 场变量提取",
            bool(case_summary and case_summary.odb_extractions),
            selected_case_dir / "case_summary.json" if selected_case_dir else None,
        ),
        _check(
            "ODB 帧曲线提取",
            bool(case_summary and case_summary.odb_frame_series),
            selected_case_dir / "case_summary.json" if selected_case_dir else None,
        ),
        _check("训练数据集导出", bool(dataset_manifest), selected_dataset_dir / "dataset_manifest.json" if selected_dataset_dir else None),
        _check(
            "代理模型训练",
            bool(surrogate_metrics),
            selected_surrogate_run / "surrogate_metrics.json" if selected_surrogate_run else None,
            note=str(surrogate_metrics.get("quality_note", "") if surrogate_metrics else ""),
        ),
    ]


def _check(step: str, ok: bool, evidence: Path | None, note: str = "") -> dict[str, Any]:
    return {
        "step": step,
        "status": "complete" if ok else "missing",
        "evidence": str(evidence) if evidence else "",
        "note": note,
    }


def _markdown_report(manifest: dict[str, Any]) -> str:
    checks = "\n".join(
        f"| {item['step']} | {item['status']} | `{item['evidence']}` | {item.get('note', '')} |" for item in manifest.get("checks", [])
    )
    paths = manifest.get("paths", {})
    material = manifest.get("material_training", {})
    abaqus = manifest.get("abaqus_validation", {})
    case = manifest.get("case_library", {})
    dataset = manifest.get("dataset_export", {})
    surrogate = manifest.get("surrogate_model", {})
    surrogate_rows = "\n".join(
        (
            f"| {item.get('model_kind', '')} | {item.get('target_column', '')} | {item.get('sample_count', '')} | "
            f"{item.get('evaluation_mode', '')} | {item.get('mae', '')} | {item.get('rmse', '')} | {item.get('r2', '')} | "
            f"`{item.get('run_dir', '')}` |"
        )
        for item in manifest.get("surrogate_comparison", [])
    )
    surrogate_comparison_section = ""
    if surrogate_rows:
        surrogate_comparison_section = f"""
## 代理模型对比

| 模型 | 目标 | 样本数 | 评估方式 | MAE | RMSE | R2 | Run |
|---|---|---:|---|---:|---:|---:|---|
{surrogate_rows}
"""
    completion = manifest.get("completion", {})
    batch = manifest.get("batch_plan", {})
    batch_rows = "\n".join(
        f"| `{item.get('sample_id', '')}` | {item.get('status', '')} | {item.get('abaqus_status', '')} | {item.get('postprocess_status', '')} | {item.get('yield_strength', '')} | {item.get('max_mises_mpa', '')} |"
        for item in batch.get("samples", [])
    )
    batch_section = ""
    if batch:
        batch_section = f"""
## 批量仿真计划

- Plan: `{paths.get("batch_plan")}`
- 样本数: `{batch.get("sample_count")}`
- 已完成样本数: `{batch.get("completed_sample_count")}`
- 状态统计: `{batch.get("status_counts")}`
- 代理模型 runs: `{batch.get("surrogate_runs")}`

| Sample | 状态 | Abaqus | ODB 后处理 | sy(MPa) | Max Mises |
|---|---|---|---|---:|---:|
{batch_rows}
"""
    return f"""# {manifest.get("title")}

生成时间：`{manifest.get("created_at")}`

## 闭环状态

- 完成度：`{completion.get("complete_steps")}/{completion.get("total_steps")}`
- 状态：`{completion.get("status")}`

| 环节 | 状态 | 证据文件 | 说明 |
|---|---|---|---|
{checks}

{batch_section}

## 材料训练

- Run：`{paths.get("material_run")}`
- 材料模型：`{material.get("name")}`
- 材料类型：`{material.get("material_type")}`
- Accuracy：`{material.get("accuracy")}`
- F1：`{material.get("f1")}`
- 支持向量：`{material.get("support_vectors")}`

## Abaqus 验算

- 状态：`{abaqus.get("status")}`
- Max Mises：`{abaqus.get("max_mises_mpa")}`
- Max PEEQ：`{abaqus.get("max_peeq")}`
- 结果行数：`{abaqus.get("row_count")}`

## 案例库与数据集

- Case：`{case.get("case_id")}` / `{case.get("title")}`
- Case 文件数：`{case.get("file_count")}`
- ODB 场变量提取次数：`{case.get("odb_extraction_count")}`
- ODB 帧曲线次数：`{case.get("frame_series_count")}`
- Dataset：`{paths.get("dataset_dir")}`
- Dataset 行数：`{dataset.get("row_count")}`
- 帧曲线索引数：`{dataset.get("frame_series_count")}`

## 代理模型

- Run：`{paths.get("surrogate_run")}`
- 目标：`{surrogate.get("target_column")}`
- 模型：`{surrogate.get("model_kind")}`
- 样本数：`{surrogate.get("sample_count")}`
- 评估方式：`{surrogate.get("evaluation_mode")}`
- MAE：`{surrogate.get("mae")}`
- RMSE：`{surrogate.get("rmse")}`
- R2：`{surrogate.get("r2")}`

质量说明：{surrogate.get("quality_note")}

{surrogate_comparison_section}

## 工程结论

本报告证明当前 MaterialAI Workbench 已经打通“材料训练 -> Abaqus 验算 -> ODB 后处理 -> 案例库 -> 数据集 -> 代理模型”的最小产品闭环。当前代理模型只应作为流程验证和产品骨架，不应作为真实工程预测依据；下一步需要通过批量 Abaqus 仿真和日常案例沉淀扩充样本量。
"""


def _surrogate_comparison_from_context(batch_context: dict[str, Any], selected_surrogate_run: Path | None) -> list[dict[str, Any]]:
    runs = list((batch_context.get("summary") or {}).get("surrogate_runs", {}).values())
    if not runs and selected_surrogate_run:
        runs = [selected_surrogate_run]
    rows = surrogate_comparison_rows(runs) if runs else []
    return rows


def _latest_material_run(root: Path = RUNS_ROOT) -> Path | None:
    if not root.exists():
        return None
    runs = [path for path in root.iterdir() if path.is_dir() and (path / "summary.json").exists()]
    return sorted(runs, key=lambda path: path.stat().st_mtime, reverse=True)[0] if runs else None


def _resolve_batch_context(
    *,
    batch_plan: Path | str | None,
    use_latest: bool,
) -> dict[str, Any]:
    selected = _resolve_optional_dir(batch_plan)
    if not selected and use_latest:
        selected = _latest_batch_plan()
    if not selected:
        return {}

    plan = load_batch_plan(selected)
    samples = plan.data.get("samples", [])
    completed_samples = [
        sample
        for sample in samples
        if sample.get("status") in {"postprocessed", "abaqus_completed", "postprocess_failed"} and sample.get("run_dir")
    ]
    representative = completed_samples[-1] if completed_samples else {}
    status_counts: dict[str, int] = {}
    sample_rows: list[dict[str, Any]] = []
    for sample in samples:
        status = sample.get("status", "unknown")
        status_counts[status] = status_counts.get(status, 0) + 1
        result_stats = sample.get("result_stats") or {}
        sample_rows.append(
            {
                "sample_id": sample.get("sample_id", ""),
                "status": sample.get("status", ""),
                "abaqus_status": sample.get("abaqus_status", ""),
                "postprocess_status": sample.get("postprocess_status", ""),
                "yield_strength": sample.get("yield_strength", ""),
                "max_mises_mpa": result_stats.get("max_mises_mpa", ""),
                "case_dir": sample.get("case_dir", ""),
            }
        )

    outputs = plan.data.get("outputs", {})
    return {
        "plan_dir": plan.plan_dir,
        "plan_path": plan.plan_path,
        "material_run": Path(representative["run_dir"]).resolve() if representative.get("run_dir") else None,
        "case_dir": Path(representative["case_dir"]).resolve() if representative.get("case_dir") else None,
        "dataset_dir": _resolve_optional_dir(outputs.get("dataset_dir")),
        "surrogate_run": _resolve_optional_dir(outputs.get("surrogate_run")),
        "summary": {
            "name": plan.data.get("name", ""),
            "sample_count": len(samples),
            "completed_sample_count": len(completed_samples),
            "status_counts": status_counts,
            "samples": sample_rows,
            "surrogate_runs": outputs.get("surrogate_runs", {}),
        },
    }


def _latest_batch_plan(root: Path = BATCH_ROOT) -> Path | None:
    for plan_dir in list_batch_plans(root):
        plan = load_batch_plan(plan_dir)
        outputs = plan.data.get("outputs", {})
        has_outputs = bool(outputs.get("dataset_dir") or outputs.get("surrogate_run"))
        has_completed = any(sample.get("status") in {"postprocessed", "abaqus_completed", "postprocess_failed"} for sample in plan.data.get("samples", []))
        if has_completed and has_outputs:
            return plan_dir
    return None


def _latest_case_dir() -> Path | None:
    cases = list_cases()
    return Path(cases[0].case_dir) if cases else None


def _latest_dataset_dir(root: Path = DATASETS_ROOT) -> Path | None:
    datasets = list_dataset_exports(root)
    return datasets[0] if datasets else None


def _latest_surrogate_run(root: Path = SURROGATES_ROOT) -> Path | None:
    if not root.exists():
        return None
    runs = [path for path in root.iterdir() if path.is_dir() and (path / "surrogate_metrics.json").exists()]
    return sorted(runs, key=lambda path: path.stat().st_mtime, reverse=True)[0] if runs else None


def _resolve_optional_dir(path: Path | str | None) -> Path | None:
    if not path:
        return None
    return Path(path).expanduser().resolve()


def _load_json_if_exists(path: Path | None) -> dict[str, Any]:
    if not path or not path.exists():
        return {}
    return json.loads(path.read_text(encoding="utf-8"))


def _load_case_if_exists(case_dir: Path | None) -> CaseSummary | None:
    if not case_dir or not (case_dir / "case_summary.json").exists():
        return None
    return load_case_summary(case_dir)


def _unique_report_dir(output_root: Path) -> Path:
    stamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    base = output_root / f"{stamp}_closed_loop_validation"
    if not base.exists():
        return base
    idx = 2
    while True:
        candidate = output_root / f"{stamp}_closed_loop_validation_{idx}"
        if not candidate.exists():
            return candidate
        idx += 1


def _main() -> None:
    parser = argparse.ArgumentParser(description="Generate a MaterialAI Workbench closed-loop validation report.")
    parser.add_argument("--material-run", type=Path, default=None)
    parser.add_argument("--case-dir", type=Path, default=None)
    parser.add_argument("--dataset-dir", type=Path, default=None)
    parser.add_argument("--surrogate-run", type=Path, default=None)
    parser.add_argument("--batch-plan", type=Path, default=None)
    parser.add_argument("--output-root", type=Path, default=CLOSED_LOOP_ROOT)
    args = parser.parse_args()
    report = generate_closed_loop_report(
        material_run=args.material_run,
        case_dir=args.case_dir,
        dataset_dir=args.dataset_dir,
        surrogate_run=args.surrogate_run,
        batch_plan=args.batch_plan,
        output_root=args.output_root,
    )
    print(report.report_path)


if __name__ == "__main__":
    _main()
