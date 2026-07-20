"""Leakage-resistant baselines for the governed CFRP experimental dataset."""

from __future__ import annotations

import csv
import hashlib
import json
import math
import os
import pickle
import platform
import shutil
from collections import Counter
from dataclasses import dataclass
from datetime import datetime, timezone
from importlib.metadata import PackageNotFoundError, version
from pathlib import Path
from typing import Any, Iterable, Sequence
from uuid import uuid4

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np
from sklearn.dummy import DummyRegressor
from sklearn.ensemble import RandomForestRegressor
from sklearn.linear_model import Ridge
from sklearn.metrics import mean_absolute_error, mean_squared_error, r2_score
from sklearn.pipeline import Pipeline
from sklearn.preprocessing import StandardScaler
from sklearn.svm import SVR
from sklearn.compose import TransformedTargetRegressor

from material_ai_workbench.config import DATASETS_ROOT, EXPERIMENTS_ROOT
from material_ai_workbench.experimental_datasets import (
    ALSHEGHRI_CFRP_SPEC,
    COLUMN_SCHEMA,
    FEATURE_COLUMNS,
    TARGET_COLUMNS,
)

DEFAULT_MODELS = ("mean", "ridge", "random_forest", "svr")
MODEL_LABELS = {
    "mean": "Training mean",
    "ridge": "Ridge regression",
    "random_forest": "Random forest",
    "svr": "Support vector regression",
}
TARGET_UNITS = {
    str(column["name"]): column.get("unit")
    for column in COLUMN_SCHEMA
    if column.get("role") == "target"
}
DEFAULT_DATASET_DIR = (
    DATASETS_ROOT / ALSHEGHRI_CFRP_SPEC.dataset_id / f"v{ALSHEGHRI_CFRP_SPEC.version}"
)
DEFAULT_OUTPUT_ROOT = EXPERIMENTS_ROOT / "cfrp_grouped_baselines"


@dataclass(frozen=True)
class ExperimentalBaselineRun:
    """Artifacts produced by one fixed-split baseline experiment."""

    run_dir: Path
    manifest_json: Path
    summary_json: Path
    comparison_csv: Path
    fold_metrics_csv: Path
    predictions_csv: Path
    report_md: Path
    figure_paths: tuple[Path, ...]
    model_paths: tuple[Path, ...]
    summary: dict[str, Any]


@dataclass(frozen=True)
class _DatasetBundle:
    dataset_dir: Path
    dataset_manifest: dict[str, Any]
    split_manifest: dict[str, Any]
    rows_by_id: dict[str, dict[str, Any]]
    normalized_csv: Path
    split_manifest_json: Path
    normalized_sha256: str
    split_sha256: str


def train_cfrp_grouped_baselines(
    dataset_dir: Path | str = DEFAULT_DATASET_DIR,
    *,
    output_root: Path | str = DEFAULT_OUTPUT_ROOT,
    targets: Sequence[str] | None = None,
    models: Sequence[str] = DEFAULT_MODELS,
    random_state: int = 42,
    interval_coverage: float = 0.90,
    rf_estimators: int = 250,
) -> ExperimentalBaselineRun:
    """Train deterministic baselines on the registered material-type folds.

    Every reported prediction is out-of-fold for a complete CFRP material type.
    Prediction intervals use nested group-wise residual calibration inside each
    outer training fold, so the held-out material type never calibrates its own
    interval.
    """

    selected_targets = _normalize_selection(
        targets or TARGET_COLUMNS, allowed=TARGET_COLUMNS, label="target"
    )
    selected_models = _normalize_selection(
        models, allowed=DEFAULT_MODELS, label="model"
    )
    if not 0.5 <= float(interval_coverage) < 1.0:
        raise ValueError("interval_coverage must be in [0.5, 1.0).")
    if int(rf_estimators) < 10:
        raise ValueError("rf_estimators must be at least 10.")

    bundle = load_cfrp_baseline_dataset(dataset_dir)
    output = Path(output_root).expanduser().resolve()
    output.mkdir(parents=True, exist_ok=True)
    run_id = _run_id()
    final_dir = output / run_id
    working_dir = output / f".{run_id}.{uuid4().hex}.partial"
    working_dir.mkdir(parents=False, exist_ok=False)

    try:
        predictions: list[dict[str, Any]] = []
        fold_metrics: list[dict[str, Any]] = []
        comparison: list[dict[str, Any]] = []
        model_paths: list[Path] = []
        model_card_paths: list[Path] = []

        for target in selected_targets:
            folds = validate_target_split_contract(bundle, target)
            target_rows = [
                row for row in bundle.rows_by_id.values() if row[target] is not None
            ]
            target_rows.sort(key=lambda row: str(row["sample_id"]))

            target_comparison: list[dict[str, Any]] = []
            for model_kind in selected_models:
                model_predictions, model_folds = _evaluate_model(
                    rows_by_id=bundle.rows_by_id,
                    target=target,
                    folds=folds,
                    model_kind=model_kind,
                    random_state=random_state,
                    interval_coverage=float(interval_coverage),
                    rf_estimators=int(rf_estimators),
                )
                predictions.extend(model_predictions)
                fold_metrics.extend(model_folds)
                metrics = _regression_metrics(model_predictions)
                metrics.update(
                    {
                        "target": target,
                        "target_unit": TARGET_UNITS.get(target),
                        "model": model_kind,
                        "model_label": MODEL_LABELS[model_kind],
                        "sample_count": len(model_predictions),
                        "group_count": len(folds),
                        "evaluation_strategy": "leave_one_material_type_out",
                        "interval_method": (
                            "nested_group_oof_absolute_residual_conformal"
                        ),
                        "interval_nominal_coverage": float(interval_coverage),
                    }
                )
                empirical_coverage = metrics["interval_empirical_coverage"]
                metrics["interval_coverage_gap"] = (
                    float(empirical_coverage) - float(interval_coverage)
                    if empirical_coverage is not None
                    else None
                )
                metrics["interval_undercoverage"] = (
                    bool(float(empirical_coverage) < float(interval_coverage))
                    if empirical_coverage is not None
                    else None
                )
                target_comparison.append(metrics)

                fitted = _make_estimator(
                    model_kind,
                    random_state=random_state,
                    rf_estimators=int(rf_estimators),
                )
                fitted.fit(_features(target_rows), _targets(target_rows, target))
                model_path, card_path = _save_full_model(
                    working_dir=working_dir,
                    estimator=fitted,
                    target=target,
                    model_kind=model_kind,
                    sample_count=len(target_rows),
                    group_count=len(folds),
                    bundle=bundle,
                    random_state=random_state,
                    interval_coverage=float(interval_coverage),
                    rf_estimators=int(rf_estimators),
                )
                model_paths.append(model_path)
                model_card_paths.append(card_path)

            _rank_target_models(target_comparison)
            comparison.extend(target_comparison)

        predictions.sort(
            key=lambda row: (
                str(row["target"]),
                _model_order(str(row["model"])),
                str(row["sample_id"]),
            )
        )
        fold_metrics.sort(
            key=lambda row: (
                str(row["target"]),
                _model_order(str(row["model"])),
                str(row["fold_id"]),
            )
        )
        comparison.sort(key=lambda row: (str(row["target"]), int(row["rank_by_mae"])))

        predictions_csv = working_dir / "predictions.csv"
        fold_metrics_csv = working_dir / "fold_metrics.csv"
        comparison_csv = working_dir / "model_comparison.csv"
        _write_csv(predictions_csv, predictions, _prediction_columns())
        _write_csv(fold_metrics_csv, fold_metrics, _fold_metric_columns())
        _write_csv(comparison_csv, comparison, _comparison_columns())

        figure_paths = _write_figures(
            working_dir / "figures", predictions, selected_targets, selected_models
        )
        summary = _build_summary(
            run_id=run_id,
            bundle=bundle,
            comparison=comparison,
            targets=selected_targets,
            models=selected_models,
            random_state=random_state,
            interval_coverage=float(interval_coverage),
            rf_estimators=int(rf_estimators),
        )
        summary_json = working_dir / "summary.json"
        _write_json(summary_json, summary)
        report_md = working_dir / "REPORT_CN.md"
        _write_text(report_md, _render_report(summary, comparison))

        manifest_json = working_dir / "run_manifest.json"
        manifest = {
            "schema_version": 1,
            "run_id": run_id,
            "created_at": _utc_now(),
            "experiment": "cfrp_grouped_regression_baselines",
            "source_dataset": {
                "dataset_id": bundle.dataset_manifest["dataset_id"],
                "dataset_version": bundle.dataset_manifest["dataset_version"],
                "dataset_doi": bundle.dataset_manifest["source"]["dataset_doi"],
                "normalized_csv_sha256": bundle.normalized_sha256,
                "grouped_splits_sha256": bundle.split_sha256,
            },
            "configuration": {
                "features": list(FEATURE_COLUMNS),
                "targets": list(selected_targets),
                "models": list(selected_models),
                "random_state": int(random_state),
                "interval_coverage": float(interval_coverage),
                "rf_estimators": int(rf_estimators),
            },
            "evaluation": {
                "outer_split": "leave_one_material_type_out",
                "interval_calibration": (
                    "nested leave-one-material-type-out on each outer training set"
                ),
                "hyperparameter_search": False,
                "paper_metric_comparability": "not_directly_comparable",
            },
            "runtime": _runtime_versions(),
            "artifacts": _artifact_inventory(working_dir, exclude={manifest_json}),
            "limitations": list(summary["limitations"]),
        }
        _write_json(manifest_json, manifest)
        os.replace(working_dir, final_dir)
    except Exception:
        if working_dir.exists() and working_dir.parent == output:
            shutil.rmtree(working_dir, ignore_errors=True)
        raise

    return ExperimentalBaselineRun(
        run_dir=final_dir,
        manifest_json=final_dir / "run_manifest.json",
        summary_json=final_dir / "summary.json",
        comparison_csv=final_dir / "model_comparison.csv",
        fold_metrics_csv=final_dir / "fold_metrics.csv",
        predictions_csv=final_dir / "predictions.csv",
        report_md=final_dir / "REPORT_CN.md",
        figure_paths=tuple(
            final_dir / path.relative_to(working_dir) for path in figure_paths
        ),
        model_paths=tuple(
            final_dir / path.relative_to(working_dir) for path in model_paths
        ),
        summary=summary,
    )


def load_cfrp_baseline_dataset(dataset_dir: Path | str) -> _DatasetBundle:
    """Load and cryptographically verify the governed dataset artifacts."""

    root = Path(dataset_dir).expanduser().resolve()
    manifest_path = root / "dataset_manifest.json"
    if not manifest_path.is_file():
        raise FileNotFoundError(
            f"dataset_manifest.json does not exist: {manifest_path}"
        )
    manifest = _read_json(manifest_path)
    if manifest.get("schema_version") != 1:
        raise ValueError("Unsupported dataset manifest schema_version.")
    if manifest.get("dataset_id") != ALSHEGHRI_CFRP_SPEC.dataset_id:
        raise ValueError("The dataset manifest is not the registered CFRP dataset.")
    if tuple(manifest.get("features", ())) != FEATURE_COLUMNS:
        raise ValueError("Dataset feature contract does not match the CFRP baseline.")
    if tuple(manifest.get("targets", ())) != TARGET_COLUMNS:
        raise ValueError("Dataset target contract does not match the CFRP baseline.")

    artifacts = manifest.get("artifacts")
    if not isinstance(artifacts, dict):
        raise ValueError("Dataset manifest does not contain artifacts.")
    normalized_csv, normalized_sha = _verified_artifact(
        root, artifacts.get("normalized_csv"), "normalized_csv"
    )
    split_json, split_sha = _verified_artifact(
        root, artifacts.get("grouped_splits"), "grouped_splits"
    )
    split_manifest = _read_json(split_json)
    if split_manifest.get("strategy") != "leave_one_material_type_out":
        raise ValueError("Expected leave_one_material_type_out split strategy.")
    if split_manifest.get("dataset_id") != manifest.get("dataset_id"):
        raise ValueError("Split manifest dataset_id does not match the dataset.")

    rows_by_id = _read_normalized_rows(normalized_csv)
    if len(rows_by_id) != int(manifest.get("row_count", -1)):
        raise ValueError("Normalized row count does not match dataset_manifest.json.")
    return _DatasetBundle(
        dataset_dir=root,
        dataset_manifest=manifest,
        split_manifest=split_manifest,
        rows_by_id=rows_by_id,
        normalized_csv=normalized_csv,
        split_manifest_json=split_json,
        normalized_sha256=normalized_sha,
        split_sha256=split_sha,
    )


def validate_target_split_contract(
    bundle: _DatasetBundle, target: str
) -> list[dict[str, Any]]:
    """Validate that fixed folds cover each labelled sample once without leakage."""

    if target not in TARGET_COLUMNS:
        raise ValueError(f"Unsupported target: {target}")
    targets = bundle.split_manifest.get("targets")
    if not isinstance(targets, dict) or not isinstance(targets.get(target), dict):
        raise ValueError(f"Split manifest does not define target: {target}")
    details = targets[target]
    folds = details.get("folds")
    if not isinstance(folds, list) or not folds:
        raise ValueError(f"No grouped folds are registered for target: {target}")

    available = {
        sample_id
        for sample_id, row in bundle.rows_by_id.items()
        if row[target] is not None
    }
    if int(details.get("available_sample_count", -1)) != len(available):
        raise ValueError(f"Available sample count is inconsistent for {target}.")
    test_occurrences: Counter[str] = Counter()
    validated: list[dict[str, Any]] = []
    for raw_fold in folds:
        if not isinstance(raw_fold, dict):
            raise ValueError(f"Invalid fold entry for target: {target}")
        fold = dict(raw_fold)
        fold_id = str(fold.get("fold_id", "")).strip()
        if not fold_id:
            raise ValueError(f"A fold for {target} has no fold_id.")
        train_ids = _unique_ids(fold.get("train_sample_ids"), fold_id, "train")
        test_ids = _unique_ids(fold.get("test_sample_ids"), fold_id, "test")
        train_set = set(train_ids)
        test_set = set(test_ids)
        if train_set & test_set:
            raise ValueError(f"Fold {fold_id} has overlapping train and test samples.")
        if train_set | test_set != available:
            raise ValueError(f"Fold {fold_id} does not partition all labelled samples.")
        if int(fold.get("train_count", -1)) != len(train_ids):
            raise ValueError(f"Fold {fold_id} train_count is inconsistent.")
        if int(fold.get("test_count", -1)) != len(test_ids):
            raise ValueError(f"Fold {fold_id} test_count is inconsistent.")
        test_group = int(fold.get("test_group"))
        actual_test_groups = {
            int(bundle.rows_by_id[sample_id]["material_type_id"])
            for sample_id in test_ids
        }
        train_groups = {
            int(bundle.rows_by_id[sample_id]["material_type_id"])
            for sample_id in train_ids
        }
        if actual_test_groups != {test_group}:
            raise ValueError(f"Fold {fold_id} test samples do not match test_group.")
        if test_group in train_groups:
            raise ValueError(f"Fold {fold_id} leaks the held-out material type.")
        test_occurrences.update(test_ids)
        fold["train_sample_ids"] = train_ids
        fold["test_sample_ids"] = test_ids
        validated.append(fold)

    if set(test_occurrences) != available or any(
        count != 1 for count in test_occurrences.values()
    ):
        raise ValueError(
            f"Grouped folds for {target} must evaluate every labelled sample once."
        )
    return validated


def _evaluate_model(
    *,
    rows_by_id: dict[str, dict[str, Any]],
    target: str,
    folds: list[dict[str, Any]],
    model_kind: str,
    random_state: int,
    interval_coverage: float,
    rf_estimators: int,
) -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
    predictions: list[dict[str, Any]] = []
    fold_metrics: list[dict[str, Any]] = []
    for fold in folds:
        train_rows = [rows_by_id[sample_id] for sample_id in fold["train_sample_ids"]]
        test_rows = [rows_by_id[sample_id] for sample_id in fold["test_sample_ids"]]
        estimator = _make_estimator(
            model_kind,
            random_state=random_state,
            rf_estimators=rf_estimators,
        )
        estimator.fit(_features(train_rows), _targets(train_rows, target))
        predicted = np.asarray(estimator.predict(_features(test_rows)), dtype=float)
        calibration_errors = _nested_group_calibration_errors(
            train_rows=train_rows,
            target=target,
            model_kind=model_kind,
            random_state=random_state,
            rf_estimators=rf_estimators,
        )
        half_width = _conformal_half_width(
            calibration_errors, coverage=interval_coverage
        )
        fold_rows: list[dict[str, Any]] = []
        for row, prediction in zip(test_rows, predicted):
            truth = float(row[target])
            lower = float(prediction - half_width)
            upper = float(prediction + half_width)
            residual = float(prediction - truth)
            result = {
                "target": target,
                "target_unit": TARGET_UNITS.get(target),
                "model": model_kind,
                "model_label": MODEL_LABELS[model_kind],
                "fold_id": fold["fold_id"],
                "test_group": int(fold["test_group"]),
                "test_group_name": str(fold.get("test_group_name", "")),
                "sample_id": str(row["sample_id"]),
                "source_row": int(row["source_row"]),
                "truth": truth,
                "prediction": float(prediction),
                "residual": residual,
                "absolute_error": abs(residual),
                "relative_error": (
                    abs(residual) / abs(truth) if abs(truth) > 1e-12 else None
                ),
                "prediction_lower": lower,
                "prediction_upper": upper,
                "interval_half_width": float(half_width),
                "interval_covered": bool(lower <= truth <= upper),
                "calibration_sample_count": len(calibration_errors),
            }
            predictions.append(result)
            fold_rows.append(result)
        fold_summary = _regression_metrics(fold_rows)
        fold_summary.update(
            {
                "target": target,
                "target_unit": TARGET_UNITS.get(target),
                "model": model_kind,
                "model_label": MODEL_LABELS[model_kind],
                "fold_id": fold["fold_id"],
                "test_group": int(fold["test_group"]),
                "test_group_name": str(fold.get("test_group_name", "")),
                "train_count": len(train_rows),
                "test_count": len(test_rows),
                "calibration_sample_count": len(calibration_errors),
                "interval_half_width": float(half_width),
            }
        )
        fold_metrics.append(fold_summary)
    return predictions, fold_metrics


def _nested_group_calibration_errors(
    *,
    train_rows: list[dict[str, Any]],
    target: str,
    model_kind: str,
    random_state: int,
    rf_estimators: int,
) -> list[float]:
    errors: list[float] = []
    groups = sorted({int(row["material_type_id"]) for row in train_rows})
    for calibration_group in groups:
        inner_train = [
            row
            for row in train_rows
            if int(row["material_type_id"]) != calibration_group
        ]
        inner_test = [
            row
            for row in train_rows
            if int(row["material_type_id"]) == calibration_group
        ]
        if not inner_train or not inner_test:
            continue
        estimator = _make_estimator(
            model_kind,
            random_state=random_state,
            rf_estimators=rf_estimators,
        )
        estimator.fit(_features(inner_train), _targets(inner_train, target))
        predicted = np.asarray(estimator.predict(_features(inner_test)), dtype=float)
        truth = _targets(inner_test, target)
        errors.extend(float(value) for value in np.abs(predicted - truth))
    if not errors:
        raise ValueError("Nested group calibration produced no residuals.")
    return errors


def _make_estimator(model_kind: str, *, random_state: int, rf_estimators: int) -> Any:
    if model_kind == "mean":
        return DummyRegressor(strategy="mean")
    if model_kind == "ridge":
        return Pipeline([("scale", StandardScaler()), ("ridge", Ridge(alpha=1.0))])
    if model_kind == "random_forest":
        return RandomForestRegressor(
            n_estimators=rf_estimators,
            min_samples_leaf=2,
            max_features=1.0,
            random_state=random_state,
            n_jobs=1,
        )
    if model_kind == "svr":
        return TransformedTargetRegressor(
            regressor=Pipeline(
                [
                    ("scale", StandardScaler()),
                    ("svr", SVR(kernel="rbf", C=10.0, epsilon=0.05, gamma="scale")),
                ]
            ),
            transformer=StandardScaler(),
        )
    raise ValueError(f"Unsupported model: {model_kind}")


def _conformal_half_width(errors: Sequence[float], *, coverage: float) -> float:
    ordered = sorted(float(error) for error in errors)
    rank = min(len(ordered), max(1, math.ceil((len(ordered) + 1) * coverage)))
    return ordered[rank - 1]


def _regression_metrics(rows: Sequence[dict[str, Any]]) -> dict[str, Any]:
    truth = np.asarray([float(row["truth"]) for row in rows], dtype=float)
    prediction = np.asarray([float(row["prediction"]) for row in rows], dtype=float)
    residual = prediction - truth
    absolute = np.abs(residual)
    target_range = float(np.max(truth) - np.min(truth)) if len(truth) else 0.0
    r2: float | None = None
    if len(truth) >= 2 and float(np.var(truth)) > 1e-15:
        r2 = float(r2_score(truth, prediction))
    relative = [
        abs(float(pred) - float(actual)) / abs(float(actual))
        for actual, pred in zip(truth, prediction)
        if abs(float(actual)) > 1e-12
    ]
    interval_rows = [row for row in rows if row.get("interval_covered") is not None]
    return {
        "mae": float(mean_absolute_error(truth, prediction)),
        "rmse": float(math.sqrt(mean_squared_error(truth, prediction))),
        "r2": r2,
        "median_absolute_error": float(np.median(absolute)),
        "mean_relative_error": float(np.mean(relative)) if relative else None,
        "bias": float(np.mean(residual)),
        "max_absolute_error": float(np.max(absolute)),
        "nrmse_by_range": (
            float(math.sqrt(mean_squared_error(truth, prediction)) / target_range)
            if target_range > 1e-15
            else None
        ),
        "interval_empirical_coverage": (
            float(np.mean([bool(row["interval_covered"]) for row in interval_rows]))
            if interval_rows
            else None
        ),
        "interval_mean_half_width": (
            float(np.mean([float(row["interval_half_width"]) for row in interval_rows]))
            if interval_rows
            else None
        ),
    }


def _rank_target_models(rows: list[dict[str, Any]]) -> None:
    ordered = sorted(
        rows, key=lambda row: (float(row["mae"]), _model_order(row["model"]))
    )
    mean_row = next((row for row in rows if row["model"] == "mean"), None)
    mean_mae = float(mean_row["mae"]) if mean_row is not None else None
    for rank, row in enumerate(ordered, start=1):
        row["rank_by_mae"] = rank
        row["mae_improvement_vs_mean_pct"] = (
            100.0 * (mean_mae - float(row["mae"])) / mean_mae
            if mean_mae is not None and mean_mae > 1e-15
            else None
        )
        row["beats_mean_baseline"] = (
            bool(float(row["mae"]) < mean_mae - 1e-12) if mean_mae is not None else None
        )


def _save_full_model(
    *,
    working_dir: Path,
    estimator: Any,
    target: str,
    model_kind: str,
    sample_count: int,
    group_count: int,
    bundle: _DatasetBundle,
    random_state: int,
    interval_coverage: float,
    rf_estimators: int,
) -> tuple[Path, Path]:
    model_dir = working_dir / "models" / target
    card_dir = working_dir / "model_cards" / target
    model_dir.mkdir(parents=True, exist_ok=True)
    card_dir.mkdir(parents=True, exist_ok=True)
    model_path = model_dir / f"{model_kind}.pkl"
    payload = {
        "schema_version": 1,
        "estimator": estimator,
        "feature_columns": list(FEATURE_COLUMNS),
        "target": target,
        "target_unit": TARGET_UNITS.get(target),
        "model": model_kind,
        "training_sample_count": sample_count,
        "training_group_count": group_count,
        "normalized_csv_sha256": bundle.normalized_sha256,
        "grouped_splits_sha256": bundle.split_sha256,
    }
    with model_path.open("wb") as handle:
        pickle.dump(payload, handle, protocol=pickle.HIGHEST_PROTOCOL)
    card_path = card_dir / f"{model_kind}.json"
    _write_json(
        card_path,
        {
            "schema_version": 1,
            "model": model_kind,
            "model_label": MODEL_LABELS[model_kind],
            "target": target,
            "target_unit": TARGET_UNITS.get(target),
            "feature_columns": list(FEATURE_COLUMNS),
            "training_sample_count": sample_count,
            "training_group_count": group_count,
            "random_state": random_state,
            "rf_estimators": rf_estimators if model_kind == "random_forest" else None,
            "evaluation_strategy": "leave_one_material_type_out",
            "interval_nominal_coverage": interval_coverage,
            "normalized_csv_sha256": bundle.normalized_sha256,
            "grouped_splits_sha256": bundle.split_sha256,
            "pickle_sha256": _sha256(model_path),
            "security": "Load this pickle only when it comes from a trusted run.",
            "intended_use": (
                "Educational CFRP property regression and workflow validation; "
                "not direct constitutive-law calibration or design allowables."
            ),
        },
    )
    return model_path, card_path


def _write_figures(
    figure_dir: Path,
    predictions: list[dict[str, Any]],
    targets: Sequence[str],
    models: Sequence[str],
) -> list[Path]:
    figure_dir.mkdir(parents=True, exist_ok=True)
    paths: list[Path] = []
    for target in targets:
        target_rows = [row for row in predictions if row["target"] == target]
        prediction_path = figure_dir / f"{target}_prediction_vs_truth.png"
        residual_path = figure_dir / f"{target}_residuals_by_group.png"
        _plot_prediction_grid(prediction_path, target, target_rows, models)
        _plot_residual_grid(residual_path, target, target_rows, models)
        paths.extend([prediction_path, residual_path])
    return paths


def _plot_prediction_grid(
    path: Path,
    target: str,
    rows: list[dict[str, Any]],
    models: Sequence[str],
) -> None:
    fig, axes = _subplot_grid(len(models))
    all_groups = sorted({int(row["test_group"]) for row in rows})
    for axis, model_kind in zip(axes, models):
        selected = [row for row in rows if row["model"] == model_kind]
        truth = np.asarray([row["truth"] for row in selected], dtype=float)
        prediction = np.asarray([row["prediction"] for row in selected], dtype=float)
        groups = np.asarray([row["test_group"] for row in selected], dtype=float)
        yerr = np.asarray([row["interval_half_width"] for row in selected], dtype=float)
        axis.errorbar(
            truth,
            prediction,
            yerr=yerr,
            fmt="none",
            ecolor="#9ca3af",
            alpha=0.28,
            linewidth=0.8,
        )
        scatter = axis.scatter(
            truth,
            prediction,
            c=groups,
            cmap="tab10",
            s=28,
            edgecolors="white",
            linewidths=0.3,
        )
        lower = float(min(np.min(truth), np.min(prediction)))
        upper = float(max(np.max(truth), np.max(prediction)))
        padding = max((upper - lower) * 0.04, 1e-6)
        axis.plot(
            [lower - padding, upper + padding],
            [lower - padding, upper + padding],
            color="#111827",
            linestyle="--",
            linewidth=1.0,
        )
        axis.set_title(MODEL_LABELS[model_kind])
        axis.set_xlabel("Measured")
        axis.set_ylabel("Grouped OOF prediction")
        axis.grid(True, alpha=0.2)
    for axis in axes[len(models) :]:
        axis.set_visible(False)
    fig.suptitle(f"CFRP grouped validation: {target}")
    fig.subplots_adjust(
        left=0.08, right=0.87, bottom=0.08, top=0.9, wspace=0.30, hspace=0.34
    )
    color_axis = fig.add_axes([0.91, 0.16, 0.018, 0.68])
    colorbar = fig.colorbar(scatter, cax=color_axis, ticks=all_groups)
    colorbar.set_label("Held-out material type")
    fig.savefig(path, dpi=160)
    plt.close(fig)


def _plot_residual_grid(
    path: Path,
    target: str,
    rows: list[dict[str, Any]],
    models: Sequence[str],
) -> None:
    fig, axes = _subplot_grid(len(models))
    for axis, model_kind in zip(axes, models):
        selected = [row for row in rows if row["model"] == model_kind]
        groups = np.asarray([row["test_group"] for row in selected], dtype=float)
        residuals = np.asarray([row["residual"] for row in selected], dtype=float)
        axis.scatter(
            groups,
            residuals,
            c=groups,
            cmap="tab10",
            s=28,
            edgecolors="white",
            linewidths=0.3,
        )
        axis.axhline(0.0, color="#111827", linestyle="--", linewidth=1.0)
        axis.set_title(MODEL_LABELS[model_kind])
        axis.set_xlabel("Held-out material type")
        axis.set_ylabel("Prediction - measured")
        axis.set_xticks(sorted({int(row["test_group"]) for row in selected}))
        axis.grid(True, alpha=0.2)
    for axis in axes[len(models) :]:
        axis.set_visible(False)
    fig.suptitle(f"CFRP grouped residuals: {target}")
    fig.subplots_adjust(
        left=0.08, right=0.97, bottom=0.08, top=0.9, wspace=0.28, hspace=0.34
    )
    fig.savefig(path, dpi=160)
    plt.close(fig)


def _subplot_grid(count: int) -> tuple[Any, np.ndarray]:
    columns = 2
    rows = math.ceil(count / columns)
    fig, axes = plt.subplots(rows, columns, figsize=(10, 4.4 * rows), squeeze=False)
    return fig, np.asarray(axes).reshape(-1)


def _build_summary(
    *,
    run_id: str,
    bundle: _DatasetBundle,
    comparison: list[dict[str, Any]],
    targets: Sequence[str],
    models: Sequence[str],
    random_state: int,
    interval_coverage: float,
    rf_estimators: int,
) -> dict[str, Any]:
    target_summaries: dict[str, Any] = {}
    for target in targets:
        rows = sorted(
            [row for row in comparison if row["target"] == target],
            key=lambda row: int(row["rank_by_mae"]),
        )
        best = rows[0]
        target_summaries[target] = {
            "target_unit": TARGET_UNITS.get(target),
            "available_sample_count": int(best["sample_count"]),
            "group_count": int(best["group_count"]),
            "best_model_by_grouped_mae": best["model"],
            "best_model_beats_mean_baseline": best["beats_mean_baseline"],
            "ranking": [row["model"] for row in rows],
            "metrics": {row["model"]: dict(row) for row in rows},
        }
    return {
        "schema_version": 1,
        "run_id": run_id,
        "created_at": _utc_now(),
        "status": "completed_with_warnings",
        "dataset_id": bundle.dataset_manifest["dataset_id"],
        "dataset_version": bundle.dataset_manifest["dataset_version"],
        "features": list(FEATURE_COLUMNS),
        "targets": target_summaries,
        "models": list(models),
        "random_state": random_state,
        "rf_estimators": rf_estimators,
        "evaluation_strategy": "leave_one_material_type_out",
        "interval_nominal_coverage": interval_coverage,
        "paper_comparison": {
            "status": "not_directly_comparable",
            "reason": (
                "The paper reports row-level leave-one-out results; this run holds "
                "out complete CFRP material types and is intentionally stricter."
            ),
        },
        "limitations": [
            "源数据只有 62 行、9 种材料类型。",
            "本实验预测表格化宏观性能，不是材料本构模型。",
            "超参数是固定基线，没有使用测试折调参。",
            "区间来自嵌套分组残差，不是经过认证的设计边界。",
            "源文件单位标签原样保留，仍需工程核验。",
            "全量模型仅用于推理；全部报告指标都来自分组 OOF 预测。",
        ],
    }


def _render_report(summary: dict[str, Any], comparison: list[dict[str, Any]]) -> str:
    sections: list[str] = []
    for target, details in summary["targets"].items():
        rows = sorted(
            [row for row in comparison if row["target"] == target],
            key=lambda row: int(row["rank_by_mae"]),
        )
        table = [
            "| 排名 | 模型 | MAE | RMSE | R2 | 相对 Mean 的 MAE 改善 | 区间覆盖率 |",
            "|---:|---|---:|---:|---:|---:|---:|",
        ]
        for row in rows:
            table.append(
                "| {rank} | `{model}` | {mae} | {rmse} | {r2} | {improvement} | {coverage} |".format(
                    rank=row["rank_by_mae"],
                    model=row["model"],
                    mae=_format_number(row["mae"]),
                    rmse=_format_number(row["rmse"]),
                    r2=_format_number(row["r2"]),
                    improvement=_format_percent(row["mae_improvement_vs_mean_pct"]),
                    coverage=_format_ratio(row["interval_empirical_coverage"]),
                )
            )
        sections.append(f"""## `{target}`

- 源标签单位：`{details['target_unit']}`
- 有效样本：`{details['available_sample_count']}`，材料类型：`{details['group_count']}`
- 严格分组 MAE 最优模型：`{details['best_model_by_grouped_mae']}`

{chr(10).join(table)}
""")
    limitations = "\n".join(f"- {item}" for item in summary["limitations"])
    return f"""# CFRP 公开实验数据分组基线报告

## 本次实验回答什么

本报告比较 Mean、Ridge、Random Forest 和 SVR 对 CFRP 宏观性能的预测能力。每次测试都完整留出一种
材料类型，测试样本及其真实值不会参与该折的训练或区间校准。这里报告的是逐样本 OOF 结果，而不是
在全量训练集上的拟合成绩。

{chr(10).join(sections)}
## 如何解释结果

- MAE、RMSE 越小越好；R2 为负表示在“预测没见过的材料类型”这一严格任务上，模型甚至不如简单基线。
- “最优”只表示当前数据、当前固定参数和当前分组协议下的最小 MAE，不是材料设计允许值。
- 预测区间由外层训练集内部再次按材料类型留一得到的残差校准，名义覆盖率为
  `{summary['interval_nominal_coverage']:.0%}`；它用于表达小样本风险，不是置信保证。
- 论文公布结果采用逐行留一法，本报告完整留出材料类型，因此数值不能直接横向判定复现成功或失败。

## 产物

- `model_comparison.csv`：每个目标和模型的汇总指标与排名。
- `fold_metrics.csv`：每个留出材料类型的独立误差。
- `predictions.csv`：逐样本真实值、预测值、残差和预测区间。
- `figures/`：预测-实测图和按材料类型的残差图。
- `models/` 与 `model_cards/`：全量有效样本重训模型及其来源约束。

## 限制

{limitations}
"""


def _read_normalized_rows(path: Path) -> dict[str, dict[str, Any]]:
    required = {
        "sample_id",
        "source_row",
        "material_type_id",
        "material_type_name",
        *FEATURE_COLUMNS,
        *TARGET_COLUMNS,
    }
    rows: dict[str, dict[str, Any]] = {}
    with path.open("r", encoding="utf-8", newline="") as handle:
        reader = csv.DictReader(handle)
        if not reader.fieldnames or not required.issubset(reader.fieldnames):
            missing = required - set(reader.fieldnames or ())
            raise ValueError(
                "Normalized CFRP CSV is missing columns: " + ", ".join(sorted(missing))
            )
        for line_number, raw in enumerate(reader, start=2):
            sample_id = str(raw.get("sample_id", "")).strip()
            if not sample_id or sample_id in rows:
                raise ValueError(
                    f"Invalid or duplicate sample_id at CSV line {line_number}."
                )
            row: dict[str, Any] = dict(raw)
            row["sample_id"] = sample_id
            row["source_row"] = _required_int(raw.get("source_row"), "source_row")
            row["material_type_id"] = _required_int(
                raw.get("material_type_id"), "material_type_id"
            )
            for column in FEATURE_COLUMNS:
                row[column] = _required_float(raw.get(column), column)
            for column in TARGET_COLUMNS:
                row[column] = _optional_float(raw.get(column), column)
            rows[sample_id] = row
    if not rows:
        raise ValueError("Normalized CFRP CSV contains no rows.")
    return rows


def _verified_artifact(root: Path, entry: Any, label: str) -> tuple[Path, str]:
    if not isinstance(entry, dict) or not entry.get("path") or not entry.get("sha256"):
        raise ValueError(f"Dataset manifest has no valid {label} artifact entry.")
    path = (root / str(entry["path"])).resolve()
    try:
        path.relative_to(root)
    except ValueError as exc:
        raise ValueError(f"Dataset artifact escapes its root: {label}") from exc
    if not path.is_file():
        raise FileNotFoundError(f"Dataset artifact does not exist: {path}")
    digest = _sha256(path)
    if digest != str(entry["sha256"]).lower():
        raise ValueError(f"Dataset artifact SHA-256 mismatch: {label}")
    if int(entry.get("size_bytes", -1)) != path.stat().st_size:
        raise ValueError(f"Dataset artifact size mismatch: {label}")
    return path, digest


def _unique_ids(value: Any, fold_id: str, role: str) -> list[str]:
    if not isinstance(value, list) or not value:
        raise ValueError(f"Fold {fold_id} has no {role} sample ids.")
    ids = [str(item) for item in value]
    if len(ids) != len(set(ids)):
        raise ValueError(f"Fold {fold_id} has duplicate {role} sample ids.")
    return ids


def _features(rows: Sequence[dict[str, Any]]) -> np.ndarray:
    values = [[float(row[column]) for column in FEATURE_COLUMNS] for row in rows]
    return np.asarray(values, dtype=float)


def _targets(rows: Sequence[dict[str, Any]], target: str) -> np.ndarray:
    return np.asarray([float(row[target]) for row in rows], dtype=float)


def _required_float(value: Any, label: str) -> float:
    result = _optional_float(value, label)
    if result is None:
        raise ValueError(f"{label} must contain a finite numeric value.")
    return result


def _optional_float(value: Any, label: str) -> float | None:
    text = "" if value is None else str(value).strip()
    if not text:
        return None
    try:
        result = float(text)
    except (TypeError, ValueError) as exc:
        raise ValueError(f"{label} contains a non-numeric value: {value!r}") from exc
    if not math.isfinite(result):
        raise ValueError(f"{label} must be finite.")
    return result


def _required_int(value: Any, label: str) -> int:
    number = _required_float(value, label)
    if not number.is_integer():
        raise ValueError(f"{label} must be an integer.")
    return int(number)


def _normalize_selection(
    values: Iterable[str], *, allowed: Sequence[str], label: str
) -> tuple[str, ...]:
    selected: list[str] = []
    for value in values:
        normalized = str(value).strip().lower()
        if normalized not in allowed:
            raise ValueError(
                f"Unsupported {label}: {value}. Allowed: {', '.join(allowed)}"
            )
        if normalized not in selected:
            selected.append(normalized)
    if not selected:
        raise ValueError(f"At least one {label} is required.")
    return tuple(selected)


def _prediction_columns() -> list[str]:
    return [
        "target",
        "target_unit",
        "model",
        "model_label",
        "fold_id",
        "test_group",
        "test_group_name",
        "sample_id",
        "source_row",
        "truth",
        "prediction",
        "residual",
        "absolute_error",
        "relative_error",
        "prediction_lower",
        "prediction_upper",
        "interval_half_width",
        "interval_covered",
        "calibration_sample_count",
    ]


def _fold_metric_columns() -> list[str]:
    return [
        "target",
        "target_unit",
        "model",
        "model_label",
        "fold_id",
        "test_group",
        "test_group_name",
        "train_count",
        "test_count",
        "calibration_sample_count",
        "mae",
        "rmse",
        "r2",
        "median_absolute_error",
        "mean_relative_error",
        "bias",
        "max_absolute_error",
        "nrmse_by_range",
        "interval_empirical_coverage",
        "interval_mean_half_width",
        "interval_half_width",
    ]


def _comparison_columns() -> list[str]:
    return [
        "target",
        "target_unit",
        "rank_by_mae",
        "model",
        "model_label",
        "sample_count",
        "group_count",
        "mae",
        "rmse",
        "r2",
        "median_absolute_error",
        "mean_relative_error",
        "bias",
        "max_absolute_error",
        "nrmse_by_range",
        "mae_improvement_vs_mean_pct",
        "beats_mean_baseline",
        "interval_empirical_coverage",
        "interval_mean_half_width",
        "interval_nominal_coverage",
        "interval_coverage_gap",
        "interval_undercoverage",
        "evaluation_strategy",
        "interval_method",
    ]


def _write_csv(
    path: Path, rows: Sequence[dict[str, Any]], columns: Sequence[str]
) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=list(columns), extrasaction="ignore")
        writer.writeheader()
        writer.writerows(rows)


def _write_json(path: Path, payload: Any) -> None:
    _write_text(path, json.dumps(payload, ensure_ascii=False, indent=2) + "\n")


def _write_text(path: Path, content: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(content, encoding="utf-8")


def _read_json(path: Path) -> dict[str, Any]:
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except json.JSONDecodeError as exc:
        raise ValueError(f"Invalid JSON: {path}") from exc
    if not isinstance(payload, dict):
        raise ValueError(f"Expected a JSON object: {path}")
    return payload


def _artifact_inventory(root: Path, *, exclude: set[Path]) -> list[dict[str, Any]]:
    excluded = {path.resolve() for path in exclude}
    artifacts = []
    for path in sorted(item for item in root.rglob("*") if item.is_file()):
        if path.resolve() in excluded:
            continue
        artifacts.append(
            {
                "path": path.relative_to(root).as_posix(),
                "sha256": _sha256(path),
                "size_bytes": path.stat().st_size,
            }
        )
    return artifacts


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _runtime_versions() -> dict[str, str]:
    return {
        "python": platform.python_version(),
        "numpy": _package_version("numpy"),
        "scikit_learn": _package_version("scikit-learn"),
        "matplotlib": _package_version("matplotlib"),
    }


def _package_version(name: str) -> str:
    try:
        return version(name)
    except PackageNotFoundError:  # pragma: no cover - core dependencies are packaged
        return "unknown"


def _run_id() -> str:
    stamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    return f"{stamp}_{uuid4().hex[:8]}"


def _utc_now() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


def _model_order(model: str) -> int:
    try:
        return DEFAULT_MODELS.index(model)
    except ValueError:
        return len(DEFAULT_MODELS)


def _format_number(value: Any) -> str:
    return "N/A" if value is None else f"{float(value):.4g}"


def _format_percent(value: Any) -> str:
    return "N/A" if value is None else f"{float(value):.1f}%"


def _format_ratio(value: Any) -> str:
    return "N/A" if value is None else f"{float(value):.1%}"


__all__ = [
    "DEFAULT_DATASET_DIR",
    "DEFAULT_MODELS",
    "DEFAULT_OUTPUT_ROOT",
    "ExperimentalBaselineRun",
    "load_cfrp_baseline_dataset",
    "train_cfrp_grouped_baselines",
    "validate_target_split_contract",
]
