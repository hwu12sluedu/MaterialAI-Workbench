"""Resumable 3D plate-hole Abaqus batch and surrogate-model pipeline."""

from __future__ import annotations

import argparse
import csv
import itertools
import json
import traceback
from dataclasses import asdict, dataclass
from datetime import datetime
from pathlib import Path
from typing import Any, Sequence

from material_ai_workbench.config import BATCHES_ROOT, CASES_ROOT
from material_ai_workbench.dataset_export import export_case_dataset
from material_ai_workbench.plate_hole_acceptance import (
    PlateHoleAcceptanceConfig,
    resume_plate_hole_acceptance,
    run_plate_hole_acceptance,
)
from material_ai_workbench.surrogate_model import compare_all_models

PLATE_HOLE_BATCH_ROOT = BATCHES_ROOT / "plate_hole"
PLAN_SCHEMA_VERSION = "1.0"
MAX_BATCH_SAMPLES = 500
SAMPLE_COLUMNS = [
    "sample_id",
    "status",
    "hole_radius",
    "yield_strength",
    "displacement",
    "acceptance_run_dir",
    "case_id",
    "case_dir",
    "max_mises_mpa",
    "max_peeq",
    "error",
]


@dataclass
class PlateHoleBatchConfig:
    name: str = "plate_hole_ml_batch"
    output_root: Path | str = PLATE_HOLE_BATCH_ROOT
    cases_root: Path | str = CASES_ROOT
    hole_radii: tuple[float, ...] = (4.0, 5.0, 6.0)
    yield_strengths: tuple[float, ...] = (250.0, 300.0, 350.0)
    displacements: tuple[float, ...] = (0.25, 0.35)
    length: float = 100.0
    width: float = 50.0
    thickness: float = 5.0
    youngs_modulus: float = 210_000.0
    poisson_ratio: float = 0.30
    tangent_modulus: float = 1_000.0
    plastic_strain_limit: float = 0.05
    mesh_size: float = 2.5
    cpus: int = 4
    backend: str = "batch"
    timeout_seconds: float = 3_600.0


@dataclass
class PlateHoleBatchPlan:
    plan_dir: Path
    plan_path: Path
    summary_csv: Path
    report_path: Path
    data: dict[str, Any]

    @property
    def samples(self) -> list[dict[str, Any]]:
        value = self.data.get("samples", [])
        return value if isinstance(value, list) else []


def create_plate_hole_batch_plan(
    config: PlateHoleBatchConfig | None = None,
) -> PlateHoleBatchPlan:
    """Create a Cartesian geometry/material/load plan without calling Abaqus."""

    cfg = config or PlateHoleBatchConfig()
    _validate_config(cfg)
    combinations = list(
        itertools.product(
            (float(value) for value in cfg.hole_radii),
            (float(value) for value in cfg.yield_strengths),
            (float(value) for value in cfg.displacements),
        )
    )
    if not combinations:
        raise ValueError(
            "At least one hole radius, yield strength and displacement is required."
        )
    if len(combinations) > MAX_BATCH_SAMPLES:
        raise ValueError(
            f"Batch contains {len(combinations)} samples; limit is {MAX_BATCH_SAMPLES}."
        )

    root = Path(cfg.output_root).expanduser().resolve()
    root.mkdir(parents=True, exist_ok=True)
    plan_dir = _unique_plan_dir(root, cfg.name)
    plan_dir.mkdir(parents=False, exist_ok=False)
    samples = []
    for index, (radius, yield_strength, displacement) in enumerate(
        combinations, start=1
    ):
        sample_id = (
            f"{index:04d}_r{_safe_number(radius)}_sy{_safe_number(yield_strength)}"
            f"_u{_safe_number(displacement)}"
        )
        samples.append(
            {
                "sample_id": sample_id,
                "status": "pending",
                "hole_radius": radius,
                "yield_strength": yield_strength,
                "displacement": displacement,
                "acceptance_run_dir": "",
                "case_id": "",
                "case_dir": "",
                "results": {},
                "error": "",
            }
        )
    now = datetime.now().isoformat(timespec="seconds")
    data = {
        "schema_version": PLAN_SCHEMA_VERSION,
        "batch_type": "abaqus_3d_plate_hole_ml",
        "name": cfg.name,
        "created_at": now,
        "updated_at": now,
        "plan_dir": str(plan_dir),
        "config": _serialize_config(cfg),
        "execution_policy": {
            "abaqus_submission_default": False,
            "requires_explicit_submit_flag": True,
        },
        "samples": samples,
        "outputs": {},
    }
    plan = _plan_from_data(plan_dir, data)
    save_plate_hole_batch_plan(plan)
    return plan


def load_plate_hole_batch_plan(plan_dir: Path | str) -> PlateHoleBatchPlan:
    path = Path(plan_dir).expanduser().resolve()
    plan_path = (
        path if path.name == "plate_hole_batch.json" else path / "plate_hole_batch.json"
    )
    data = json.loads(plan_path.read_text(encoding="utf-8"))
    if data.get("schema_version") != PLAN_SCHEMA_VERSION:
        raise ValueError(
            f"Unsupported plate-hole batch schema: {data.get('schema_version')}"
        )
    return _plan_from_data(plan_path.parent, data)


def list_plate_hole_batch_plans(
    root: Path = PLATE_HOLE_BATCH_ROOT,
) -> list[Path]:
    """Return persisted plate-hole batch folders, newest first."""

    root = Path(root)
    if not root.exists():
        return []
    return sorted(
        [
            path
            for path in root.iterdir()
            if path.is_dir() and (path / "plate_hole_batch.json").is_file()
        ],
        key=lambda path: path.stat().st_mtime,
        reverse=True,
    )


def save_plate_hole_batch_plan(plan: PlateHoleBatchPlan) -> None:
    plan.data["updated_at"] = datetime.now().isoformat(timespec="seconds")
    plan.plan_path.write_text(
        json.dumps(plan.data, indent=2, ensure_ascii=False), encoding="utf-8"
    )
    _write_summary_csv(plan)
    plan.report_path.write_text(_report_markdown(plan), encoding="utf-8")


def run_plate_hole_batch_plan(
    plan_dir: Path | str,
    *,
    execute: bool = False,
    submit_jobs: bool = False,
    archive_cases: bool = True,
    export_dataset_after: bool = False,
    train_models_after: bool = False,
    max_samples: int | None = None,
) -> PlateHoleBatchPlan:
    """Prepare or solve pending samples and optionally train RF/MLP/GBR surrogates."""

    if submit_jobs and not execute:
        raise ValueError("submit_jobs=True requires execute=True.")
    plan = load_plate_hole_batch_plan(plan_dir)
    cfg = PlateHoleBatchConfig(**plan.data["config"])
    processed = 0
    eligible_states = {
        "pending",
        "failed",
        "blocked",
        "prepared",
        "built",
        "solved",
        "postprocessed",
        "validated",
    }
    for sample in plan.samples:
        if max_samples is not None and processed >= max(0, int(max_samples)):
            break
        if sample.get("status") not in eligible_states:
            continue
        if not execute and sample.get("status") != "pending":
            continue
        _run_sample(
            plan,
            cfg,
            sample,
            execute=execute,
            submit_jobs=submit_jobs,
            archive_cases=archive_cases,
        )
        processed += 1
        save_plate_hole_batch_plan(plan)

    plan.data["last_run"] = {
        "finished_at": datetime.now().isoformat(timespec="seconds"),
        "execute": execute,
        "submit_jobs": submit_jobs,
        "archive_cases": archive_cases,
        "processed_samples": processed,
    }
    if export_dataset_after or train_models_after:
        _export_and_train(
            plan,
            train_models=train_models_after,
        )
    save_plate_hole_batch_plan(plan)
    return plan


def batch_table_rows(plan: PlateHoleBatchPlan | dict[str, Any]) -> list[dict[str, Any]]:
    data = plan.data if isinstance(plan, PlateHoleBatchPlan) else plan
    rows = []
    for sample in data.get("samples", []) or []:
        results = sample.get("results", {}) or {}
        rows.append(
            {
                "sample_id": sample.get("sample_id", ""),
                "status": sample.get("status", ""),
                "hole_radius": sample.get("hole_radius", ""),
                "yield_strength": sample.get("yield_strength", ""),
                "displacement": sample.get("displacement", ""),
                "acceptance_run_dir": sample.get("acceptance_run_dir", ""),
                "case_id": sample.get("case_id", ""),
                "case_dir": sample.get("case_dir", ""),
                "max_mises_mpa": results.get("max_mises_mpa", ""),
                "max_peeq": results.get("max_peeq", ""),
                "error": sample.get("error", ""),
            }
        )
    return rows


def _run_sample(
    plan: PlateHoleBatchPlan,
    config: PlateHoleBatchConfig,
    sample: dict[str, Any],
    *,
    execute: bool,
    submit_jobs: bool,
    archive_cases: bool,
) -> None:
    sample["status"] = "running"
    sample["started_at"] = datetime.now().isoformat(timespec="seconds")
    sample["error"] = ""
    save_plate_hole_batch_plan(plan)
    try:
        run_dir = str(sample.get("acceptance_run_dir", "")).strip()
        if run_dir:
            result = resume_plate_hole_acceptance(
                run_dir,
                execute=execute,
                submit_job=submit_jobs,
                archive_case=archive_cases,
                backend=config.backend,
            )
        else:
            acceptance_config = PlateHoleAcceptanceConfig(
                name=f"{_safe_name(config.name)}_{sample['sample_id']}",
                output_root=plan.plan_dir / "runs",
                cases_root=Path(config.cases_root),
                length=float(config.length),
                width=float(config.width),
                thickness=float(config.thickness),
                hole_radius=float(sample["hole_radius"]),
                youngs_modulus=float(config.youngs_modulus),
                poisson_ratio=float(config.poisson_ratio),
                yield_strength=float(sample["yield_strength"]),
                tangent_modulus=float(config.tangent_modulus),
                plastic_strain_limit=float(config.plastic_strain_limit),
                displacement=float(sample["displacement"]),
                mesh_size=float(config.mesh_size),
                cpus=int(config.cpus),
                backend=config.backend,
                submit_job=bool(submit_jobs),
                archive_case=bool(archive_cases),
                timeout_seconds=float(config.timeout_seconds),
            )
            result = run_plate_hole_acceptance(acceptance_config, execute=execute)
        sample["acceptance_run_dir"] = str(result.run_dir)
        sample["status"] = result.status
        sample["results"] = dict(result.manifest.get("results", {}) or {})
        sample["case_id"] = str(result.manifest.get("case_id", "") or "")
        archive_evidence = (
            (result.manifest.get("stages", {}) or {}).get("archive", {}) or {}
        ).get("evidence", {}) or {}
        sample["case_dir"] = str(archive_evidence.get("case_dir", "") or "")
        sample["completed_at"] = datetime.now().isoformat(timespec="seconds")
    except Exception as exc:
        sample["status"] = "failed"
        sample["error"] = f"{type(exc).__name__}: {exc}"
        sample["traceback"] = traceback.format_exc()
        sample["completed_at"] = datetime.now().isoformat(timespec="seconds")


def _export_and_train(plan: PlateHoleBatchPlan, *, train_models: bool) -> None:
    case_dirs = [
        Path(sample["case_dir"])
        for sample in plan.samples
        if str(sample.get("case_dir", "")).strip() and Path(sample["case_dir"]).is_dir()
    ]
    outputs = plan.data.setdefault("outputs", {})
    if not case_dirs:
        outputs["dataset_status"] = "blocked_no_archived_cases"
        return
    dataset = export_case_dataset(
        output_root=plan.plan_dir / "datasets",
        name=f"{_safe_name(plan.data.get('name', 'plate_hole'))}_training",
        case_dirs=case_dirs,
        training_only=True,
    )
    outputs.update(
        {
            "dataset_status": "ready" if dataset.case_count else "blocked_quality_gate",
            "dataset_dir": str(dataset.export_dir),
            "dataset_csv": str(dataset.dataset_csv),
            "dataset_source_case_count": dataset.source_case_count,
            "dataset_case_count": dataset.case_count,
            "dataset_skipped_case_count": dataset.skipped_case_count,
        }
    )
    if not train_models:
        return
    if dataset.case_count < 4:
        outputs["model_training_status"] = "blocked_need_at_least_4_cases"
        return
    comparison = compare_all_models(
        dataset.export_dir,
        target_column="abaqus_max_mises",
        output_root=plan.plan_dir / "surrogates",
    )
    comparison_path = plan.plan_dir / "model_comparison.json"
    comparison_path.write_text(
        json.dumps(comparison, indent=2, ensure_ascii=False), encoding="utf-8"
    )
    valid = [
        row
        for row in comparison
        if not row.get("error") and isinstance(row.get("rmse"), (int, float))
    ]
    best = min(valid, key=lambda row: float(row["rmse"])) if valid else None
    outputs.update(
        {
            "model_training_status": "completed" if valid else "failed",
            "model_comparison": str(comparison_path),
            "best_model": best,
            "neural_network_run": next(
                (
                    row.get("run_dir")
                    for row in comparison
                    if row.get("model_kind") == "mlp" and not row.get("error")
                ),
                None,
            ),
        }
    )


def _validate_config(config: PlateHoleBatchConfig) -> None:
    for name in (
        "length",
        "width",
        "thickness",
        "youngs_modulus",
        "mesh_size",
        "timeout_seconds",
    ):
        if float(getattr(config, name)) <= 0:
            raise ValueError(f"{name} must be positive.")
    if not -1.0 < float(config.poisson_ratio) < 0.5:
        raise ValueError("poisson_ratio must be between -1 and 0.5.")
    if config.backend not in {"batch", "mcp"}:
        raise ValueError("backend must be 'batch' or 'mcp'.")
    if int(config.cpus) < 1:
        raise ValueError("cpus must be at least 1.")
    for radius in config.hole_radii:
        if float(radius) <= 0 or float(radius) * 2.2 >= float(config.width):
            raise ValueError(f"Invalid hole radius for plate width: {radius}")
        if float(config.mesh_size) > float(radius):
            raise ValueError(f"mesh_size exceeds hole radius: {radius}")
    if any(float(value) <= 0 for value in config.yield_strengths):
        raise ValueError("yield_strengths must be positive.")
    if any(float(value) <= 0 for value in config.displacements):
        raise ValueError("displacements must be positive.")


def _serialize_config(config: PlateHoleBatchConfig) -> dict[str, Any]:
    payload = asdict(config)
    payload["output_root"] = str(Path(config.output_root).expanduser().resolve())
    payload["cases_root"] = str(Path(config.cases_root).expanduser().resolve())
    for key in ("hole_radii", "yield_strengths", "displacements"):
        payload[key] = list(payload[key])
    return payload


def _plan_from_data(plan_dir: Path, data: dict[str, Any]) -> PlateHoleBatchPlan:
    return PlateHoleBatchPlan(
        plan_dir=plan_dir,
        plan_path=plan_dir / "plate_hole_batch.json",
        summary_csv=plan_dir / "plate_hole_batch_summary.csv",
        report_path=plan_dir / "plate_hole_batch_report.md",
        data=data,
    )


def _write_summary_csv(plan: PlateHoleBatchPlan) -> None:
    with plan.summary_csv.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=SAMPLE_COLUMNS)
        writer.writeheader()
        writer.writerows(
            [
                {key: row.get(key, "") for key in SAMPLE_COLUMNS}
                for row in batch_table_rows(plan)
            ]
        )


def _report_markdown(plan: PlateHoleBatchPlan) -> str:
    counts: dict[str, int] = {}
    for sample in plan.samples:
        status = str(sample.get("status", "unknown"))
        counts[status] = counts.get(status, 0) + 1
    status_lines = "\n".join(
        f"- `{key}`: {value}" for key, value in sorted(counts.items())
    )
    output_lines = (
        "\n".join(
            f"- `{key}`: `{value}`"
            for key, value in plan.data.get("outputs", {}).items()
        )
        or "- 暂无数据集或代理模型输出。"
    )
    return f"""# 3D 带孔板批量仿真与代理模型

- 批次: `{plan.data.get('name')}`
- 样本数: `{len(plan.samples)}`
- 更新时间: `{plan.data.get('updated_at')}`

## 状态

{status_lines}

## 输出

{output_lines}

## 证据边界

`prepared` 只表示脚本已生成；`archived` 表示真实 ODB 已后处理并归档。
只有通过案例质量门的样本会进入训练数据集。MLP 结果用于代理模型实验，不替代独立 Abaqus 验证。
"""


def _unique_plan_dir(root: Path, name: str) -> Path:
    return root / f"{datetime.now().strftime('%Y%m%d_%H%M%S_%f')}_{_safe_name(name)}"


def _safe_name(value: Any) -> str:
    text = str(value or "")
    return (
        "".join(
            char if char.isalnum() or char in {"-", "_"} else "_" for char in text
        ).strip("_")
        or "plate_hole_batch"
    )


def _safe_number(value: float) -> str:
    return f"{float(value):g}".replace("-", "m").replace(".", "p")


def _parse_values(value: str) -> tuple[float, ...]:
    return tuple(
        float(item.strip())
        for item in value.replace("，", ",").split(",")
        if item.strip()
    )


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    subparsers = parser.add_subparsers(dest="command", required=True)
    create = subparsers.add_parser("create")
    create.add_argument("--name", default="plate_hole_ml_batch")
    create.add_argument("--hole-radii", default="4,5,6")
    create.add_argument("--yield-strengths", default="250,300,350")
    create.add_argument("--displacements", default="0.25,0.35")
    create.add_argument("--backend", choices=("batch", "mcp"), default="batch")
    create.add_argument("--output-root", type=Path, default=PLATE_HOLE_BATCH_ROOT)
    create.add_argument("--cases-root", type=Path, default=CASES_ROOT)

    run = subparsers.add_parser("run")
    run.add_argument("plan_dir", type=Path)
    run.add_argument("--execute", action="store_true")
    run.add_argument("--submit-jobs", action="store_true")
    run.add_argument("--no-archive", action="store_true")
    run.add_argument("--export-dataset", action="store_true")
    run.add_argument("--train-models", action="store_true")
    run.add_argument("--max-samples", type=int)

    status = subparsers.add_parser("status")
    status.add_argument("plan_dir", type=Path)
    return parser


def main(argv: Sequence[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    try:
        if args.command == "create":
            plan = create_plate_hole_batch_plan(
                PlateHoleBatchConfig(
                    name=args.name,
                    output_root=args.output_root,
                    cases_root=args.cases_root,
                    hole_radii=_parse_values(args.hole_radii),
                    yield_strengths=_parse_values(args.yield_strengths),
                    displacements=_parse_values(args.displacements),
                    backend=args.backend,
                )
            )
        elif args.command == "run":
            plan = run_plate_hole_batch_plan(
                args.plan_dir,
                execute=args.execute,
                submit_jobs=args.submit_jobs,
                archive_cases=not args.no_archive,
                export_dataset_after=args.export_dataset,
                train_models_after=args.train_models,
                max_samples=args.max_samples,
            )
        else:
            plan = load_plate_hole_batch_plan(args.plan_dir)
    except Exception as exc:
        print(json.dumps({"ok": False, "error": str(exc)}, ensure_ascii=False))
        return 2
    print(
        json.dumps(
            {
                "ok": True,
                "plan_dir": str(plan.plan_dir),
                "sample_count": len(plan.samples),
                "status_counts": _status_counts(plan),
                "outputs": plan.data.get("outputs", {}),
            },
            indent=2,
            ensure_ascii=False,
        )
    )
    return 0


def _status_counts(plan: PlateHoleBatchPlan) -> dict[str, int]:
    counts: dict[str, int] = {}
    for sample in plan.samples:
        status = str(sample.get("status", "unknown"))
        counts[status] = counts.get(status, 0) + 1
    return counts


if __name__ == "__main__":
    raise SystemExit(main())
