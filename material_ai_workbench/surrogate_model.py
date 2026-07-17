"""Surrogate-model training utilities for case-library datasets."""

from __future__ import annotations

import csv
import json
import math
import pickle
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from typing import Any, Iterable

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np
from sklearn.ensemble import RandomForestRegressor
from sklearn.feature_extraction import DictVectorizer
from sklearn.metrics import mean_absolute_error, mean_squared_error, r2_score
from sklearn.model_selection import KFold, cross_val_score, train_test_split
from sklearn.neural_network import MLPRegressor
from sklearn.pipeline import Pipeline
from sklearn.preprocessing import StandardScaler

from material_ai_workbench.config import SURROGATES_ROOT as DEFAULT_SURROGATES_ROOT
from material_ai_workbench.dataset_export import DATASETS_ROOT

SURROGATES_ROOT = DEFAULT_SURROGATES_ROOT
DEFAULT_TARGET = "latest_odb_max_mises"
TARGET_COLUMNS = {
    "latest_odb_max_mises",
    "latest_odb_max_peeq",
    "latest_odb_max_displacement",
    "latest_odb_max_reaction_force",
    "result_max_mises",
    "result_max_peeq",
    "result_max_displacement",
    "result_max_reaction_force",
    "abaqus_max_mises",
    "abaqus_max_peeq",
    "abaqus_max_displacement",
    "abaqus_max_reaction_force",
}
IDENTIFIER_COLUMNS = {
    "case_id",
    "case_schema_version",
    "source_fingerprint",
    "title",
    "source_folder",
    "latest_frame_series_csv",
    "updated_at",
    "status",
    "unit_system",
    "unit_length",
    "unit_stress",
    "quality_status",
    "quality_score",
    "execution_state",
    "training_eligible",
    "quality_blocking_reasons",
}
NUMERIC_FEATURE_COLUMNS = {
    "file_count",
    "model_file_count",
    "result_file_count",
    "data_file_count",
    "inp_node_count",
    "inp_element_count",
    "csv_row_count",
    "log_warning_count",
    "log_error_count",
    "odb_extraction_count",
    "frame_series_count",
    "latest_frame_series_rows",
    "yield_strength",
    "youngs_modulus",
    "poisson_ratio",
    "n_load_cases",
    "n_sequence",
    "max_abaqus_load_cases",
    "geometry_length",
    "geometry_width",
    "geometry_thickness",
    "geometry_hole_radius",
    "fiber_volume_fraction",
    "loading_applied_strain",
    "loading_applied_stress",
    "mesh_node_count",
    "mesh_element_count",
    "odb_csv_file_count",
    "odb_log_file_count",
    "odb_warning_count",
    "odb_error_count",
}


@dataclass
class SurrogateRun:
    run_dir: Path
    model_path: Path
    metrics_path: Path
    predictions_csv: Path
    features_csv: Path
    targets_csv: Path
    plot_path: Path
    report_path: Path
    metrics: dict[str, Any]


def list_dataset_exports(root: Path = DATASETS_ROOT) -> list[Path]:
    """Return dataset export folders that contain case_dataset.csv."""

    if not root.exists():
        return []
    return sorted(
        [
            path
            for path in root.iterdir()
            if path.is_dir() and (path / "case_dataset.csv").exists()
        ],
        key=lambda item: item.stat().st_mtime,
        reverse=True,
    )


def list_surrogate_runs(root: Path = SURROGATES_ROOT) -> list[Path]:
    """Return surrogate-model run folders, newest first."""

    if not root.exists():
        return []
    runs = [
        path
        for path in root.iterdir()
        if path.is_dir() and (path / "surrogate_metrics.json").exists()
    ]
    return sorted(runs, key=lambda item: item.stat().st_mtime, reverse=True)


def compare_all_models(
    dataset_dir: Path | str,
    *,
    target_column: str = DEFAULT_TARGET,
    output_root: Path = SURROGATES_ROOT,
    random_state: int = 42,
) -> list[dict[str, Any]]:
    """Train RF, MLP, and GBR on the same dataset and return a comparison table.

    Returns a list of dicts with model_name, mae, rmse, r2, cv_mae, cv_rmse, cv_r2, training_time.
    """
    import time

    rows: list[dict[str, Any]] = []
    models = [
        ("random_forest", "Random Forest"),
        ("mlp", "MLP Neural Network"),
        ("gbr", "Gradient Boosting"),
    ]
    for model_kind, label in models:
        t0 = time.time()
        try:
            run = train_surrogate_from_dataset(
                dataset_dir,
                target_column=target_column,
                model_kind=model_kind,
                output_root=output_root,
                random_state=random_state,
            )
            elapsed = time.time() - t0
            m = run.metrics
            rows.append(
                {
                    "model": label,
                    "model_kind": model_kind,
                    "mae": m.get("mae"),
                    "rmse": m.get("rmse"),
                    "r2": m.get("r2"),
                    "cv_mae_mean": m.get("cv_mae_mean"),
                    "cv_rmse_mean": m.get("cv_rmse_mean"),
                    "cv_r2_mean": m.get("cv_r2_mean"),
                    "training_time_s": round(elapsed, 1),
                    "run_dir": str(run.run_dir),
                    "error": None,
                }
            )
        except Exception as exc:
            rows.append(
                {
                    "model": label,
                    "model_kind": model_kind,
                    "mae": None,
                    "rmse": None,
                    "r2": None,
                    "cv_mae_mean": None,
                    "cv_rmse_mean": None,
                    "cv_r2_mean": None,
                    "training_time_s": None,
                    "run_dir": None,
                    "error": str(exc),
                }
            )
    return rows


def surrogate_comparison_rows(
    runs: Iterable[Path | str] | None = None,
    *,
    dataset_dir: Path | str | None = None,
    target_column: str | None = None,
) -> list[dict[str, Any]]:
    """Build compact comparison rows from surrogate_metrics.json files."""

    selected_runs = (
        [Path(item) for item in runs] if runs is not None else list_surrogate_runs()
    )
    dataset_filter = Path(dataset_dir).expanduser().resolve() if dataset_dir else None
    rows: list[dict[str, Any]] = []

    for run_dir in selected_runs:
        metrics_path = Path(run_dir) / "surrogate_metrics.json"
        if not metrics_path.exists():
            continue
        try:
            metrics = json.loads(metrics_path.read_text(encoding="utf-8"))
        except Exception:
            continue

        dataset_csv = (
            Path(str(metrics.get("dataset_csv", "")))
            if metrics.get("dataset_csv")
            else None
        )
        metrics_dataset_dir = dataset_csv.parent.resolve() if dataset_csv else None
        if dataset_filter and metrics_dataset_dir != dataset_filter:
            continue
        if target_column and metrics.get("target_column") != target_column:
            continue

        rows.append(
            {
                "run_dir": str(Path(run_dir).resolve()),
                "run": Path(run_dir).name,
                "dataset_dir": str(metrics_dataset_dir) if metrics_dataset_dir else "",
                "target_column": metrics.get("target_column", ""),
                "model_kind": metrics.get("model_kind", ""),
                "sample_count": metrics.get("sample_count"),
                "evaluation_mode": metrics.get("evaluation_mode", ""),
                "mae": metrics.get("mae"),
                "rmse": metrics.get("rmse"),
                "r2": metrics.get("r2"),
                "mean_relative_error": metrics.get("mean_relative_error"),
                "cv_mae_mean": metrics.get("cv_mae_mean"),
                "cv_rmse_mean": metrics.get("cv_rmse_mean"),
                "cv_r2_mean": metrics.get("cv_r2_mean"),
                "uncertainty": metrics.get("uncertainty", ""),
                "prediction_interval_mean_half_width": metrics.get(
                    "prediction_interval_mean_half_width"
                ),
                "prediction_interval_coverage": metrics.get(
                    "prediction_interval_coverage"
                ),
                "created_at": metrics.get("created_at", ""),
                "quality_note": metrics.get("quality_note", ""),
            }
        )

    return sorted(rows, key=_comparison_sort_key)


def train_surrogate_from_dataset(
    dataset_dir: Path | str,
    *,
    target_column: str = DEFAULT_TARGET,
    model_kind: str = "random_forest",
    output_root: Path = SURROGATES_ROOT,
    random_state: int = 42,
    uncertainty: str = "none",
) -> SurrogateRun:
    """Train a small surrogate model from a case-dataset export."""

    dataset = Path(dataset_dir).expanduser().resolve()
    dataset_csv = dataset / "case_dataset.csv" if dataset.is_dir() else dataset
    if not dataset_csv.exists():
        raise FileNotFoundError(f"case_dataset.csv does not exist: {dataset_csv}")
    rows = _read_csv(dataset_csv)
    if not rows:
        raise ValueError("case_dataset.csv contains no cases.")
    if target_column not in rows[0]:
        raise ValueError(f"Target column not found: {target_column}")

    rows, quality_skipped_rows, governance = _governed_training_rows(rows)
    if not rows:
        raise ValueError("No rows pass the dataset training quality gate.")

    clean_rows = []
    skipped_rows = list(quality_skipped_rows)
    for row in rows:
        target = _to_float(row.get(target_column))
        if target is None:
            skipped_rows.append(row.get("case_id", ""))
            continue
        clean_rows.append(row)
    if not clean_rows:
        raise ValueError(f"No rows contain a numeric target for {target_column}.")

    feature_dicts = [_feature_dict(row, target_column) for row in clean_rows]
    targets = np.array([float(row[target_column]) for row in clean_rows], dtype=float)
    case_ids = [row.get("case_id", "") for row in clean_rows]
    feature_names = sorted({key for item in feature_dicts for key in item.keys()})

    model_name = _normalize_model_kind(model_kind)
    uncertainty_mode = _normalize_uncertainty(uncertainty)
    run_dir = _unique_run_dir(output_root, dataset_csv.stem, target_column, model_name)
    run_dir.mkdir(parents=True, exist_ok=False)

    cv_metrics = _cross_validation_metrics(
        feature_dicts, targets, model_name, random_state
    )
    model, predictions, eval_indices, evaluation_mode = _fit_and_predict(
        feature_dicts,
        targets,
        model_name=model_name,
        random_state=random_state,
    )
    uncertainty_payload = _prediction_uncertainty(
        model, feature_dicts, uncertainty_mode
    )
    metrics = _metrics(
        targets=targets,
        predictions=predictions,
        eval_indices=eval_indices,
        target_column=target_column,
        model_kind=model_name,
        evaluation_mode=evaluation_mode,
        feature_count=len(feature_names),
        sample_count=len(clean_rows),
        skipped_case_ids=skipped_rows,
        dataset_csv=dataset_csv,
    )
    metrics.update(cv_metrics)
    metrics["dataset_governance"] = governance
    metrics["quality_gate_skipped_case_ids"] = quality_skipped_rows
    metrics["uncertainty"] = uncertainty_mode
    metrics.update(_uncertainty_metrics(targets, uncertainty_payload))

    features_csv = run_dir / "features.csv"
    targets_csv = run_dir / "targets.csv"
    predictions_csv = run_dir / "predictions.csv"
    metrics_path = run_dir / "surrogate_metrics.json"
    model_path = run_dir / "surrogate_model.pkl"
    plot_path = run_dir / "prediction_vs_truth.png"
    report_path = run_dir / "surrogate_report.md"

    _write_features_csv(features_csv, case_ids, feature_dicts, feature_names)
    _write_targets_csv(targets_csv, case_ids, target_column, targets)
    _write_predictions_csv(
        predictions_csv,
        case_ids,
        target_column,
        targets,
        predictions,
        eval_indices,
        uncertainty_payload,
    )
    metrics_path.write_text(
        json.dumps(metrics, indent=2, ensure_ascii=False), encoding="utf-8"
    )
    with model_path.open("wb") as handle:
        pickle.dump(model, handle)
    _plot_prediction_vs_truth(
        plot_path,
        target_column,
        targets,
        predictions,
        eval_indices,
        uncertainty_payload,
    )
    report_path.write_text(
        _surrogate_report(metrics, predictions_csv, plot_path), encoding="utf-8"
    )

    return SurrogateRun(
        run_dir=run_dir,
        model_path=model_path,
        metrics_path=metrics_path,
        predictions_csv=predictions_csv,
        features_csv=features_csv,
        targets_csv=targets_csv,
        plot_path=plot_path,
        report_path=report_path,
        metrics=metrics,
    )


def _fit_and_predict(
    feature_dicts: list[dict[str, Any]],
    targets: np.ndarray,
    *,
    model_name: str,
    random_state: int,
) -> tuple[Any, np.ndarray, list[int], str]:
    vectorizer = DictVectorizer(sparse=False)
    estimator = _estimator(model_name, random_state)
    model = Pipeline([("vectorizer", vectorizer), ("estimator", estimator)])
    n_samples = len(targets)
    if n_samples >= 4:
        indices = np.arange(n_samples)
        train_idx, test_idx = train_test_split(
            indices,
            test_size=max(1, math.ceil(n_samples * 0.25)),
            random_state=random_state,
        )
        model.fit([feature_dicts[int(idx)] for idx in train_idx], targets[train_idx])
        predictions = model.predict(feature_dicts)
        return (
            model,
            np.asarray(predictions, dtype=float),
            [int(idx) for idx in test_idx],
            "holdout",
        )

    model.fit(feature_dicts, targets)
    predictions = model.predict(feature_dicts)
    return (
        model,
        np.asarray(predictions, dtype=float),
        list(range(n_samples)),
        "training_set_only",
    )


def _estimator(model_name: str, random_state: int) -> Any:
    if model_name == "mlp":
        return Pipeline(
            [
                ("scaler", StandardScaler()),
                (
                    "mlp",
                    MLPRegressor(
                        hidden_layer_sizes=(32, 16),
                        activation="relu",
                        solver="lbfgs",
                        max_iter=1000,
                        random_state=random_state,
                    ),
                ),
            ]
        )
    if model_name == "gbr":
        from sklearn.ensemble import GradientBoostingRegressor

        return GradientBoostingRegressor(
            n_estimators=200,
            max_depth=4,
            learning_rate=0.05,
            random_state=random_state,
        )
    return RandomForestRegressor(
        n_estimators=200, random_state=random_state, min_samples_leaf=1
    )


def _cross_validation_metrics(
    feature_dicts: list[dict[str, Any]],
    targets: np.ndarray,
    model_name: str,
    random_state: int,
) -> dict[str, Any]:
    if len(targets) < 4:
        return {
            "cv_folds": 0,
            "cv_mae_mean": None,
            "cv_rmse_mean": None,
            "cv_r2_mean": None,
            "cv_note": "Too few samples for K-fold CV.",
        }
    folds = min(5, len(targets))
    pipeline = Pipeline(
        [
            ("vectorizer", DictVectorizer(sparse=False)),
            ("estimator", _estimator(model_name, random_state)),
        ]
    )
    cv = KFold(n_splits=folds, shuffle=True, random_state=random_state)
    try:
        mae = -cross_val_score(
            pipeline, feature_dicts, targets, cv=cv, scoring="neg_mean_absolute_error"
        )
        rmse = -cross_val_score(
            pipeline,
            feature_dicts,
            targets,
            cv=cv,
            scoring="neg_root_mean_squared_error",
        )
    except Exception as exc:
        return {
            "cv_folds": folds,
            "cv_mae_mean": None,
            "cv_rmse_mean": None,
            "cv_r2_mean": None,
            "cv_note": f"CV failed: {exc}",
        }
    cv_r2_mean = None
    cv_r2_std = None
    r2_note = ""
    r2_folds = min(5, max(2, len(targets) // 2))
    try:
        r2_cv = KFold(n_splits=r2_folds, shuffle=True, random_state=random_state)
        r2_values = cross_val_score(
            pipeline, feature_dicts, targets, cv=r2_cv, scoring="r2"
        )
        finite_r2 = r2_values[np.isfinite(r2_values)]
        if len(finite_r2):
            cv_r2_mean = float(np.mean(finite_r2))
            cv_r2_std = float(np.std(finite_r2))
        else:
            r2_note = " R2 was undefined for the selected folds."
    except Exception as exc:
        r2_note = f" R2 CV failed: {exc}"
    return {
        "cv_folds": folds,
        "cv_mae_mean": float(np.mean(mae)),
        "cv_mae_std": float(np.std(mae)),
        "cv_rmse_mean": float(np.mean(rmse)),
        "cv_rmse_std": float(np.std(rmse)),
        "cv_r2_mean": cv_r2_mean,
        "cv_r2_std": cv_r2_std,
        "cv_note": f"K-fold CV on all available samples.{r2_note}",
    }


def _prediction_uncertainty(
    model: Any,
    feature_dicts: list[dict[str, Any]],
    uncertainty: str,
) -> dict[str, np.ndarray] | None:
    if uncertainty == "none":
        return None
    if uncertainty == "ensemble":
        try:
            vectorizer = model.named_steps["vectorizer"]
            estimator = model.named_steps["estimator"]
            if not isinstance(estimator, RandomForestRegressor):
                return None
            x_vec = vectorizer.transform(feature_dicts)
            tree_predictions = np.asarray(
                [tree.predict(x_vec) for tree in estimator.estimators_], dtype=float
            )
            std = np.std(tree_predictions, axis=0)
            mean = np.mean(tree_predictions, axis=0)
            return {"std": std, "lower": mean - 1.64 * std, "upper": mean + 1.64 * std}
        except Exception:
            return None
    return None


def _uncertainty_metrics(
    targets: np.ndarray, payload: dict[str, np.ndarray] | None
) -> dict[str, Any]:
    if not payload or "lower" not in payload or "upper" not in payload:
        return {
            "prediction_interval_mean_half_width": None,
            "prediction_interval_coverage": None,
        }
    lower = payload["lower"]
    upper = payload["upper"]
    return {
        "prediction_interval_mean_half_width": float(np.mean((upper - lower) / 2.0)),
        "prediction_interval_coverage": float(
            np.mean((targets >= lower) & (targets <= upper))
        ),
    }


def _metrics(
    *,
    targets: np.ndarray,
    predictions: np.ndarray,
    eval_indices: list[int],
    target_column: str,
    model_kind: str,
    evaluation_mode: str,
    feature_count: int,
    sample_count: int,
    skipped_case_ids: list[str],
    dataset_csv: Path,
) -> dict[str, Any]:
    eval_targets = targets[eval_indices]
    eval_predictions = predictions[eval_indices]
    mae = float(mean_absolute_error(eval_targets, eval_predictions))
    rmse = float(mean_squared_error(eval_targets, eval_predictions) ** 0.5)
    r2 = None
    if len(eval_indices) >= 2:
        try:
            r2 = float(r2_score(eval_targets, eval_predictions))
        except Exception:
            r2 = None
    rel_errors = []
    for truth, pred in zip(eval_targets, eval_predictions):
        if abs(float(truth)) > 1e-12:
            rel_errors.append(abs(float(pred) - float(truth)) / abs(float(truth)))
    mean_relative_error = float(np.mean(rel_errors)) if rel_errors else None
    return {
        "created_at": datetime.now().isoformat(timespec="seconds"),
        "dataset_csv": str(dataset_csv),
        "target_column": target_column,
        "model_kind": model_kind,
        "evaluation_mode": evaluation_mode,
        "sample_count": sample_count,
        "evaluated_sample_count": len(eval_indices),
        "feature_count": feature_count,
        "mae": mae,
        "rmse": rmse,
        "r2": r2,
        "mean_relative_error": mean_relative_error,
        "skipped_case_ids": skipped_case_ids,
        "quality_note": _quality_note(sample_count, evaluation_mode),
    }


def _quality_note(sample_count: int, evaluation_mode: str) -> str:
    if sample_count < 4:
        return "样本数少于 4，本次仅验证代理模型训练流程，不代表预测精度。"
    if evaluation_mode == "training_set_only":
        return "本次只在训练集上评估，不代表泛化精度。"
    return "使用 holdout 样本评估；样本量增加后应使用交叉验证和独立验证集。"


def _feature_dict(row: dict[str, str], target_column: str) -> dict[str, Any]:
    features: dict[str, Any] = {}
    excluded = set(IDENTIFIER_COLUMNS) | set(TARGET_COLUMNS) | {target_column}
    for key, value in row.items():
        if key in excluded:
            continue
        if key in NUMERIC_FEATURE_COLUMNS:
            features[key] = _to_float(value) or 0.0
        else:
            text = str(value or "").strip()
            features[key] = text if text else "<missing>"
    return features


def _read_csv(path: Path) -> list[dict[str, str]]:
    with path.open("r", encoding="utf-8", newline="") as handle:
        return list(csv.DictReader(handle))


def _governed_training_rows(
    rows: list[dict[str, str]],
) -> tuple[list[dict[str, str]], list[str], dict[str, Any]]:
    """Filter explicit quality failures and reject mixed physical unit systems."""

    has_quality_gate = "training_eligible" in rows[0]
    eligible: list[dict[str, str]] = []
    skipped: list[str] = []
    for row in rows:
        if has_quality_gate and str(
            row.get("training_eligible", "")
        ).strip().lower() not in {
            "1",
            "true",
            "yes",
        }:
            skipped.append(row.get("case_id", ""))
            continue
        eligible.append(row)

    unit_systems = {
        str(row.get("unit_system", "")).strip()
        for row in eligible
        if str(row.get("unit_system", "")).strip()
    }
    if has_quality_gate and any(
        not str(row.get("unit_system", "")).strip() for row in eligible
    ):
        raise ValueError("Training-eligible rows must declare a unit_system.")
    if len(unit_systems) > 1:
        raise ValueError(
            "Mixed unit systems are not supported in one surrogate dataset: "
            + ", ".join(sorted(unit_systems))
        )
    governance = {
        "mode": "quality_gate_v1" if has_quality_gate else "legacy_unverified",
        "input_row_count": len(rows),
        "eligible_row_count": len(eligible),
        "skipped_row_count": len(skipped),
        "unit_system": next(iter(unit_systems), "unknown"),
        "mixed_units": False,
    }
    return eligible, skipped, governance


def _to_float(value: Any) -> float | None:
    if value is None:
        return None
    text = str(value).strip()
    if not text:
        return None
    try:
        return float(text)
    except ValueError:
        return None


def _write_features_csv(
    path: Path,
    case_ids: list[str],
    feature_dicts: list[dict[str, Any]],
    feature_names: list[str],
) -> None:
    columns = ["case_id"] + feature_names
    with path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=columns)
        writer.writeheader()
        for case_id, features in zip(case_ids, feature_dicts):
            row = {"case_id": case_id}
            row.update(features)
            writer.writerow(row)


def _write_targets_csv(
    path: Path, case_ids: list[str], target_column: str, targets: np.ndarray
) -> None:
    with path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=["case_id", target_column])
        writer.writeheader()
        for case_id, target in zip(case_ids, targets):
            writer.writerow({"case_id": case_id, target_column: float(target)})


def _write_predictions_csv(
    path: Path,
    case_ids: list[str],
    target_column: str,
    targets: np.ndarray,
    predictions: np.ndarray,
    eval_indices: list[int],
    uncertainty_payload: dict[str, np.ndarray] | None = None,
) -> None:
    eval_set = set(eval_indices)
    columns = [
        "case_id",
        "truth",
        "prediction",
        "predicted",
        "error",
        "relative_error",
        "evaluated",
    ]
    if uncertainty_payload:
        if "std" in uncertainty_payload:
            columns.append("prediction_std")
        if "lower" in uncertainty_payload:
            columns.append("prediction_lower")
        if "upper" in uncertainty_payload:
            columns.append("prediction_upper")
    with path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=columns)
        writer.writeheader()
        for idx, (case_id, truth, pred) in enumerate(
            zip(case_ids, targets, predictions)
        ):
            error = float(pred) - float(truth)
            relative = (
                abs(error) / abs(float(truth)) if abs(float(truth)) > 1e-12 else ""
            )
            row = {
                "case_id": case_id,
                "truth": float(truth),
                "prediction": float(pred),
                "predicted": float(pred),
                "error": error,
                "relative_error": relative,
                "evaluated": idx in eval_set,
            }
            if uncertainty_payload:
                if "std" in uncertainty_payload:
                    row["prediction_std"] = float(uncertainty_payload["std"][idx])
                if "lower" in uncertainty_payload:
                    row["prediction_lower"] = float(uncertainty_payload["lower"][idx])
                if "upper" in uncertainty_payload:
                    row["prediction_upper"] = float(uncertainty_payload["upper"][idx])
            writer.writerow(row)


def _plot_prediction_vs_truth(
    path: Path,
    target_column: str,
    targets: np.ndarray,
    predictions: np.ndarray,
    eval_indices: list[int],
    uncertainty_payload: dict[str, np.ndarray] | None = None,
) -> None:
    fig, ax = plt.subplots(figsize=(6, 5), dpi=140)
    if uncertainty_payload and "std" in uncertainty_payload:
        ax.errorbar(
            targets,
            predictions,
            yerr=uncertainty_payload["std"],
            fmt="o",
            color="#2563eb",
            ecolor="#93c5fd",
            label="cases",
        )
    else:
        ax.scatter(targets, predictions, color="#2563eb", label="cases")
    eval_targets = targets[eval_indices]
    eval_predictions = predictions[eval_indices]
    ax.scatter(
        eval_targets,
        eval_predictions,
        facecolors="none",
        edgecolors="#dc2626",
        s=90,
        label="evaluated",
    )
    lower = float(min(np.min(targets), np.min(predictions)))
    upper = float(max(np.max(targets), np.max(predictions)))
    if abs(upper - lower) < 1e-12:
        lower -= 1.0
        upper += 1.0
    ax.plot(
        [lower, upper],
        [lower, upper],
        color="#111827",
        linewidth=1.2,
        linestyle="--",
        label="ideal",
    )
    ax.set_xlabel("Truth")
    ax.set_ylabel("Prediction")
    ax.set_title(f"Surrogate prediction: {target_column}")
    ax.grid(True, alpha=0.25)
    ax.legend()
    fig.tight_layout()
    try:
        fig.savefig(str(path))
    except Exception:
        pass
    plt.close(fig)


def _surrogate_report(
    metrics: dict[str, Any], predictions_csv: Path, plot_path: Path
) -> str:
    return f"""# 代理模型训练报告

## 基本信息

- 数据集: `{metrics.get("dataset_csv")}`
- 目标: `{metrics.get("target_column")}`
- 模型: `{metrics.get("model_kind")}`
- 样本数: `{metrics.get("sample_count")}`
- 特征数: `{metrics.get("feature_count")}`
- 评估方式: `{metrics.get("evaluation_mode")}`

## 误差指标

- MAE: `{metrics.get("mae")}`
- RMSE: `{metrics.get("rmse")}`
- R2: `{metrics.get("r2")}`
- 平均相对误差: `{metrics.get("mean_relative_error")}`

## Cross Validation

- K-folds: `{metrics.get("cv_folds")}`
- CV MAE: `{metrics.get("cv_mae_mean")}` ± `{metrics.get("cv_mae_std")}`
- CV RMSE: `{metrics.get("cv_rmse_mean")}` ± `{metrics.get("cv_rmse_std")}`
- Note: `{metrics.get("cv_note")}`

## Prediction Uncertainty

- Mode: `{metrics.get("uncertainty")}`
- Mean interval half width: `{metrics.get("prediction_interval_mean_half_width")}`
- Interval coverage: `{metrics.get("prediction_interval_coverage")}`

## 输出

- 预测表: `{predictions_csv}`
- 预测图: `{plot_path}`

## 质量说明

{metrics.get("quality_note")}

## 工程解释

本报告用于验证“案例库特征 -> 代理模型预测”的最小流程。当前模型不是 Abaqus 的替代品，而是后续高质量样本积累后的快速预测层。所有关键设计仍应回到 Abaqus 真实求解进行抽样验证。
"""


def _normalize_model_kind(model_kind: str) -> str:
    value = str(model_kind or "random_forest").strip().lower()
    aliases = {
        "rf": "random_forest",
        "random_forest": "random_forest",
        "forest": "random_forest",
        "mlp": "mlp",
        "neural_network": "mlp",
        "nn": "mlp",
        "gbr": "gbr",
        "gradient_boosting": "gbr",
        "boosting": "gbr",
    }
    if value not in aliases:
        raise ValueError("model_kind must be one of: random_forest, mlp, gbr")
    return aliases[value]


def _normalize_uncertainty(value: str) -> str:
    normalized = str(value or "none").strip().lower()
    if normalized not in {"none", "ensemble"}:
        raise ValueError("uncertainty must be one of: none, ensemble")
    return normalized


def _unique_run_dir(
    output_root: Path, dataset_name: str, target_column: str, model_kind: str
) -> Path:
    stamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    base = (
        output_root
        / f"{stamp}_{_safe_name(dataset_name)}_{_safe_name(target_column)}_{model_kind}"
    )
    if not base.exists():
        return base
    idx = 2
    while True:
        candidate = (
            output_root
            / f"{stamp}_{_safe_name(dataset_name)}_{_safe_name(target_column)}_{model_kind}_{idx}"
        )
        if not candidate.exists():
            return candidate
        idx += 1


def _safe_name(value: str) -> str:
    return (
        "".join(ch if ch.isalnum() or ch in ("-", "_") else "_" for ch in value).strip(
            "_"
        )
        or "surrogate"
    )


def _comparison_sort_key(row: dict[str, Any]) -> tuple[Any, ...]:
    rmse = row.get("rmse")
    mae = row.get("mae")
    rmse_key = float(rmse) if isinstance(rmse, (int, float)) else float("inf")
    mae_key = float(mae) if isinstance(mae, (int, float)) else float("inf")
    return (
        str(row.get("dataset_dir", "")),
        str(row.get("target_column", "")),
        rmse_key,
        mae_key,
        str(row.get("model_kind", "")),
    )
