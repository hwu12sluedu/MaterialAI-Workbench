"""Dataset export utilities for the MaterialAI Workbench case library."""

from __future__ import annotations

import csv
import json
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from typing import Any

from material_ai_workbench.case_library import (
    CASES_ROOT,
    CaseSummary,
    infer_case_type,
    list_cases,
    load_case_summary,
)
from material_ai_workbench.case_package import evaluate_case_quality
from material_ai_workbench.config import DATASETS_ROOT


@dataclass
class DatasetExport:
    export_dir: Path
    dataset_csv: Path
    frame_series_index_csv: Path
    manifest_json: Path
    report_md: Path
    case_count: int
    row_count: int
    frame_series_count: int
    source_case_count: int
    skipped_case_count: int


def export_case_dataset(
    *,
    cases_root: Path = CASES_ROOT,
    output_root: Path = DATASETS_ROOT,
    name: str = "case_dataset",
    case_dirs: list[Path | str] | tuple[Path | str, ...] | None = None,
    training_only: bool = False,
) -> DatasetExport:
    """Export case-library features into CSV assets for ML experiments."""

    source_cases = _selected_cases(cases_root=cases_root, case_dirs=case_dirs)
    quality_by_case = {
        case.case_id: case.quality or evaluate_case_quality(case)
        for case in source_cases
    }
    skipped_cases = [
        {
            "case_id": case.case_id,
            "title": case.title,
            "blocking_reasons": quality_by_case[case.case_id].get(
                "blocking_reasons", []
            ),
        }
        for case in source_cases
        if training_only
        and not quality_by_case[case.case_id].get("training_eligible", False)
    ]
    cases = [
        case
        for case in source_cases
        if not training_only
        or quality_by_case[case.case_id].get("training_eligible", False)
    ]
    stamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    safe_name = _safe_name(name)
    export_dir = output_root / f"{stamp}_{safe_name}"
    export_dir.mkdir(parents=True, exist_ok=False)

    dataset_rows = [_case_dataset_row(case) for case in cases]
    frame_rows = _frame_series_index_rows(cases)
    dataset_csv = export_dir / "case_dataset.csv"
    frame_series_index_csv = export_dir / "frame_series_index.csv"
    manifest_json = export_dir / "dataset_manifest.json"
    report_md = export_dir / "dataset_report.md"

    _write_csv(dataset_csv, dataset_rows, CASE_DATASET_COLUMNS)
    _write_csv(frame_series_index_csv, frame_rows, FRAME_SERIES_COLUMNS)
    manifest = {
        "created_at": datetime.now().isoformat(timespec="seconds"),
        "cases_root": str(cases_root),
        "training_only": training_only,
        "source_case_count": len(source_cases),
        "skipped_case_count": len(skipped_cases),
        "skipped_cases": skipped_cases,
        "case_dirs": [str(case.case_dir) for case in cases],
        "case_count": len(cases),
        "row_count": len(dataset_rows),
        "frame_series_count": len(frame_rows),
        "dataset_csv": str(dataset_csv),
        "frame_series_index_csv": str(frame_series_index_csv),
        "columns": {
            "case_dataset": CASE_DATASET_COLUMNS,
            "frame_series_index": FRAME_SERIES_COLUMNS,
        },
    }
    manifest_json.write_text(
        json.dumps(manifest, indent=2, ensure_ascii=False), encoding="utf-8"
    )
    report_md.write_text(_dataset_report(manifest), encoding="utf-8")
    return DatasetExport(
        export_dir=export_dir,
        dataset_csv=dataset_csv,
        frame_series_index_csv=frame_series_index_csv,
        manifest_json=manifest_json,
        report_md=report_md,
        case_count=len(cases),
        row_count=len(dataset_rows),
        frame_series_count=len(frame_rows),
        source_case_count=len(source_cases),
        skipped_case_count=len(skipped_cases),
    )


CASE_DATASET_COLUMNS = [
    "case_id",
    "case_schema_version",
    "source_fingerprint",
    "title",
    "status",
    "unit_system",
    "unit_length",
    "unit_stress",
    "quality_status",
    "quality_score",
    "execution_state",
    "training_eligible",
    "quality_blocking_reasons",
    "tags",
    "batch_sample_id",
    "material_type",
    "case_type",
    "geometry_length",
    "geometry_width",
    "geometry_thickness",
    "geometry_hole_radius",
    "fiber_volume_fraction",
    "loading_applied_strain",
    "loading_applied_stress",
    "loading_type",
    "mesh_node_count",
    "mesh_element_count",
    "yield_strength",
    "youngs_modulus",
    "poisson_ratio",
    "n_load_cases",
    "n_sequence",
    "max_abaqus_load_cases",
    "source_folder",
    "file_count",
    "model_file_count",
    "result_file_count",
    "data_file_count",
    "inp_node_count",
    "inp_element_count",
    "inp_materials",
    "inp_steps",
    "inp_element_types",
    "csv_row_count",
    "log_warning_count",
    "log_error_count",
    "result_max_mises",
    "result_max_peeq",
    "result_max_displacement",
    "result_max_reaction_force",
    "abaqus_max_mises",
    "abaqus_max_peeq",
    "abaqus_max_displacement",
    "abaqus_max_reaction_force",
    "odb_csv_file_count",
    "odb_log_file_count",
    "odb_warning_count",
    "odb_error_count",
    "odb_extraction_count",
    "latest_odb_max_mises",
    "latest_odb_max_peeq",
    "latest_odb_max_displacement",
    "latest_odb_max_reaction_force",
    "frame_series_count",
    "latest_frame_series_rows",
    "latest_frame_series_csv",
    "updated_at",
]


FRAME_SERIES_COLUMNS = [
    "case_id",
    "case_title",
    "odb_name",
    "odb_path",
    "fields",
    "regions_requested",
    "regions_found",
    "row_count",
    "step_count",
    "csv_path",
    "json_path",
    "report_path",
    "created_at",
]


def _case_dataset_row(case: CaseSummary) -> dict[str, Any]:
    inp = (case.inp_features or {}).get("summary", {})
    result = (case.result_features or {}).get("summary", {})
    latest_odb = case.odb_extractions[-1] if case.odb_extractions else {}
    latest_aggregate = latest_odb.get("aggregate", {}) if latest_odb else {}
    latest_series = case.odb_frame_series[-1] if case.odb_frame_series else {}
    params = case.parameters or {}
    geometry = case.geometry or {}
    loading = case.loading or {}
    mesh_stats = case.mesh_stats or {}
    abaqus_results = case.abaqus_results or {}
    odb_features = case.odb_features or {}
    material_type = case.material_type or params.get("material_type", "")
    quality = case.quality or evaluate_case_quality(case)
    units = case.units or {}
    return {
        "case_id": case.case_id,
        "case_schema_version": case.schema_version,
        "source_fingerprint": case.source_fingerprint,
        "title": case.title,
        "status": case.status,
        "unit_system": units.get("system", ""),
        "unit_length": units.get("length", ""),
        "unit_stress": units.get("stress", ""),
        "quality_status": quality.get("status", ""),
        "quality_score": quality.get("score", 0),
        "execution_state": quality.get("execution_state", "unknown"),
        "training_eligible": quality.get("training_eligible", False),
        "quality_blocking_reasons": ";".join(quality.get("blocking_reasons", [])),
        "tags": ";".join(case.tags),
        "batch_sample_id": params.get("batch_sample_id", ""),
        "material_type": material_type,
        "case_type": infer_case_type(case),
        "geometry_length": geometry.get("length", params.get("length", "")),
        "geometry_width": geometry.get("width", params.get("width", "")),
        "geometry_thickness": geometry.get("thickness", params.get("thickness", "")),
        "geometry_hole_radius": geometry.get(
            "hole_radius", params.get("hole_radius", "")
        ),
        "fiber_volume_fraction": geometry.get(
            "fiber_volume_fraction", params.get("fiber_volume_fraction", "")
        ),
        "loading_applied_strain": loading.get(
            "applied_strain", params.get("applied_strain", "")
        ),
        "loading_applied_stress": loading.get(
            "applied_stress", params.get("applied_stress", "")
        ),
        "loading_type": loading.get("load_type", params.get("load_type", "")),
        "mesh_node_count": mesh_stats.get(
            "node_count", inp.get("estimated_node_count", 0)
        ),
        "mesh_element_count": mesh_stats.get(
            "element_count", inp.get("estimated_element_count", 0)
        ),
        "yield_strength": params.get("yield_strength", ""),
        "youngs_modulus": params.get("youngs_modulus", ""),
        "poisson_ratio": params.get("poisson_ratio", ""),
        "n_load_cases": params.get("n_load_cases", ""),
        "n_sequence": params.get("n_sequence", ""),
        "max_abaqus_load_cases": params.get("max_abaqus_load_cases", ""),
        "source_folder": case.source_folder,
        "file_count": len(case.files),
        "model_file_count": case.file_counts.get("model", 0),
        "result_file_count": case.file_counts.get("result", 0),
        "data_file_count": case.file_counts.get("data", 0),
        "inp_node_count": inp.get("estimated_node_count", 0),
        "inp_element_count": inp.get("estimated_element_count", 0),
        "inp_materials": ";".join(inp.get("materials", [])),
        "inp_steps": ";".join(inp.get("steps", [])),
        "inp_element_types": ";".join(inp.get("element_types", [])),
        "csv_row_count": result.get("csv_row_count", 0),
        "log_warning_count": result.get("warning_count", 0),
        "log_error_count": result.get("error_count", 0),
        "result_max_mises": result.get("max_mises"),
        "result_max_peeq": result.get("max_peeq"),
        "result_max_displacement": result.get("max_displacement"),
        "result_max_reaction_force": result.get("max_reaction_force"),
        "abaqus_max_mises": _first_present(
            abaqus_results.get("max_mises"),
            result.get("max_mises"),
            latest_aggregate.get("max_mises"),
        ),
        "abaqus_max_peeq": _first_present(
            abaqus_results.get("max_peeq"),
            result.get("max_peeq"),
            latest_aggregate.get("max_peeq"),
        ),
        "abaqus_max_displacement": _first_present(
            abaqus_results.get("max_displacement"),
            result.get("max_displacement"),
            latest_aggregate.get("max_displacement"),
        ),
        "abaqus_max_reaction_force": _first_present(
            abaqus_results.get("max_reaction_force"),
            result.get("max_reaction_force"),
            latest_aggregate.get("max_reaction_force"),
        ),
        "odb_csv_file_count": odb_features.get(
            "csv_file_count", result.get("csv_file_count", 0)
        ),
        "odb_log_file_count": odb_features.get(
            "log_file_count", result.get("log_file_count", 0)
        ),
        "odb_warning_count": odb_features.get(
            "warning_count", result.get("warning_count", 0)
        ),
        "odb_error_count": odb_features.get(
            "error_count", result.get("error_count", 0)
        ),
        "odb_extraction_count": len(case.odb_extractions),
        "latest_odb_max_mises": latest_aggregate.get("max_mises"),
        "latest_odb_max_peeq": latest_aggregate.get("max_peeq"),
        "latest_odb_max_displacement": latest_aggregate.get("max_displacement"),
        "latest_odb_max_reaction_force": latest_aggregate.get("max_reaction_force"),
        "frame_series_count": len(case.odb_frame_series),
        "latest_frame_series_rows": latest_series.get("row_count", 0),
        "latest_frame_series_csv": latest_series.get("csv_path", ""),
        "updated_at": case.updated_at,
    }


def _frame_series_index_rows(cases: list[CaseSummary]) -> list[dict[str, Any]]:
    rows = []
    for case in cases:
        for series in case.odb_frame_series:
            rows.append(
                {
                    "case_id": case.case_id,
                    "case_title": case.title,
                    "odb_name": series.get("odb_name", ""),
                    "odb_path": series.get("odb_path", ""),
                    "fields": ";".join(series.get("fields_requested", [])),
                    "regions_requested": ";".join(series.get("regions_requested", [])),
                    "regions_found": ";".join(
                        (
                            f"{item.get('name', '')}:{item.get('kind', '')}:{item.get('scope', '')}"
                            if isinstance(item, dict)
                            else str(item)
                        )
                        for item in series.get("regions_found", [])
                    ),
                    "row_count": series.get("row_count", 0),
                    "step_count": series.get("step_count", 0),
                    "csv_path": series.get("csv_path", ""),
                    "json_path": series.get("json_path", ""),
                    "report_path": series.get("report_path", ""),
                    "created_at": series.get("created_at", ""),
                }
            )
    return rows


def _selected_cases(
    *,
    cases_root: Path,
    case_dirs: list[Path | str] | tuple[Path | str, ...] | None,
) -> list[CaseSummary]:
    if not case_dirs:
        return list_cases(cases_root)

    cases: list[CaseSummary] = []
    seen: set[str] = set()
    for case_dir in case_dirs:
        summary = load_case_summary(case_dir)
        key = str(Path(summary.case_dir).resolve()).lower()
        if key in seen:
            continue
        seen.add(key)
        cases.append(summary)
    return cases


def _write_csv(path: Path, rows: list[dict[str, Any]], columns: list[str]) -> None:
    with path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=columns)
        writer.writeheader()
        writer.writerows(rows)


def _first_present(*values: Any) -> Any:
    for value in values:
        if value is not None and value != "":
            return value
    return ""


def _dataset_report(manifest: dict[str, Any]) -> str:
    return f"""# 案例库训练数据导出

## 基本信息

- 创建时间: `{manifest.get("created_at")}`
- 仅导出训练合格案例: `{manifest.get("training_only")}`
- 候选案例数: `{manifest.get("source_case_count")}`
- 实际导出案例数: `{manifest.get("case_count")}`
- 质量门排除案例数: `{manifest.get("skipped_case_count")}`
- 主表行数: `{manifest.get("row_count")}`
- 帧曲线索引数: `{manifest.get("frame_series_count")}`
- 主表: `{manifest.get("dataset_csv")}`
- 帧曲线索引: `{manifest.get("frame_series_index_csv")}`

## 用途

`case_dataset.csv` 汇总 INP 输入特征、显式单位、求解证据、CSV/ODB 结果和数据血缘。
`frame_series_index.csv` 指向每个 ODB 的逐帧曲线，可用于时序代理模型或结果趋势预测。
训练前应检查 `training_eligible`；被排除案例及原因保存在 `dataset_manifest.json`。
"""


def _safe_name(value: str) -> str:
    return (
        "".join(ch if ch.isalnum() or ch in ("-", "_") else "_" for ch in value).strip(
            "_"
        )
        or "dataset"
    )


# -- Dataset governance: train/validation split with lineage tracking --

RESULT_COLUMNS = {
    "abaqus_max_mises",
    "abaqus_max_peeq",
    "abaqus_max_displacement",
    "abaqus_max_reaction_force",
    "latest_odb_max_mises",
    "latest_odb_max_peeq",
    "latest_odb_max_displacement",
    "latest_odb_max_reaction_force",
    "result_max_mises",
    "result_max_peeq",
    "result_max_displacement",
    "result_max_reaction_force",
}
IDENTIFIER_COLUMNS_DS = {"case_id", "title", "source_folder", "batch_sample_id"}
GOVERNANCE_COLUMNS_DS = {
    "case_schema_version",
    "source_fingerprint",
    "status",
    "unit_system",
    "unit_length",
    "unit_stress",
    "quality_status",
    "quality_score",
    "execution_state",
    "training_eligible",
    "quality_blocking_reasons",
    "updated_at",
}


def create_dataset_split(
    dataset_csv: Path | str,
    *,
    output_dir: Path | None = None,
    test_fraction: float = 0.25,
    random_seed: int = 42,
) -> dict[str, Any]:
    """Create train/validation split manifest for a case dataset.

    Returns a manifest with train/val case IDs, feature/target classification,
    and lineage tracing back to source cases.
    """
    import random

    random.seed(random_seed)

    csv_path = Path(dataset_csv)
    rows = _read_csv_rows(csv_path)
    if len(rows) < 2:
        return {
            "error": "Need at least 2 cases for a split.",
            "csv_path": str(csv_path),
        }

    case_ids = [r.get("case_id", str(i)) for i, r in enumerate(rows)]
    n_test = max(1, int(len(rows) * test_fraction))
    indices = list(range(len(rows)))
    random.shuffle(indices)
    test_indices = set(indices[:n_test])
    train_indices = set(indices[n_test:])

    # Identify feature vs target columns
    all_columns = sorted(rows[0].keys())
    feature_columns = []
    target_columns = []
    skipped_columns = []

    for col in all_columns:
        if col in IDENTIFIER_COLUMNS_DS:
            skipped_columns.append({"column": col, "reason": "identifier"})
        elif col in GOVERNANCE_COLUMNS_DS:
            skipped_columns.append({"column": col, "reason": "governance_metadata"})
        elif col in RESULT_COLUMNS:
            target_columns.append(col)
        elif any(
            col.startswith(prefix) for prefix in ("abaqus_", "latest_odb_", "result_")
        ):
            target_columns.append(col)
        else:
            feature_columns.append(col)

    # Check for potential leakage (feature columns that contain result data)
    leakage_warnings = []
    for col in feature_columns:
        if any(
            leak in col.lower()
            for leak in ("mises", "peeq", "displacement", "reaction", "stress", "force")
        ):
            leakage_warnings.append(
                f"Potential leakage: '{col}' is classified as a feature but may contain result data."
            )

    # Build split manifest
    out = output_dir or csv_path.parent
    out = Path(out)
    out.mkdir(parents=True, exist_ok=True)

    train_rows = [rows[i] for i in sorted(train_indices)]
    test_rows = [rows[i] for i in sorted(test_indices)]

    train_csv = out / "train_split.csv"
    test_csv = out / "test_split.csv"
    _write_split(train_csv, train_rows)
    _write_split(test_csv, test_rows)

    manifest = {
        "created_at": datetime.now().isoformat(timespec="seconds"),
        "source_dataset": str(csv_path),
        "random_seed": random_seed,
        "test_fraction": test_fraction,
        "total_rows": len(rows),
        "train_rows": len(train_rows),
        "test_rows": len(test_rows),
        "train_case_ids": [case_ids[i] for i in sorted(train_indices)],
        "test_case_ids": [case_ids[i] for i in sorted(test_indices)],
        "train_csv": str(train_csv),
        "test_csv": str(test_csv),
        "feature_columns": feature_columns,
        "target_columns": target_columns,
        "skipped_columns": skipped_columns,
        "leakage_warnings": leakage_warnings,
    }

    manifest_path = out / "split_manifest.json"
    manifest_path.write_text(
        json.dumps(manifest, indent=2, ensure_ascii=False), encoding="utf-8"
    )
    return manifest


def _read_csv_rows(path: Path) -> list[dict[str, str]]:
    rows: list[dict[str, str]] = []
    with path.open("r", encoding="utf-8-sig", newline="") as f:
        for row in csv.DictReader(f):
            rows.append({k.strip(): v.strip() for k, v in row.items()})
    return rows


def _write_split(path: Path, rows: list[dict[str, str]]) -> None:
    if not rows:
        return
    with path.open("w", encoding="utf-8", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=list(rows[0].keys()))
        writer.writeheader()
        writer.writerows(rows)
