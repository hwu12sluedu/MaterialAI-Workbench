"""Multi-fidelity surrogate models for pyLabFEA and Abaqus data."""

from __future__ import annotations

import csv
import json
import pickle
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from typing import Any

import matplotlib

matplotlib.use("Agg", force=True)
import matplotlib.pyplot as plt
import numpy as np
from sklearn.ensemble import RandomForestRegressor
from sklearn.metrics import mean_absolute_error, r2_score

from material_ai_workbench.config import SURROGATES_ROOT
from material_ai_workbench.logging_config import get_logger


logger = get_logger(__name__)


@dataclass
class MultiFidelityResult:
    run_dir: Path
    low_model_path: Path
    residual_model_path: Path
    predictions_csv: Path
    plot_path: Path
    metrics_path: Path
    report_path: Path
    metrics: dict[str, Any]


def train_multi_fidelity(
    X_low: np.ndarray,
    y_low: np.ndarray,
    X_high: np.ndarray,
    y_high: np.ndarray,
    *,
    name: str = "multi_fidelity",
    output_root: Path = SURROGATES_ROOT,
    random_state: int = 42,
) -> MultiFidelityResult:
    """Train an additive correction model: high ~= low_model + residual_model."""

    X_low = np.asarray(X_low, dtype=float)
    y_low = np.asarray(y_low, dtype=float).ravel()
    X_high = np.asarray(X_high, dtype=float)
    y_high = np.asarray(y_high, dtype=float).ravel()
    _validate_arrays(X_low, y_low, X_high, y_high)

    run_dir = _unique_run_dir(output_root, name)
    run_dir.mkdir(parents=True, exist_ok=False)

    low_model = RandomForestRegressor(n_estimators=200, random_state=random_state)
    low_model.fit(X_low, y_low)
    low_at_high = low_model.predict(X_high)
    residuals = y_high - low_at_high

    residual_model = RandomForestRegressor(n_estimators=120, random_state=random_state)
    residual_model.fit(X_high, residuals)
    combined = low_at_high + residual_model.predict(X_high)

    baseline = RandomForestRegressor(n_estimators=200, random_state=random_state)
    baseline.fit(X_high, y_high)
    baseline_pred = baseline.predict(X_high)

    mf_mae = float(mean_absolute_error(y_high, combined))
    baseline_mae = float(mean_absolute_error(y_high, baseline_pred))
    metrics = {
        "created_at": datetime.now().isoformat(timespec="seconds"),
        "n_low_fidelity": int(len(X_low)),
        "n_high_fidelity": int(len(X_high)),
        "multi_fidelity_mae": mf_mae,
        "baseline_single_fidelity_mae": baseline_mae,
        "multi_fidelity_r2": _safe_r2(y_high, combined),
        "residual_mean": float(np.mean(residuals)),
        "residual_std": float(np.std(residuals)),
        "improvement_fraction": float((baseline_mae - mf_mae) / baseline_mae) if baseline_mae > 1e-12 else None,
    }

    low_model_path = run_dir / "base_low_fidelity_model.pkl"
    residual_model_path = run_dir / "residual_correction_model.pkl"
    with low_model_path.open("wb") as handle:
        pickle.dump(low_model, handle)
    with residual_model_path.open("wb") as handle:
        pickle.dump(residual_model, handle)

    predictions_csv = run_dir / "predictions.csv"
    _write_predictions(predictions_csv, y_high, low_at_high, residuals, combined, baseline_pred)
    plot_path = run_dir / "multi_fidelity_comparison.png"
    _plot_comparison(plot_path, y_high, combined, baseline_pred, metrics)
    metrics_path = run_dir / "multi_fidelity_metrics.json"
    metrics_path.write_text(json.dumps(metrics, indent=2), encoding="utf-8")
    report_path = run_dir / "multi_fidelity_report.md"
    report_path.write_text(_report(metrics, predictions_csv, plot_path), encoding="utf-8")
    logger.info("Multi-fidelity surrogate trained: %s", run_dir)

    return MultiFidelityResult(
        run_dir=run_dir,
        low_model_path=low_model_path,
        residual_model_path=residual_model_path,
        predictions_csv=predictions_csv,
        plot_path=plot_path,
        metrics_path=metrics_path,
        report_path=report_path,
        metrics=metrics,
    )


def _validate_arrays(X_low: np.ndarray, y_low: np.ndarray, X_high: np.ndarray, y_high: np.ndarray) -> None:
    if X_low.ndim != 2 or X_high.ndim != 2:
        raise ValueError("X_low and X_high must be 2D arrays.")
    if len(X_low) != len(y_low) or len(X_high) != len(y_high):
        raise ValueError("Feature and target lengths do not match.")
    if len(X_low) < 2 or len(X_high) < 2:
        raise ValueError("At least two low-fidelity and two high-fidelity samples are required.")
    if X_low.shape[1] != X_high.shape[1]:
        raise ValueError("Low- and high-fidelity feature dimensions must match.")


def _write_predictions(path: Path, y_true: np.ndarray, base: np.ndarray, residual: np.ndarray, combined: np.ndarray, baseline: np.ndarray) -> None:
    with path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=["sample_index", "y_true", "base_pred", "residual", "combined_pred", "baseline_pred"])
        writer.writeheader()
        for idx, values in enumerate(zip(y_true, base, residual, combined, baseline)):
            writer.writerow(
                {
                    "sample_index": idx,
                    "y_true": float(values[0]),
                    "base_pred": float(values[1]),
                    "residual": float(values[2]),
                    "combined_pred": float(values[3]),
                    "baseline_pred": float(values[4]),
                }
            )


def _plot_comparison(path: Path, y_true: np.ndarray, combined: np.ndarray, baseline: np.ndarray, metrics: dict[str, Any]) -> None:
    fig, axes = plt.subplots(1, 2, figsize=(10, 4.5), dpi=150)
    axes[0].scatter(y_true, baseline, marker="x", color="#6b7280", label="single fidelity")
    axes[0].scatter(y_true, combined, color="#2563eb", label="multi fidelity")
    lower = float(min(np.min(y_true), np.min(combined), np.min(baseline)))
    upper = float(max(np.max(y_true), np.max(combined), np.max(baseline)))
    if abs(upper - lower) < 1e-12:
        lower -= 1.0
        upper += 1.0
    axes[0].plot([lower, upper], [lower, upper], "k--", linewidth=1)
    axes[0].set_xlabel("True high-fidelity target")
    axes[0].set_ylabel("Predicted target")
    axes[0].legend()
    axes[0].grid(True, alpha=0.25)
    axes[1].bar(["single", "multi"], [metrics["baseline_single_fidelity_mae"], metrics["multi_fidelity_mae"]], color=["#9ca3af", "#2563eb"])
    axes[1].set_ylabel("MAE")
    axes[1].grid(True, axis="y", alpha=0.25)
    fig.tight_layout()
    fig.savefig(path)
    plt.close(fig)


def _report(metrics: dict[str, Any], predictions_csv: Path, plot_path: Path) -> str:
    improvement = metrics.get("improvement_fraction")
    improvement_text = "N/A" if improvement is None else f"{100.0 * float(improvement):.2f}%"
    return f"""# Multi-Fidelity Surrogate Report

## Data

- Low-fidelity samples: `{metrics["n_low_fidelity"]}`
- High-fidelity samples: `{metrics["n_high_fidelity"]}`

## Metrics

- Multi-fidelity MAE: `{metrics["multi_fidelity_mae"]}`
- Single-fidelity baseline MAE: `{metrics["baseline_single_fidelity_mae"]}`
- Improvement: `{improvement_text}`
- Multi-fidelity R2: `{metrics["multi_fidelity_r2"]}`
- Residual mean/std: `{metrics["residual_mean"]}` / `{metrics["residual_std"]}`

## Outputs

- Predictions: `{predictions_csv}`
- Plot: `{plot_path}`
"""


def _safe_r2(y_true: np.ndarray, y_pred: np.ndarray) -> float | None:
    if len(y_true) < 2:
        return None
    try:
        return float(r2_score(y_true, y_pred))
    except Exception:
        return None


def _unique_run_dir(root: Path, name: str) -> Path:
    stamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    safe = "".join(ch if ch.isalnum() or ch in ("-", "_") else "_" for ch in str(name)).strip("_") or "multi_fidelity"
    base = Path(root) / f"{stamp}_{safe}"
    if not base.exists():
        return base
    idx = 2
    while True:
        candidate = Path(root) / f"{stamp}_{safe}_{idx}"
        if not candidate.exists():
            return candidate
        idx += 1
