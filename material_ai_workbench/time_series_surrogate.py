"""Time-series surrogate for ODB frame curves."""

from __future__ import annotations

import csv
import json
import pickle
from datetime import datetime
from pathlib import Path
from typing import Any

import matplotlib

matplotlib.use("Agg", force=True)
import matplotlib.pyplot as plt
import numpy as np
from sklearn.ensemble import RandomForestRegressor
from sklearn.feature_extraction import DictVectorizer
from sklearn.neural_network import MLPRegressor
from sklearn.preprocessing import StandardScaler

from material_ai_workbench.config import SURROGATES_ROOT
from material_ai_workbench.logging_config import get_logger


logger = get_logger(__name__)
N_TIME_POINTS = 50
IDENTIFIER_COLUMNS = {"case_id", "title", "source_folder", "latest_frame_series_csv", "updated_at"}


def resample_curve(time_values: np.ndarray, field_values: np.ndarray, n_points: int = N_TIME_POINTS) -> np.ndarray:
    """Interpolate a curve to a normalized 0-1 grid."""

    time_values = np.asarray(time_values, dtype=float)
    field_values = np.asarray(field_values, dtype=float)
    if len(time_values) != len(field_values) or len(time_values) < 2:
        raise ValueError("time_values and field_values must have the same length >= 2.")
    order = np.argsort(time_values)
    time_values = time_values[order]
    field_values = field_values[order]
    span = float(time_values[-1] - time_values[0])
    t_norm = (time_values - time_values[0]) / (span if abs(span) > 1e-12 else 1.0)
    return np.interp(np.linspace(0.0, 1.0, int(n_points)), t_norm, field_values)


def train_time_series_surrogate(
    frame_series_index_csv: str | Path,
    case_dataset_csv: str | Path,
    *,
    target_field: str = "S",
    target_metric: str = "max",
    n_time_points: int = N_TIME_POINTS,
    model_kind: str = "random_forest",
    output_root: Path = SURROGATES_ROOT,
    random_state: int = 42,
) -> dict[str, Any]:
    """Train a model that predicts a resampled frame curve from case features."""

    case_rows = _read_csv(Path(case_dataset_csv))
    index_rows = _read_csv(Path(frame_series_index_csv))
    if not case_rows:
        raise ValueError("case_dataset_csv contains no rows.")
    curves, features, case_ids = _collect_curves(case_rows, index_rows, target_field, target_metric, int(n_time_points))
    if len(curves) < 2:
        return {"error": f"Only {len(curves)} valid samples found for training"}

    vectorizer = DictVectorizer(sparse=False)
    X = vectorizer.fit_transform(features)
    Y = np.asarray(curves, dtype=float)
    scaler = StandardScaler()
    Y_scaled = scaler.fit_transform(Y)

    models = []
    for idx in range(Y_scaled.shape[1]):
        model = _make_model(model_kind, random_state)
        model.fit(X, Y_scaled[:, idx])
        models.append(model)
    Y_pred = scaler.inverse_transform(np.column_stack([model.predict(X) for model in models]))
    mae_per_point = np.mean(np.abs(Y - Y_pred), axis=0)
    overall_mae = float(np.mean(mae_per_point))

    run_dir = _unique_run_dir(output_root, f"ts_{target_field}_{target_metric}")
    run_dir.mkdir(parents=True, exist_ok=False)
    model_path = run_dir / "time_series_model.pkl"
    with model_path.open("wb") as handle:
        pickle.dump(
            {
                "models": models,
                "vectorizer": vectorizer,
                "scaler": scaler,
                "n_time_points": int(n_time_points),
                "target_field": target_field,
                "target_metric": target_metric,
            },
            handle,
        )
    predictions_csv = run_dir / "time_series_predictions.csv"
    _write_predictions(predictions_csv, case_ids, Y, Y_pred)
    plot_path = run_dir / "prediction_curves.png"
    _plot_curves(plot_path, Y, Y_pred, overall_mae)
    metrics = {
        "created_at": datetime.now().isoformat(timespec="seconds"),
        "overall_mae": overall_mae,
        "n_samples": len(curves),
        "n_features": int(X.shape[1]),
        "n_time_points": int(n_time_points),
        "target_field": target_field,
        "target_metric": target_metric,
        "model_kind": model_kind,
    }
    metrics_path = run_dir / "time_series_metrics.json"
    metrics_path.write_text(json.dumps(metrics, indent=2), encoding="utf-8")
    report_path = run_dir / "time_series_report.md"
    report_path.write_text(_report(metrics, model_path, predictions_csv, plot_path), encoding="utf-8")
    logger.info("Time-series surrogate trained: %s", run_dir)
    return {
        "run_dir": str(run_dir),
        "model_path": str(model_path),
        "predictions_csv": str(predictions_csv),
        "plot_path": str(plot_path),
        "metrics_path": str(metrics_path),
        "report_path": str(report_path),
        "metrics": metrics,
    }


def _collect_curves(
    case_rows: list[dict[str, str]],
    index_rows: list[dict[str, str]],
    target_field: str,
    target_metric: str,
    n_time_points: int,
) -> tuple[list[np.ndarray], list[dict[str, Any]], list[str]]:
    by_case: dict[str, list[dict[str, str]]] = {}
    for row in index_rows:
        by_case.setdefault(str(row.get("case_id", "")), []).append(row)
    curves: list[np.ndarray] = []
    features: list[dict[str, Any]] = []
    case_ids: list[str] = []
    for case_row in case_rows:
        case_id = str(case_row.get("case_id", ""))
        for index_row in by_case.get(case_id, []):
            curve_csv = Path(index_row.get("frame_series_csv") or index_row.get("csv_path") or "")
            if not curve_csv.is_file():
                continue
            curve = _read_curve(curve_csv, target_field, target_metric)
            if curve is None:
                continue
            times, values = curve
            curves.append(resample_curve(times, values, n_time_points))
            features.append(_numeric_features(case_row))
            case_ids.append(case_id)
    return curves, features, case_ids


def _read_curve(path: Path, target_field: str, target_metric: str) -> tuple[np.ndarray, np.ndarray] | None:
    times: list[float] = []
    values: list[float] = []
    for row in _read_csv(path):
        field = str(row.get("field", row.get("Field", ""))).upper()
        metric = str(row.get("metric", row.get("Metric", ""))).lower()
        if field and field != target_field.upper():
            continue
        if metric and metric != target_metric.lower():
            continue
        time_value = _to_float(row.get("frame_value") or row.get("time") or row.get("FrameValue"))
        value = _to_float(row.get("value") or row.get("mean") or row.get("max") or row.get("Mean") or row.get("Max"))
        if time_value is None or value is None:
            continue
        times.append(time_value)
        values.append(value)
    if len(times) < 2:
        return None
    return np.asarray(times, dtype=float), np.asarray(values, dtype=float)


def _numeric_features(row: dict[str, str]) -> dict[str, Any]:
    features: dict[str, Any] = {}
    for key, value in row.items():
        if key in IDENTIFIER_COLUMNS:
            continue
        number = _to_float(value)
        if number is not None:
            features[key] = number
    return features


def _make_model(model_kind: str, random_state: int) -> Any:
    if str(model_kind).lower() in {"mlp", "nn", "neural_network"}:
        return MLPRegressor(hidden_layer_sizes=(32, 16), max_iter=1000, random_state=random_state)
    return RandomForestRegressor(n_estimators=120, random_state=random_state)


def _write_predictions(path: Path, case_ids: list[str], truth: np.ndarray, pred: np.ndarray) -> None:
    columns = ["case_id", "time_index", "truth", "prediction", "error"]
    with path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=columns)
        writer.writeheader()
        for row_idx, case_id in enumerate(case_ids):
            for time_idx in range(truth.shape[1]):
                writer.writerow(
                    {
                        "case_id": case_id,
                        "time_index": time_idx,
                        "truth": float(truth[row_idx, time_idx]),
                        "prediction": float(pred[row_idx, time_idx]),
                        "error": float(pred[row_idx, time_idx] - truth[row_idx, time_idx]),
                    }
                )


def _plot_curves(path: Path, truth: np.ndarray, pred: np.ndarray, overall_mae: float) -> None:
    n_plot = min(5, len(truth))
    fig, axes = plt.subplots(1, n_plot, figsize=(max(4, 3.2 * n_plot), 3.6), dpi=150)
    if n_plot == 1:
        axes = [axes]
    grid = np.linspace(0.0, 1.0, truth.shape[1])
    for idx in range(n_plot):
        axes[idx].plot(grid, truth[idx], color="#2563eb", label="truth")
        axes[idx].plot(grid, pred[idx], color="#dc2626", linestyle="--", label="pred")
        axes[idx].set_title(f"Sample {idx + 1}")
        axes[idx].grid(True, alpha=0.25)
    axes[0].legend(fontsize=8)
    fig.suptitle(f"Time-series surrogate, MAE={overall_mae:.4g}")
    fig.tight_layout()
    fig.savefig(path)
    plt.close(fig)


def _report(metrics: dict[str, Any], model_path: Path, predictions_csv: Path, plot_path: Path) -> str:
    return f"""# Time-Series Surrogate Report

## Metrics

- Target: `{metrics["target_field"]}` / `{metrics["target_metric"]}`
- Samples: `{metrics["n_samples"]}`
- Features: `{metrics["n_features"]}`
- Time points: `{metrics["n_time_points"]}`
- Overall MAE: `{metrics["overall_mae"]}`

## Outputs

- Model: `{model_path}`
- Predictions: `{predictions_csv}`
- Plot: `{plot_path}`
"""


def _read_csv(path: Path) -> list[dict[str, str]]:
    with path.open("r", encoding="utf-8", newline="") as handle:
        return list(csv.DictReader(handle))


def _to_float(value: Any) -> float | None:
    try:
        if value in (None, ""):
            return None
        return float(str(value).strip())
    except (TypeError, ValueError):
        return None


def _unique_run_dir(root: Path, name: str) -> Path:
    stamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    safe = "".join(ch if ch.isalnum() or ch in ("-", "_") else "_" for ch in str(name)).strip("_") or "time_series"
    base = Path(root) / f"{stamp}_{safe}"
    if not base.exists():
        return base
    idx = 2
    while True:
        candidate = Path(root) / f"{stamp}_{safe}_{idx}"
        if not candidate.exists():
            return candidate
        idx += 1
