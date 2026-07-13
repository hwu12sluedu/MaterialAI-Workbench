"""Composite RVE dataset and surrogate utilities."""

from __future__ import annotations

import csv
import json
import logging
import math
import pickle
from dataclasses import asdict, dataclass
from datetime import datetime
from pathlib import Path
from typing import Any

import matplotlib

matplotlib.use("Agg", force=True)

import matplotlib.pyplot as plt
import numpy as np
from sklearn.ensemble import RandomForestRegressor
from sklearn.metrics import mean_absolute_error, mean_squared_error, r2_score
from sklearn.model_selection import train_test_split
from sklearn.neural_network import MLPRegressor
from sklearn.pipeline import Pipeline
from sklearn.preprocessing import StandardScaler

from material_ai_workbench.composite_workflow import CompositePlateConfig, run_composite_plate_workflow
from material_ai_workbench.config import COMPOSITE_BATCH_ROOT, COMPOSITE_SURROGATE_ROOT


DEFAULT_COMPOSITE_TARGET = "max_stress_near_hole_estimate_mpa"
_log = logging.getLogger(__name__)
COMPOSITE_TARGET_COLUMNS = {
    "E1",
    "E2",
    "E3",
    "G12",
    "G13",
    "G23",
    "stress_concentration_factor_estimate",
    "nominal_axial_stress_mpa",
    "max_stress_near_hole_estimate_mpa",
    "net_section_force_n",
    "gross_section_force_n",
}


@dataclass
class CompositeBatchConfig:
    name: str = "composite_rve_sweep"
    output_dir: Path = COMPOSITE_BATCH_ROOT
    sample_count: int = 8
    random_seed: int = 23
    vf_min: float = 0.35
    vf_max: float = 0.65
    interface_efficiency_min: float = 0.75
    interface_efficiency_max: float = 1.0
    hole_radius_min: float = 3.0
    hole_radius_max: float = 7.0
    fiber_e: float = 230_000.0
    fiber_nu: float = 0.20
    matrix_e: float = 3_500.0
    matrix_nu: float = 0.35
    length: float = 120.0
    width: float = 40.0
    thickness: float = 2.0
    applied_strain: float = 0.003
    mesh_size: float = 2.0
    micro_fiber_count: int = 12
    micro_nx: int = 4
    micro_ny: int = 12
    micro_nz: int = 12
    run_abaqus: bool = False
    run_pbc_homogenization: bool = False
    use_abaqus_homogenization: bool = False


@dataclass
class CompositeBatchPlan:
    plan_dir: Path
    plan_path: Path
    sample_csv: Path
    dataset_csv: Path
    report_path: Path
    data: dict[str, Any]


@dataclass
class CompositeSurrogateRun:
    run_dir: Path
    model_path: Path
    metrics_path: Path
    predictions_csv: Path
    plot_path: Path
    report_path: Path
    metrics: dict[str, Any]


def create_composite_batch_plan(config: CompositeBatchConfig) -> CompositeBatchPlan:
    _validate_batch_config(config)
    plan_dir = _unique_dir(Path(config.output_dir), config.name)
    plan_dir.mkdir(parents=True, exist_ok=False)
    samples = _sample_composite_configs(config)
    plan_path = plan_dir / "composite_batch_plan.json"
    sample_csv = plan_dir / "samples.csv"
    dataset_csv = plan_dir / "composite_dataset.csv"
    report_path = plan_dir / "composite_batch_report.md"
    data = {
        "created_at": datetime.now().isoformat(timespec="seconds"),
        "config": _json_ready(asdict(config)),
        "plan_dir": str(plan_dir),
        "samples": samples,
        "outputs": {
            "sample_csv": str(sample_csv),
            "dataset_csv": str(dataset_csv),
            "report": str(report_path),
        },
    }
    plan_path.write_text(json.dumps(data, indent=2), encoding="utf-8")
    _write_rows(sample_csv, samples)
    report_path.write_text(_batch_report(data), encoding="utf-8")
    return CompositeBatchPlan(plan_dir, plan_path, sample_csv, dataset_csv, report_path, data)


def list_composite_batch_plans(root: Path = COMPOSITE_BATCH_ROOT) -> list[Path]:
    if not root.exists():
        return []
    return sorted(
        [path for path in root.iterdir() if path.is_dir() and (path / "composite_batch_plan.json").exists()],
        key=lambda item: item.stat().st_mtime,
        reverse=True,
    )


def load_composite_batch_plan(plan_dir: Path | str) -> CompositeBatchPlan:
    root = Path(plan_dir)
    plan_path = root / "composite_batch_plan.json"
    data = json.loads(plan_path.read_text(encoding="utf-8"))
    outputs = data.get("outputs", {})
    return CompositeBatchPlan(
        plan_dir=root,
        plan_path=plan_path,
        sample_csv=Path(outputs.get("sample_csv", root / "samples.csv")),
        dataset_csv=Path(outputs.get("dataset_csv", root / "composite_dataset.csv")),
        report_path=Path(outputs.get("report", root / "composite_batch_report.md")),
        data=data,
    )


def run_composite_batch_plan(plan_dir: Path | str, *, max_samples: int | None = None) -> CompositeBatchPlan:
    plan = load_composite_batch_plan(plan_dir)
    samples = list(plan.data.get("samples", []))
    runs_dir = plan.plan_dir / "runs"
    runs_dir.mkdir(parents=True, exist_ok=True)
    processed = 0
    for sample in samples:
        if max_samples is not None and processed >= max_samples:
            break
        if sample.get("status") == "completed":
            continue
        config = _config_from_sample(sample, runs_dir)
        try:
            result = run_composite_plate_workflow(config)
            sample["status"] = "completed"
            sample["run_dir"] = str(result.run_dir)
            sample["dataset_row"] = str(result.dataset_csv)
            sample["report"] = str(result.report_path)
        except Exception as exc:
            sample["status"] = "failed"
            sample["error"] = str(exc)
        processed += 1

    plan.data["samples"] = samples
    plan.data["updated_at"] = datetime.now().isoformat(timespec="seconds")
    plan.plan_path.write_text(json.dumps(plan.data, indent=2), encoding="utf-8")
    _write_rows(plan.sample_csv, samples)
    build_composite_dataset(plan.plan_dir, plan.dataset_csv)
    plan.report_path.write_text(_batch_report(plan.data), encoding="utf-8")
    return load_composite_batch_plan(plan.plan_dir)


def build_composite_dataset(plan_dir: Path | str, output_csv: Path | str | None = None) -> Path:
    root = Path(plan_dir)
    output = Path(output_csv) if output_csv else root / "composite_dataset.csv"
    row_files = sorted(root.glob("runs/*/composite_plate_dataset_row.csv"))
    rows: list[dict[str, Any]] = []
    for row_file in row_files:
        with row_file.open("r", encoding="utf-8", newline="") as handle:
            for row in csv.DictReader(handle):
                row["run_dir"] = str(row_file.parent)
                rows.append(row)
    if not rows:
        output.write_text("", encoding="utf-8")
        return output
    fieldnames = sorted({key for row in rows for key in row.keys()})
    with output.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(rows)
    return output


def train_composite_surrogate(
    dataset_csv: Path | str,
    *,
    target_column: str = DEFAULT_COMPOSITE_TARGET,
    model_kind: str = "random_forest",
    output_root: Path = COMPOSITE_SURROGATE_ROOT,
    random_state: int = 42,
    uncertainty: str = "none",
) -> CompositeSurrogateRun:
    dataset = Path(dataset_csv)
    rows = _read_rows(dataset)
    if not rows:
        raise ValueError("Composite dataset is empty.")
    if target_column not in rows[0]:
        raise ValueError(f"Target column not found: {target_column}")
    clean_rows = [row for row in rows if _to_float(row.get(target_column)) is not None]
    if not clean_rows:
        raise ValueError(f"No numeric target values for {target_column}.")

    feature_names = _numeric_feature_names(clean_rows, target_column)
    x = np.asarray([[float(row[name]) for name in feature_names] for row in clean_rows], dtype=float)
    y = np.asarray([float(row[target_column]) for row in clean_rows], dtype=float)
    model_name = _normalize_model_kind(model_kind)
    model, predictions, eval_indices, evaluation_mode = _fit_composite_model(x, y, model_name, random_state)

    # Uncertainty quantification via ensemble std (RandomForest only)
    unc_payload = None
    if uncertainty == "ensemble" and model_name == "random_forest":
        try:
            tree_preds = np.asarray([tree.predict(x) for tree in model.estimators_], dtype=float)
            std = np.std(tree_preds, axis=0)
            mean = np.mean(tree_preds, axis=0)
            unc_payload = {"std": std, "lower": mean - 1.64 * std, "upper": mean + 1.64 * std}
        except Exception as exc:
            _log.warning("Composite surrogate ensemble uncertainty failed: %s", exc)

    run_dir = _unique_dir(output_root, f"{dataset.stem}_{target_column}_{model_name}")
    run_dir.mkdir(parents=True, exist_ok=False)
    model_path = run_dir / "composite_surrogate_model.pkl"
    metrics_path = run_dir / "composite_surrogate_metrics.json"
    predictions_csv = run_dir / "predictions.csv"
    plot_path = run_dir / "prediction_vs_truth.png"
    report_path = run_dir / "composite_surrogate_report.md"
    metrics = _surrogate_metrics(dataset, target_column, model_name, feature_names, y, predictions, eval_indices, evaluation_mode)

    # Add uncertainty metrics
    if unc_payload:
        metrics["uncertainty"] = "ensemble"
        metrics["prediction_interval_mean_half_width"] = float(np.mean((unc_payload["upper"] - unc_payload["lower"]) / 2.0))
        metrics["prediction_interval_coverage"] = float(np.mean((y >= unc_payload["lower"]) & (y <= unc_payload["upper"])))
    else:
        metrics["uncertainty"] = "none"
        metrics["prediction_interval_mean_half_width"] = None
        metrics["prediction_interval_coverage"] = None

    with model_path.open("wb") as handle:
        pickle.dump({"model": model, "feature_names": feature_names}, handle)
    metrics_path.write_text(json.dumps(metrics, indent=2), encoding="utf-8")
    _write_predictions(predictions_csv, clean_rows, target_column, y, predictions, eval_indices, unc_payload)
    _plot_prediction(plot_path, target_column, y, predictions, eval_indices, unc_payload)
    report_path.write_text(_surrogate_report(metrics, predictions_csv, plot_path), encoding="utf-8")
    return CompositeSurrogateRun(run_dir, model_path, metrics_path, predictions_csv, plot_path, report_path, metrics)


def list_composite_surrogate_runs(root: Path = COMPOSITE_SURROGATE_ROOT) -> list[Path]:
    if not root.exists():
        return []
    runs = [path for path in root.iterdir() if path.is_dir() and (path / "composite_surrogate_metrics.json").exists()]
    return sorted(runs, key=lambda item: item.stat().st_mtime, reverse=True)


def composite_surrogate_comparison_rows(
    runs: list[Path | str] | None = None,
    *,
    dataset_csv: Path | str | None = None,
    target_column: str | None = None,
) -> list[dict[str, Any]]:
    selected_runs = [Path(item) for item in runs] if runs is not None else list_composite_surrogate_runs()
    dataset_filter = Path(dataset_csv).expanduser().resolve() if dataset_csv else None
    rows: list[dict[str, Any]] = []
    for run_dir in selected_runs:
        metrics_path = Path(run_dir) / "composite_surrogate_metrics.json"
        if not metrics_path.exists():
            continue
        try:
            metrics = json.loads(metrics_path.read_text(encoding="utf-8"))
        except Exception:
            continue
        metrics_dataset = Path(str(metrics.get("dataset_csv", ""))).expanduser().resolve() if metrics.get("dataset_csv") else None
        if dataset_filter and metrics_dataset != dataset_filter:
            continue
        if target_column and metrics.get("target_column") != target_column:
            continue
        rows.append(
            {
                "run_dir": str(Path(run_dir).resolve()),
                "run": Path(run_dir).name,
                "dataset_csv": str(metrics_dataset) if metrics_dataset else "",
                "target_column": metrics.get("target_column", ""),
                "model_kind": metrics.get("model_kind", ""),
                "sample_count": metrics.get("sample_count"),
                "evaluation_mode": metrics.get("evaluation_mode", ""),
                "mae": metrics.get("mae"),
                "rmse": metrics.get("rmse"),
                "r2": metrics.get("r2"),
                "uncertainty": metrics.get("uncertainty", ""),
                "prediction_interval_mean_half_width": metrics.get("prediction_interval_mean_half_width"),
                "prediction_interval_coverage": metrics.get("prediction_interval_coverage"),
                "created_at": metrics.get("created_at", ""),
                "quality_note": metrics.get("quality_note", ""),
            }
        )
    return sorted(rows, key=_comparison_sort_key)


def _sample_composite_configs(config: CompositeBatchConfig) -> list[dict[str, Any]]:
    rng = np.random.default_rng(config.random_seed)
    samples: list[dict[str, Any]] = []
    for idx in range(config.sample_count):
        vf = float(rng.uniform(config.vf_min, config.vf_max))
        eta = float(rng.uniform(config.interface_efficiency_min, config.interface_efficiency_max))
        hole = float(rng.uniform(config.hole_radius_min, config.hole_radius_max))
        samples.append(
            {
                "sample_id": f"{idx + 1:04d}",
                "name": f"{config.name}_{idx + 1:04d}",
                "status": "pending",
                "fiber_volume_fraction": round(vf, 6),
                "interface_efficiency": round(eta, 6),
                "hole_radius": round(hole, 6),
                "fiber_e": config.fiber_e,
                "fiber_nu": config.fiber_nu,
                "matrix_e": config.matrix_e,
                "matrix_nu": config.matrix_nu,
                "length": config.length,
                "width": config.width,
                "thickness": config.thickness,
                "applied_strain": config.applied_strain,
                "mesh_size": config.mesh_size,
                "micro_fiber_count": config.micro_fiber_count,
                "micro_nx": config.micro_nx,
                "micro_ny": config.micro_ny,
                "micro_nz": config.micro_nz,
                "random_seed": config.random_seed + idx,
                "run_abaqus": config.run_abaqus,
                "run_pbc_homogenization": config.run_pbc_homogenization,
                "use_abaqus_homogenization": config.use_abaqus_homogenization,
            }
        )
    return samples


def _config_from_sample(sample: dict[str, Any], output_dir: Path) -> CompositePlateConfig:
    return CompositePlateConfig(
        name=str(sample["name"]),
        output_dir=output_dir,
        fiber_volume_fraction=float(sample["fiber_volume_fraction"]),
        fiber_e=float(sample["fiber_e"]),
        fiber_nu=float(sample["fiber_nu"]),
        matrix_e=float(sample["matrix_e"]),
        matrix_nu=float(sample["matrix_nu"]),
        interface_efficiency=float(sample["interface_efficiency"]),
        length=float(sample["length"]),
        width=float(sample["width"]),
        thickness=float(sample["thickness"]),
        hole_radius=float(sample["hole_radius"]),
        applied_strain=float(sample["applied_strain"]),
        mesh_size=float(sample["mesh_size"]),
        micro_fiber_count=int(sample["micro_fiber_count"]),
        micro_nx=int(sample["micro_nx"]),
        micro_ny=int(sample["micro_ny"]),
        micro_nz=int(sample["micro_nz"]),
        random_seed=int(sample["random_seed"]),
        run_pbc_homogenization=bool(sample.get("run_pbc_homogenization", False)),
        use_abaqus_homogenization=bool(sample.get("use_abaqus_homogenization", False)),
        run_abaqus=bool(sample.get("run_abaqus", False)),
    )


def _fit_composite_model(
    x: np.ndarray,
    y: np.ndarray,
    model_name: str,
    random_state: int,
) -> tuple[Any, np.ndarray, list[int], str]:
    model: Any
    if model_name == "mlp":
        model = Pipeline(
            [
                ("scaler", StandardScaler()),
                ("mlp", MLPRegressor(hidden_layer_sizes=(32, 16), solver="lbfgs", max_iter=1000, random_state=random_state)),
            ]
        )
    else:
        model = RandomForestRegressor(n_estimators=200, random_state=random_state, min_samples_leaf=1)

    if len(y) >= 4:
        indices = np.arange(len(y))
        train_idx, test_idx = train_test_split(indices, test_size=max(1, math.ceil(len(y) * 0.25)), random_state=random_state)
        model.fit(x[train_idx], y[train_idx])
        return model, np.asarray(model.predict(x), dtype=float), [int(idx) for idx in test_idx], "holdout"
    model.fit(x, y)
    return model, np.asarray(model.predict(x), dtype=float), list(range(len(y))), "training_set_only"


def _surrogate_metrics(
    dataset_csv: Path,
    target_column: str,
    model_kind: str,
    feature_names: list[str],
    targets: np.ndarray,
    predictions: np.ndarray,
    eval_indices: list[int],
    evaluation_mode: str,
) -> dict[str, Any]:
    eval_targets = targets[eval_indices]
    eval_predictions = predictions[eval_indices]
    mae = float(mean_absolute_error(eval_targets, eval_predictions))
    rmse = float(mean_squared_error(eval_targets, eval_predictions) ** 0.5)
    r2 = float(r2_score(eval_targets, eval_predictions)) if len(eval_indices) >= 2 else None
    return {
        "created_at": datetime.now().isoformat(timespec="seconds"),
        "dataset_csv": str(dataset_csv),
        "target_column": target_column,
        "model_kind": model_kind,
        "evaluation_mode": evaluation_mode,
        "sample_count": int(len(targets)),
        "evaluated_sample_count": int(len(eval_indices)),
        "feature_names": feature_names,
        "mae": mae,
        "rmse": rmse,
        "r2": r2,
        "quality_note": "样本少时仅验证流程；工业预测精度需要更多 Abaqus/RVE 标签。",
    }


def _numeric_feature_names(rows: list[dict[str, str]], target_column: str) -> list[str]:
    excluded = set(COMPOSITE_TARGET_COLUMNS) | {target_column, "run_dir", "case_type"}
    names: list[str] = []
    for key in rows[0].keys():
        if key in excluded:
            continue
        if all(_to_float(row.get(key)) is not None for row in rows):
            names.append(key)
    if not names:
        raise ValueError("No numeric feature columns found.")
    return names


def _write_predictions(path: Path, rows: list[dict[str, str]], target_column: str, y: np.ndarray, predictions: np.ndarray, eval_indices: list[int], unc: dict | None = None) -> None:
    eval_set = set(eval_indices)
    fieldnames = ["row", "run_dir", "truth", "prediction", "error", "evaluated"]
    if unc:
        fieldnames.extend(["lower", "upper", "std"])
    with path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=fieldnames)
        writer.writeheader()
        for idx, (row, truth, pred) in enumerate(zip(rows, y, predictions)):
            d = {
                "row": idx,
                "run_dir": row.get("run_dir", ""),
                "truth": float(truth),
                "prediction": float(pred),
                "error": float(pred) - float(truth),
                "evaluated": idx in eval_set,
            }
            if unc:
                d["lower"] = float(unc["lower"][idx])
                d["upper"] = float(unc["upper"][idx])
                d["std"] = float(unc["std"][idx])
            writer.writerow(d)


def _plot_prediction(path: Path, target_column: str, y: np.ndarray, predictions: np.ndarray, eval_indices: list[int], unc: dict | None = None) -> None:
    fig, ax = plt.subplots(figsize=(6, 5), dpi=140)
    if unc and "std" in unc and "lower" in unc:
        ax.errorbar(y, predictions, yerr=1.64 * unc["std"], fmt="o", color="#2563eb",
                    ecolor="#93c5fd", alpha=0.7, capsize=2, markersize=6)
    else:
        ax.scatter(y, predictions, color="#2563eb")
    ax.scatter(y[eval_indices], predictions[eval_indices], facecolors="none", edgecolors="#dc2626", s=90)
    limits = float(min(np.min(y), np.min(predictions))), float(max(np.max(y), np.max(predictions)))
    if abs(limits[1] - limits[0]) < 1e-12:
        limits = (limits[0] - 1, limits[1] + 1)
    ax.plot(limits, limits, color="#111827", linestyle="--")
    ax.set_xlabel("Truth")
    ax.set_ylabel("Prediction")
    ax.set_title(f"Composite surrogate: {target_column}")
    ax.grid(True, alpha=0.25)
    fig.tight_layout()
    try:
        fig.savefig(str(path))
    except Exception:
        pass
    plt.close(fig)


def _surrogate_report(metrics: dict[str, Any], predictions_csv: Path, plot_path: Path) -> str:
    return f"""# 复合材料代理模型报告

## 任务

- 数据集：`{metrics['dataset_csv']}`
- 目标：`{metrics['target_column']}`
- 模型：`{metrics['model_kind']}`
- 样本数：`{metrics['sample_count']}`
- 评估方式：`{metrics['evaluation_mode']}`

## 指标

- MAE：`{metrics['mae']}`
- RMSE：`{metrics['rmse']}`
- R2：`{metrics['r2']}`

## 输出

- 预测明细：`{predictions_csv}`
- 预测图：`{plot_path}`

## 说明

{metrics['quality_note']}
"""


def _comparison_sort_key(row: dict[str, Any]) -> tuple[Any, ...]:
    rmse = _sort_number(row.get("rmse"))
    mae = _sort_number(row.get("mae"))
    r2 = _sort_number(row.get("r2"), reverse=True)
    return (rmse, mae, r2, str(row.get("run", "")))


def _sort_number(value: Any, *, reverse: bool = False) -> float:
    try:
        number = float(value)
    except (TypeError, ValueError):
        return -math.inf if reverse else math.inf
    if not math.isfinite(number):
        return -math.inf if reverse else math.inf
    return -number if reverse else number


def _batch_report(data: dict[str, Any]) -> str:
    samples = data.get("samples", [])
    counts: dict[str, int] = {}
    for sample in samples:
        status = str(sample.get("status", "unknown"))
        counts[status] = counts.get(status, 0) + 1
    return f"""# 复合材料批量数据计划

## 概况

- 样本数：`{len(samples)}`
- Pending：`{counts.get('pending', 0)}`
- Completed：`{counts.get('completed', 0)}`
- Failed：`{counts.get('failed', 0)}`

## 作用

这个批量计划用于生成复合材料微观 RVE、phase map、宏观带孔板估算标签和 Abaqus 脚本。后续可以把其中的估算标签替换为真实 RVE/PBC ODB 提取标签。
"""


def _validate_batch_config(config: CompositeBatchConfig) -> None:
    if config.sample_count < 1:
        raise ValueError("sample_count must be positive.")
    if not 0.05 <= config.vf_min <= config.vf_max <= 0.8:
        raise ValueError("fiber volume fraction range must stay within 0.05..0.8.")
    if not 0.1 <= config.interface_efficiency_min <= config.interface_efficiency_max <= 1.5:
        raise ValueError("interface efficiency range must stay within 0.1..1.5.")
    if config.hole_radius_min <= 0 or config.hole_radius_max >= config.width / 2.2:
        raise ValueError("hole radius range is invalid for the plate width.")


def _read_rows(path: Path) -> list[dict[str, str]]:
    with path.open("r", encoding="utf-8", newline="") as handle:
        return list(csv.DictReader(handle))


def _write_rows(path: Path, rows: list[dict[str, Any]]) -> None:
    if not rows:
        path.write_text("", encoding="utf-8")
        return
    fieldnames = sorted({key for row in rows for key in row.keys()})
    with path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(rows)


def _to_float(value: Any) -> float | None:
    if value is None:
        return None
    try:
        return float(str(value).strip())
    except ValueError:
        return None


def _normalize_model_kind(model_kind: str) -> str:
    value = str(model_kind or "random_forest").strip().lower()
    aliases = {"rf": "random_forest", "random_forest": "random_forest", "mlp": "mlp", "nn": "mlp"}
    if value not in aliases:
        raise ValueError("model_kind must be random_forest or mlp.")
    return aliases[value]


def _unique_dir(root: Path, name: str) -> Path:
    stamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    safe = "".join(ch if ch.isalnum() or ch in ("-", "_") else "_" for ch in name).strip("_") or "composite"
    candidate = root / f"{stamp}_{safe}"
    if not candidate.exists():
        return candidate
    idx = 2
    while True:
        next_candidate = root / f"{stamp}_{safe}_{idx}"
        if not next_candidate.exists():
            return next_candidate
        idx += 1


def _json_ready(value: Any) -> Any:
    if isinstance(value, Path):
        return str(value)
    if isinstance(value, dict):
        return {key: _json_ready(item) for key, item in value.items()}
    if isinstance(value, (list, tuple)):
        return [_json_ready(item) for item in value]
    return value
