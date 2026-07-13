"""ODB post-processing helpers for MaterialAI Workbench case library."""

from __future__ import annotations

import csv
import json
from datetime import datetime
from pathlib import Path
from typing import Any

from material_ai_workbench.abaqus_batch_client import (
    AbaqusBatchConfig,
    extract_odb_field_summary_batch,
    extract_odb_frame_series_batch,
)
from material_ai_workbench.abaqus_mcp_client import (
    AbaqusMcpConfig,
    capture_viewport,
    display_odb_contour,
    extract_odb_field_summary,
)
from material_ai_workbench.case_library import CaseSummary


DEFAULT_ODB_FIELDS = ("S", "PEEQ", "U", "RF", "CPRESS", "COPEN")
DEFAULT_FRAME_SERIES_FIELDS = ("S", "PEEQ", "U", "RF")


def run_case_odb_extraction(
    summary: CaseSummary,
    odb_path: Path | str,
    *,
    fields: list[str] | tuple[str, ...] | None = None,
    max_values_per_field: int = 500_000,
    capture_contour: bool = True,
    backend: str = "auto",
    config: AbaqusMcpConfig | None = None,
    batch_config: AbaqusBatchConfig | None = None,
) -> dict[str, Any]:
    """Extract ODB field summaries and persist them under a case directory."""

    odb = Path(odb_path).expanduser().resolve()
    if not odb.exists():
        raise FileNotFoundError(f"ODB file does not exist: {odb}")

    field_names = _normalize_fields(fields or DEFAULT_ODB_FIELDS)
    extraction_dir = _unique_extraction_dir(Path(summary.case_dir) / "odb_extractions", odb.stem)
    extraction_dir.mkdir(parents=True, exist_ok=False)

    raw, backend_used, backend_errors = _extract_raw_odb_summary(
        odb=odb,
        fields=field_names,
        max_values_per_field=max_values_per_field,
        extraction_dir=extraction_dir,
        backend=backend,
        config=config,
        batch_config=batch_config,
    )
    result = _build_extraction_result(
        summary=summary,
        odb_path=odb,
        extraction_dir=extraction_dir,
        raw=raw,
        fields=field_names,
        max_values_per_field=max_values_per_field,
    )
    result["backend_requested"] = _normalize_backend(backend)
    result["backend_used"] = backend_used
    result["backend_errors"] = backend_errors

    contour_errors: list[str] = []
    if capture_contour and backend_used == "mcp":
        try:
            display_odb_contour(odb, field_label="S", invariant="Mises", config=config)
            viewport_dir = extraction_dir / "viewports"
            viewport_path = capture_viewport(viewport_dir, config=config)
            result["viewport_image"] = str(viewport_path)
        except Exception as exc:
            contour_errors.append(str(exc))
    elif capture_contour:
        contour_errors.append("云图截图需要 Abaqus MCP 实时桥接；本次仅完成 ODB 批处理特征提取。")
    result["contour_errors"] = contour_errors

    _write_outputs(result, extraction_dir)
    return result


def extraction_summary_rows(extraction: dict[str, Any]) -> list[dict[str, Any]]:
    rows = []
    for stat in extraction.get("field_stats", []):
        rows.append(
            {
                "Step": stat.get("step", ""),
                "Frame": stat.get("frame_index", ""),
                "Field": stat.get("field", ""),
                "Metric": stat.get("metric", ""),
                "Count": stat.get("scanned_count", 0),
                "Min": stat.get("min"),
                "Max": stat.get("max"),
                "MaxAbs": stat.get("max_abs"),
                "Location": _format_location(stat.get("max_abs_location") or stat.get("max_location") or {}),
                "Truncated": stat.get("truncated", False),
            }
        )
    return rows


def run_case_odb_frame_series_extraction(
    summary: CaseSummary,
    odb_path: Path | str,
    *,
    fields: list[str] | tuple[str, ...] | None = None,
    region_names: list[str] | tuple[str, ...] | None = None,
    max_values_per_field: int = 200_000,
    max_frames_per_step: int = 500,
    batch_config: AbaqusBatchConfig | None = None,
) -> dict[str, Any]:
    """Extract per-frame field aggregate curves and persist them under a case."""

    odb = Path(odb_path).expanduser().resolve()
    if not odb.exists():
        raise FileNotFoundError(f"ODB file does not exist: {odb}")

    field_names = _normalize_fields(fields or DEFAULT_FRAME_SERIES_FIELDS)
    series_dir = _unique_extraction_dir(Path(summary.case_dir) / "odb_frame_series", odb.stem)
    series_dir.mkdir(parents=True, exist_ok=False)
    raw = extract_odb_frame_series_batch(
        odb,
        fields=field_names,
        region_names=_normalize_region_names(region_names or ()),
        max_values_per_field=max_values_per_field,
        max_frames_per_step=max_frames_per_step,
        output_dir=series_dir / "batch_work",
        config=batch_config,
    )
    result = _build_frame_series_result(
        summary=summary,
        odb_path=odb,
        series_dir=series_dir,
        raw=raw,
        fields=field_names,
        max_values_per_field=max_values_per_field,
        max_frames_per_step=max_frames_per_step,
    )
    _write_frame_series_outputs(result, series_dir)
    return result


def frame_series_rows(series: dict[str, Any]) -> list[dict[str, Any]]:
    rows = []
    for row in series.get("rows", []):
        rows.append(
            {
                "Step": row.get("step", ""),
                "Frame": row.get("frame_index", ""),
                "FrameValue": row.get("frame_value"),
                "Field": row.get("field", ""),
                "Metric": row.get("metric", ""),
                "Region": row.get("region_name", "GLOBAL"),
                "RegionKind": row.get("region_kind", "global"),
                "Count": row.get("scanned_count", 0),
                "Min": row.get("min"),
                "Max": row.get("max"),
                "Mean": row.get("mean"),
                "MaxAbs": row.get("max_abs"),
                "Location": _format_location(row.get("max_abs_location") or {}),
                "Truncated": row.get("truncated", False),
            }
        )
    return rows


def _extract_raw_odb_summary(
    *,
    odb: Path,
    fields: list[str],
    max_values_per_field: int,
    extraction_dir: Path,
    backend: str,
    config: AbaqusMcpConfig | None,
    batch_config: AbaqusBatchConfig | None,
) -> tuple[dict[str, Any], str, list[str]]:
    backend_name = _normalize_backend(backend)
    backend_errors: list[str] = []
    if backend_name in ("mcp", "auto"):
        try:
            raw = extract_odb_field_summary(
                odb,
                fields=fields,
                max_values_per_field=max_values_per_field,
                config=config,
            )
            return raw, "mcp", backend_errors
        except Exception as exc:
            if backend_name == "mcp":
                raise
            backend_errors.append(f"MCP: {exc}")

    raw = extract_odb_field_summary_batch(
        odb,
        fields=fields,
        max_values_per_field=max_values_per_field,
        output_dir=extraction_dir / "batch_work",
        config=batch_config,
    )
    return raw, "abaqus_python", backend_errors


def _normalize_backend(backend: str) -> str:
    value = str(backend or "mcp").strip().lower()
    aliases = {
        "mcp": "mcp",
        "socket": "mcp",
        "live": "mcp",
        "auto": "auto",
        "batch": "abaqus_python",
        "abaqus": "abaqus_python",
        "abaqus_python": "abaqus_python",
        "smapython": "abaqus_python",
    }
    if value not in aliases:
        raise ValueError("backend must be one of: mcp, auto, abaqus_python")
    return aliases[value]


def _build_extraction_result(
    *,
    summary: CaseSummary,
    odb_path: Path,
    extraction_dir: Path,
    raw: dict[str, Any],
    fields: list[str],
    max_values_per_field: int,
) -> dict[str, Any]:
    field_stats = raw.get("field_stats", [])
    aggregate = _aggregate_field_stats(field_stats)
    return {
        "created_at": datetime.now().isoformat(timespec="seconds"),
        "case_id": summary.case_id,
        "case_title": summary.title,
        "odb_path": str(odb_path),
        "odb_name": odb_path.name,
        "extraction_dir": str(extraction_dir),
        "fields_requested": fields,
        "regions_requested": raw.get("regions_requested", []),
        "regions_found": raw.get("regions_found", []),
        "max_values_per_field": int(max_values_per_field),
        "frame_mode": raw.get("frame_mode", "last_frame_per_step"),
        "aggregate": aggregate,
        "instances": raw.get("instances", []),
        "node_sets": raw.get("node_sets", []),
        "element_sets": raw.get("element_sets", []),
        "steps": raw.get("steps", []),
        "field_stats": field_stats,
        "history_outputs": raw.get("history_outputs", []),
        "history_truncated": raw.get("history_truncated", False),
        "raw_summary": {
            "title": raw.get("title", ""),
            "description": raw.get("description", ""),
            "limits": raw.get("limits", {}),
        },
        "json_path": str(extraction_dir / "odb_field_summary.json"),
        "csv_path": str(extraction_dir / "odb_field_summary.csv"),
        "report_path": str(extraction_dir / "odb_field_report.md"),
        "viewport_image": None,
        "contour_errors": [],
    }


def _build_frame_series_result(
    *,
    summary: CaseSummary,
    odb_path: Path,
    series_dir: Path,
    raw: dict[str, Any],
    fields: list[str],
    max_values_per_field: int,
    max_frames_per_step: int,
) -> dict[str, Any]:
    rows = raw.get("rows", [])
    steps = raw.get("steps", [])
    return {
        "created_at": datetime.now().isoformat(timespec="seconds"),
        "case_id": summary.case_id,
        "case_title": summary.title,
        "odb_path": str(odb_path),
        "odb_name": odb_path.name,
        "series_dir": str(series_dir),
        "fields_requested": fields,
        "regions_requested": raw.get("regions_requested", []),
        "regions_found": raw.get("regions_found", []),
        "max_values_per_field": int(max_values_per_field),
        "max_frames_per_step": int(max_frames_per_step),
        "backend_used": "abaqus_python",
        "frame_mode": raw.get("frame_mode", "all_frames_per_step_limited"),
        "step_count": len(steps),
        "row_count": len(rows),
        "steps": steps,
        "rows": rows,
        "raw_summary": {
            "title": raw.get("title", ""),
            "description": raw.get("description", ""),
            "limits": raw.get("limits", {}),
        },
        "json_path": str(series_dir / "odb_frame_series.json"),
        "csv_path": str(series_dir / "odb_frame_series.csv"),
        "report_path": str(series_dir / "odb_frame_series_report.md"),
    }


def _aggregate_field_stats(field_stats: list[dict[str, Any]]) -> dict[str, Any]:
    aggregate: dict[str, Any] = {
        "field_count": len(field_stats),
        "max_mises": None,
        "max_peeq": None,
        "max_displacement": None,
        "max_reaction_force": None,
        "truncated_field_count": sum(1 for item in field_stats if item.get("truncated")),
    }
    for stat in field_stats:
        field = str(stat.get("field", "")).upper()
        metric = str(stat.get("metric", "")).upper()
        max_value = stat.get("max")
        max_abs = stat.get("max_abs")
        if field == "S" and metric == "MISES":
            aggregate["max_mises"] = _max_value(aggregate.get("max_mises"), max_value)
        elif field == "PEEQ":
            aggregate["max_peeq"] = _max_value(aggregate.get("max_peeq"), max_value)
        elif field == "U":
            aggregate["max_displacement"] = _max_value(aggregate.get("max_displacement"), max_abs)
        elif field == "RF":
            aggregate["max_reaction_force"] = _max_value(aggregate.get("max_reaction_force"), max_abs)
    return aggregate


def _write_outputs(result: dict[str, Any], extraction_dir: Path) -> None:
    json_path = extraction_dir / "odb_field_summary.json"
    csv_path = extraction_dir / "odb_field_summary.csv"
    report_path = extraction_dir / "odb_field_report.md"
    result["json_path"] = str(json_path)
    result["csv_path"] = str(csv_path)
    result["report_path"] = str(report_path)

    json_path.write_text(json.dumps(result, indent=2, ensure_ascii=False), encoding="utf-8")
    _write_field_csv(result, csv_path)
    report_path.write_text(_markdown_report(result), encoding="utf-8")


def _write_frame_series_outputs(result: dict[str, Any], series_dir: Path) -> None:
    json_path = series_dir / "odb_frame_series.json"
    csv_path = series_dir / "odb_frame_series.csv"
    report_path = series_dir / "odb_frame_series_report.md"
    result["json_path"] = str(json_path)
    result["csv_path"] = str(csv_path)
    result["report_path"] = str(report_path)

    json_path.write_text(json.dumps(result, indent=2, ensure_ascii=False), encoding="utf-8")
    _write_frame_series_csv(result, csv_path)
    report_path.write_text(_frame_series_markdown_report(result), encoding="utf-8")


def _write_field_csv(result: dict[str, Any], path: Path) -> None:
    rows = extraction_summary_rows(result)
    columns = ["Step", "Frame", "Field", "Metric", "Count", "Min", "Max", "MaxAbs", "Location", "Truncated"]
    with path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=columns)
        writer.writeheader()
        writer.writerows(rows)


def _write_frame_series_csv(result: dict[str, Any], path: Path) -> None:
    rows = frame_series_rows(result)
    columns = [
        "Step",
        "Frame",
        "FrameValue",
        "Field",
        "Metric",
        "Region",
        "RegionKind",
        "Count",
        "Min",
        "Max",
        "Mean",
        "MaxAbs",
        "Location",
        "Truncated",
    ]
    with path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=columns)
        writer.writeheader()
        writer.writerows(rows)


def _markdown_report(result: dict[str, Any]) -> str:
    aggregate = result.get("aggregate", {})
    field_lines = []
    for row in extraction_summary_rows(result):
        field_lines.append(
            "- {Step} / {Field} {Metric}: max={Max}, max_abs={MaxAbs}, loc={Location}".format(**row)
        )
    field_body = "\n".join(field_lines) or "- 暂无字段统计"
    contour = result.get("viewport_image") or "未生成"
    errors = "\n".join(f"- {item}" for item in result.get("contour_errors", [])) or "- 无"
    return f"""# ODB 场变量后处理报告

## 基本信息

- Case: `{result.get("case_id")}`
- ODB: `{result.get("odb_path")}`
- 创建时间: `{result.get("created_at")}`
- 帧模式: `{result.get("frame_mode")}`
- 请求字段: `{", ".join(result.get("fields_requested", []))}`

## 关键指标

- Max Mises: `{aggregate.get("max_mises")}`
- Max PEEQ: `{aggregate.get("max_peeq")}`
- Max Displacement: `{aggregate.get("max_displacement")}`
- Max Reaction Force: `{aggregate.get("max_reaction_force")}`
- 截断字段数: `{aggregate.get("truncated_field_count")}`

## 字段统计

{field_body}

## 云图截图

{contour}

## 异常

{errors}

## 说明

本报告由 MaterialAI Workbench 通过 Abaqus MCP 从 ODB 最后一帧提取，用于把真实仿真输出沉淀为可检索、可训练的结构化结果特征。
"""


def _frame_series_markdown_report(result: dict[str, Any]) -> str:
    steps = result.get("steps", [])
    step_lines = "\n".join(
        "- `{name}`: frames `{sampled}` / `{total}`".format(
            name=item.get("name", ""),
            sampled=item.get("sampled_frame_count", 0),
            total=item.get("frame_count", 0),
        )
        for item in steps
    ) or "- 暂无 step"
    fields = ", ".join(result.get("fields_requested", []))
    return f"""# ODB 帧曲线提取报告

## 基本信息

- Case: `{result.get("case_id")}`
- ODB: `{result.get("odb_path")}`
- 创建时间: `{result.get("created_at")}`
- 后端: `{result.get("backend_used")}`
- 字段: `{fields}`
- 请求区域: `{", ".join(result.get("regions_requested", [])) or "GLOBAL"}`
- 找到区域: `{result.get("regions_found", [])}`
- 行数: `{result.get("row_count", 0)}`
- CSV: `{result.get("csv_path")}`

## Step / Frame

{step_lines}

## 用途

本报告把 ODB 中每一帧的场变量聚合为曲线表，可用于训练样本、结果趋势检查、批量案例对比和后续神经网络代理模型标签构建。
"""


def _normalize_fields(fields: list[str] | tuple[str, ...]) -> list[str]:
    result = []
    seen = set()
    for field in fields:
        item = str(field).strip().upper()
        if item and item not in seen:
            seen.add(item)
            result.append(item)
    return result or list(DEFAULT_ODB_FIELDS)


def _normalize_region_names(region_names: list[str] | tuple[str, ...]) -> list[str]:
    result = []
    seen = set()
    for region in region_names:
        item = str(region).strip()
        if item and item.upper() not in seen:
            seen.add(item.upper())
            result.append(item)
    return result


def _unique_extraction_dir(root: Path, odb_stem: str) -> Path:
    stamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    safe_stem = "".join(ch if ch.isalnum() or ch in ("-", "_") else "_" for ch in odb_stem).strip("_") or "odb"
    base = root / f"{stamp}_{safe_stem}"
    if not base.exists():
        return base
    idx = 2
    while True:
        candidate = root / f"{stamp}_{safe_stem}_{idx}"
        if not candidate.exists():
            return candidate
        idx += 1


def _max_value(current: Any, candidate: Any) -> float | None:
    values = []
    for item in (current, candidate):
        if isinstance(item, (int, float)):
            values.append(float(item))
    return max(values) if values else None


def _format_location(location: dict[str, Any]) -> str:
    parts = []
    for key in ("instance", "node_label", "element_label", "integration_point"):
        value = location.get(key)
        if value:
            parts.append(f"{key}={value}")
    return ", ".join(parts)
