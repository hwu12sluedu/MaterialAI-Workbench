"""Prepare a traceable Abaqus run workspace from grounded historical cases."""

from __future__ import annotations

import json
import shutil
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from typing import Any

from material_ai_workbench.case_library import CASES_ROOT, load_case_summary
from material_ai_workbench.config import RUNS_ROOT
from material_ai_workbench.task_schema import build_executable_plan

CASE_PLAN_ROOT = RUNS_ROOT / "case_based_plans"
MAX_COPIED_INPUT_BYTES = 64 * 1024 * 1024
EDITABLE_INPUT_EXTENSIONS = {
    ".inp",
    ".cae",
    ".inc",
    ".py",
    ".for",
    ".f",
    ".f90",
    ".f95",
    ".json",
    ".yaml",
    ".yml",
    ".csv",
}


@dataclass(frozen=True)
class CaseBasedPlanResult:
    run_dir: Path
    manifest_path: Path
    review_path: Path
    copied_inputs: tuple[Path, ...]
    reference_case_ids: tuple[str, ...]
    status: str


def prepare_case_based_plan(
    payload: dict[str, Any],
    *,
    cases_root: Path = CASES_ROOT,
    output_root: Path = CASE_PLAN_ROOT,
) -> CaseBasedPlanResult:
    """Clone editable inputs and write a reviewable, non-submitted job plan."""

    executable = build_executable_plan(payload)
    if not executable.schema.valid:
        details = {
            "missing_sections": executable.schema.missing_sections,
            "missing_fields": executable.schema.missing_fields,
            "warnings": executable.schema.warnings,
        }
        raise ValueError(f"Invalid case-based task payload: {details}")
    if executable.schema.task_type != "case_based_simulation":
        raise ValueError("Expected task_type 'case_based_simulation'.")

    case_plan = dict(executable.payload.get("case_plan", {}) or {})
    grounding = dict(executable.payload.get("grounding", {}) or {})
    requested_ids = [str(value) for value in case_plan.get("reference_case_ids", [])]
    allowed_ids = {str(value) for value in grounding.get("retrieved_case_ids", [])}
    if not requested_ids or any(
        case_id not in allowed_ids for case_id in requested_ids
    ):
        raise ValueError(
            "Reference cases must come from the attached grounding evidence."
        )

    output_root = Path(output_root).expanduser().resolve()
    output_root.mkdir(parents=True, exist_ok=True)
    run_dir = _unique_run_dir(output_root, case_plan.get("objective", "case_plan"))
    inputs_root = run_dir / "inputs"
    inputs_root.mkdir(parents=True)

    copied_rows: list[dict[str, Any]] = []
    skipped_rows: list[dict[str, Any]] = []
    reference_rows: list[dict[str, Any]] = []
    copied_paths: list[Path] = []
    for case_id in requested_ids:
        summary = load_case_summary(Path(cases_root) / case_id)
        reference_rows.append(
            {
                "case_id": summary.case_id,
                "title": summary.title,
                "source_fingerprint": summary.source_fingerprint,
                "quality": summary.quality,
                "units": summary.units,
            }
        )
        case_input_root = inputs_root / _safe_name(summary.case_id)
        for item in summary.files:
            source = Path(item.path)
            reason = _copy_skip_reason(item, source)
            if reason:
                skipped_rows.append(
                    {
                        "case_id": summary.case_id,
                        "relative_path": item.relative_path,
                        "reason": reason,
                    }
                )
                continue
            relative = Path(item.relative_path)
            destination = case_input_root / relative
            destination.parent.mkdir(parents=True, exist_ok=True)
            shutil.copy2(source, destination)
            copied_paths.append(destination)
            copied_rows.append(
                {
                    "case_id": summary.case_id,
                    "source_relative_path": item.relative_path,
                    "prepared_relative_path": str(destination.relative_to(run_dir)),
                    "size_bytes": item.size_bytes,
                    "source_fingerprint": item.fingerprint,
                    "fingerprint_mode": item.fingerprint_mode,
                }
            )

    if not any(path.suffix.lower() in {".inp", ".cae"} for path in copied_paths):
        shutil.rmtree(run_dir)
        raise ValueError("No readable INP or CAE model input could be prepared.")

    now = datetime.now().isoformat(timespec="seconds")
    sanitized_payload = json.loads(json.dumps(executable.payload))
    sanitized_payload["case_plan"]["submit_job"] = False
    sanitized_payload["execution_policy"] = {
        "mode": "prepared_inputs_only",
        "abaqus_submission_allowed": False,
        "requires_user_confirmation": True,
    }
    manifest = {
        "schema_version": "1.0",
        "plan_type": "grounded_case_based_simulation",
        "status": "prepared_unmodified",
        "created_at": now,
        "run_dir": str(run_dir),
        "task": sanitized_payload,
        "reference_cases": reference_rows,
        "copied_inputs": copied_rows,
        "skipped_files": skipped_rows,
        "safety": {
            "source_cases_modified": False,
            "input_parameters_modified": False,
            "abaqus_submitted": False,
            "requires_difference_review": True,
            "requires_user_confirmation": True,
        },
    }
    manifest_path = run_dir / "case_plan_manifest.json"
    manifest_path.write_text(
        json.dumps(manifest, indent=2, ensure_ascii=False), encoding="utf-8"
    )
    review_path = run_dir / "CHANGE_REVIEW_CN.md"
    review_path.write_text(_review_markdown(manifest), encoding="utf-8")
    return CaseBasedPlanResult(
        run_dir=run_dir,
        manifest_path=manifest_path,
        review_path=review_path,
        copied_inputs=tuple(copied_paths),
        reference_case_ids=tuple(requested_ids),
        status="prepared_unmodified",
    )


def _copy_skip_reason(item: Any, source: Path) -> str:
    if str(getattr(item, "extension", "")).lower() not in EDITABLE_INPUT_EXTENSIONS:
        return "not_editable_input"
    if int(getattr(item, "size_bytes", 0) or 0) > MAX_COPIED_INPUT_BYTES:
        return "input_exceeds_64MiB_copy_limit"
    relative = Path(str(getattr(item, "relative_path", "")))
    if relative.is_absolute() or ".." in relative.parts:
        return "unsafe_relative_path"
    if not source.is_file():
        return "source_missing"
    return ""


def _unique_run_dir(root: Path, objective: Any) -> Path:
    stem = _safe_name(str(objective))[:48] or "case_plan"
    stamp = datetime.now().strftime("%Y%m%d_%H%M%S_%f")
    path = root / f"{stamp}_{stem}"
    path.mkdir(parents=False, exist_ok=False)
    return path


def _safe_name(value: str) -> str:
    return "".join(
        char if char.isalnum() or char in {"-", "_"} else "_" for char in value
    ).strip("_")


def _review_markdown(manifest: dict[str, Any]) -> str:
    task = manifest["task"]
    plan = task["case_plan"]
    changes = plan.get("changes", []) or []
    change_lines = []
    for item in changes:
        if not isinstance(item, dict):
            change_lines.append(f"- {item}")
            continue
        change_lines.append(
            "- `{parameter}`: `{before}` -> `{after}` {unit}".format(
                parameter=item.get("parameter", "unknown"),
                before=item.get("from", "未提供"),
                after=item.get("to", "未提供"),
                unit=item.get("unit", ""),
            )
        )
    if not change_lines:
        change_lines.append("- 尚未定义参数变化，禁止提交求解。")
    references = "\n".join(
        f"- `{item['case_id']}`: {item['title']}"
        for item in manifest["reference_cases"]
    )
    return f"""# 历史案例复用差异审查

## 当前状态

- 状态: `{manifest['status']}`
- Abaqus 已提交: `False`
- 原案例已修改: `False`
- 输入参数已自动修改: `False`
- 单位制: `{plan.get('unit_system', '')}`

## 参考案例

{references}

## 目标

{plan.get('objective', '')}

## 待实施变化

{chr(10).join(change_lines)}

## 提交前检查

1. 在复制的 INP/CAE 中实施并复核上述变化。
2. 核对材料、单位制、截面、接触、边界条件、载荷、网格和输出请求。
3. 生成新 Job 名称，禁止覆盖历史 ODB。
4. 在客户端单独勾选确认后，才允许提交 Abaqus。
"""
