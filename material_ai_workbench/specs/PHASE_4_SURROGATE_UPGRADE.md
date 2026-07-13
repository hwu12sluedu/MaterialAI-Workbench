# Phase 4: Surrogate Model Upgrade

## Objective
Advance surrogate models from "pipeline validation only" to credible engineering prediction tools with uncertainty quantification, multi-fidelity support, and time-series prediction capability.

## Prerequisites
- Phase 0 required
- Phase 1.1 (K-fold CV) strongly recommended
- Phase 3.2 (ODB frame series queue) recommended for Task 4.3

---

## Task 4.1: Uncertainty Quantification

### Context
`surrogate_model.py` predicts scalar values (max Mises, max U) but provides no confidence intervals. An engineer needs to know: "The predicted max stress is 245 MPa, plus or minus 15 MPa." Implement two approaches: quantile regression for Random Forest, and ensemble standard deviation.

### File to modify
`D:\githubproject\pyLabFEA\material_ai_workbench\surrogate_model.py`

### Changes

#### a) Add uncertainty methods to `SurrogateRun` and `train_surrogate_from_dataset()`

Add parameter `uncertainty: str = "none"` with options: `"none"`, `"ensemble"`, `"quantile"`.

**Ensemble method** (simplest, always available):
For Random Forest, each tree in the ensemble produces an independent prediction. The standard deviation across trees gives a rough uncertainty estimate. Add after training:

```python
if uncertainty == "ensemble" and model_kind == "random_forest":
    rf_model = pipeline.named_steps["model"]
    # Get per-tree predictions on test set
    tree_preds = np.array([
        tree.predict(X_test_scaled)
        for tree in rf_model.estimators_
    ])
    pred_mean = tree_preds.mean(axis=0)
    pred_std = tree_preds.std(axis=0)
    # Save as additional columns in predictions.csv
```

**Quantile regression** (requires `sklearn.ensemble.RandomForestQuantileRegressor` or `QuantileRegressor`):
```python
if uncertainty == "quantile":
    from sklearn.ensemble import GradientBoostingRegressor
    # Train three models: median (q=0.5), lower (q=0.05), upper (q=0.95)
    models = {}
    for q, label in [(0.05, "lower"), (0.5, "median"), (0.95, "upper")]:
        gb = GradientBoostingRegressor(
            loss="quantile", alpha=q,
            n_estimators=200, max_depth=4,
            random_state=random_state,
        )
        gb.fit(X_train_vec, y_train)
        models[label] = gb
    # Store all three models in a dict pickle
```

#### b) Update `predictions.csv` output

Add columns:
- `predicted` (mean prediction)
- `prediction_std` (if ensemble)
- `prediction_lower` (if quantile, 5th percentile)
- `prediction_upper` (if quantile, 95th percentile)

#### c) Update prediction-vs-truth plot

Add error bars or shaded region showing the uncertainty band around predictions.

#### d) Update the markdown report

Add a "Prediction Uncertainty" section:
- Mean prediction interval width (upper - lower) / 2
- Coverage: fraction of true values that fall within [lower, upper]

### Acceptance Criteria
- Train with `uncertainty="ensemble"` → `predictions.csv` has `prediction_std` column
- Plot shows error bars on predictions
- Ensemble std is larger for data-poor regions (qualitative check)
- Coverage of 90% prediction interval is approximately 90% on holdout set

---

## Task 4.2: Multi-Fidelity Surrogate Model

### Context
The project has two sources of training data:
- **Low fidelity**: pyLabFEA small-FE stress-strain curves (cheap, abundant)
- **High fidelity**: Abaqus simulations (expensive, scarce — 5-20 samples)

A multi-fidelity model can leverage both: use cheap pyLabFEA data to learn the overall trend, then correct with expensive Abaqus data.

### Design Pattern: Co-Kriging / Hierarchical Gaussian Process

For MVP, implement a simple **additive correction** model:
1. Train a base model on low-fidelity data
2. Train a second model on the residuals (high_fidelity - low_fidelity_prediction) using only the high-fidelity data
3. Final prediction = base_model_prediction + residual_correction

### New file: `multi_fidelity.py`

```python
"""Multi-fidelity surrogate models combining pyLabFEA and Abaqus data.

Implements additive correction:
  pred_high(x) = model_low(x) + model_residual(x)

Where:
  model_low  -> trained on all available data (mostly low-fidelity)
  model_residual -> trained on (high_fidelity_data - model_low_prediction)
"""

from __future__ import annotations

import json
import pickle
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from typing import Any

import matplotlib
matplotlib.use("Agg")
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
    metrics: dict[str, float]
    predictions_csv: Path
    report_path: Path


def train_multi_fidelity(
    X_low: np.ndarray,      # features for low-fidelity data
    y_low: np.ndarray,       # targets for low-fidelity data
    X_high: np.ndarray,      # features for high-fidelity data
    y_high: np.ndarray,      # targets for high-fidelity data
    name: str = "multi_fidelity",
    random_state: int = 42,
) -> MultiFidelityResult:
    """Train a multi-fidelity surrogate.

    Steps:
    1. Train base model on all low-fidelity data
    2. Predict low-fidelity values at high-fidelity input points
    3. Train residual model on (y_high - pred_low) at high-fidelity points
    4. Combine: prediction = base(x) + residual(x)
    """
    run_dir = SURROGATES_ROOT / f"{datetime.now().strftime('%Y%m%d_%H%M%S')}_{name}"
    run_dir.mkdir(parents=True, exist_ok=True)

    # Step 1: Base model on low-fidelity
    base_model = RandomForestRegressor(n_estimators=200, random_state=random_state)
    base_model.fit(X_low, y_low)
    logger.info("Base model trained on %d low-fidelity samples", len(X_low))

    # Step 2: Low-fidelity predictions at high-fidelity points
    y_low_at_high = base_model.predict(X_high)
    residuals = y_high - y_low_at_high
    logger.info("Residual mean: %.4f, std: %.4f", float(np.mean(residuals)),
                float(np.std(residuals)))

    # Step 3: Residual model
    residual_model = RandomForestRegressor(n_estimators=100, random_state=random_state)
    residual_model.fit(X_high, residuals)

    # Step 4: Evaluate on high-fidelity data (using leave-one-out-like approach)
    combined_pred = base_model.predict(X_high) + residual_model.predict(X_high)
    mae = mean_absolute_error(y_high, combined_pred)
    r2 = r2_score(y_high, combined_pred)

    # Compare with single-fidelity baseline
    baseline = RandomForestRegressor(n_estimators=200, random_state=random_state)
    baseline.fit(X_high, y_high)
    baseline_pred = baseline.predict(X_high)
    baseline_mae = mean_absolute_error(y_high, baseline_pred)

    metrics = {
        "multi_fidelity_mae": float(mae),
        "multi_fidelity_r2": float(r2),
        "baseline_single_fidelity_mae": float(baseline_mae),
        "n_low_fidelity": len(X_low),
        "n_high_fidelity": len(X_high),
        "residual_mean": float(np.mean(residuals)),
        "residual_std": float(np.std(residuals)),
    }

    # Save
    low_model_path = run_dir / "base_model.pkl"
    residual_model_path = run_dir / "residual_model.pkl"
    with open(low_model_path, "wb") as f:
        pickle.dump(base_model, f)
    with open(residual_model_path, "wb") as f:
        pickle.dump(residual_model, f)

    # Predictions CSV
    predictions_csv = run_dir / "predictions.csv"
    with open(predictions_csv, "w") as f:
        f.write("y_true,base_pred,residual,combined_pred,baseline_pred\n")
        for yt, bp, r, cp, blp in zip(y_high, y_low_at_high, residuals,
                                       combined_pred, baseline_pred):
            f.write(f"{yt},{bp},{r},{cp},{blp}\n")

    # Plot
    plot_path = run_dir / "multi_fidelity_comparison.png"
    fig, axes = plt.subplots(1, 2, figsize=(12, 5))
    axes[0].scatter(y_high, combined_pred, alpha=0.7, label="Multi-fidelity")
    axes[0].scatter(y_high, baseline_pred, alpha=0.7, marker="x", label="Single-fidelity")
    lims = [min(y_high.min(), combined_pred.min()), max(y_high.max(), combined_pred.max())]
    axes[0].plot(lims, lims, "k--", alpha=0.3)
    axes[0].set_xlabel("True")
    axes[0].set_ylabel("Predicted")
    axes[0].set_title(f"Multi-fidelity MAE={mae:.3f} vs Baseline MAE={baseline_mae:.3f}")
    axes[0].legend()

    axes[1].bar(["Single-fidelity", "Multi-fidelity"], [baseline_mae, mae], color=["gray", "steelblue"])
    axes[1].set_ylabel("MAE")
    axes[1].set_title("Error Comparison")
    fig.tight_layout()
    fig.savefig(plot_path, dpi=150)
    plt.close(fig)

    # Report
    report_path = run_dir / "multi_fidelity_report.md"
    improvement = (baseline_mae - mae) / baseline_mae * 100 if baseline_mae > 0 else 0
    report_path.write_text(f"""# Multi-Fidelity Surrogate Report

## Data
- Low-fidelity samples: {len(X_low)}
- High-fidelity samples: {len(X_high)}

## Results
| Metric | Value |
|---|---:|
| Multi-fidelity MAE | {mae:.4f} |
| Multi-fidelity R² | {r2:.4f} |
| Single-fidelity MAE | {baseline_mae:.4f} |
| Improvement | {improvement:.1f}% |
| Residual mean | {np.mean(residuals):.4f} |
| Residual std | {np.std(residuals):.4f} |

## Interpretation
{'Multi-fidelity model outperforms single-fidelity baseline by ' + f'{improvement:.1f}%.' if improvement > 0 else 'Multi-fidelity did not improve over baseline. This can happen when low-fidelity data is not informative for the target.'}
""")

    return MultiFidelityResult(
        run_dir=run_dir,
        low_model_path=low_model_path,
        residual_model_path=residual_model_path,
        metrics=metrics,
        predictions_csv=predictions_csv,
        report_path=report_path,
    )
```

#### b) Integration point
Add a "Multi-Fidelity" option in `streamlit_app.py` `_surrogate_panel()`. The UI should:
1. Let the user select a low-fidelity dataset (e.g., pyLabFEA curves from batch runs)
2. Select a high-fidelity dataset (e.g., Abaqus-verified cases)
3. Map features from both to a common space
4. Call `train_multi_fidelity()` and show the comparison plot

### Acceptance Criteria
- With 3 high-fidelity and 20 low-fidelity samples, multi-fidelity MAE < single-fidelity MAE
- Report correctly states improvement (or lack thereof)
- Predictions CSV has all 5 columns
- Plot shows both models on the same scatter

---

## Task 4.3: Time-Series Surrogate for Frame Curves

### Context
`frame_series_index.csv` points to per-frame ODB curve CSVs. Currently surrogate models only predict scalar max values. A time-series model can predict the full stress-strain or Mises-vs-time curve for a given set of input parameters.

### Design
Use scikit-learn's `MLPRegressor` (or a simple sklearn-compatible approach) to predict the full frame curve. For MVP, represent each curve as a fixed-length vector by interpolating to N uniformly spaced time points.

### New file: `time_series_surrogate.py`

```python
"""Time-series surrogate for predicting full ODB frame curves.

Resamples each frame series to a fixed number of points,
then trains a regressor to predict the resampled curve.
"""

from __future__ import annotations

import json
import pickle
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np
from sklearn.ensemble import RandomForestRegressor
from sklearn.metrics import mean_absolute_error, r2_score
from sklearn.preprocessing import StandardScaler

from material_ai_workbench.config import SURROGATES_ROOT
from material_ai_workbench.logging_config import get_logger

logger = get_logger(__name__)

N_TIME_POINTS = 50  # Resample all curves to 50 uniform time steps


def resample_curve(time_values: np.ndarray, field_values: np.ndarray,
                   n_points: int = N_TIME_POINTS) -> np.ndarray:
    """Linearly interpolate a curve to n_points uniformly spaced positions."""
    t_norm = (time_values - time_values[0]) / (time_values[-1] - time_values[0] + 1e-12)
    t_new = np.linspace(0, 1, n_points)
    return np.interp(t_new, t_norm, field_values)


def train_time_series_surrogate(
    frame_series_index_csv: str | Path,
    case_dataset_csv: str | Path,
    target_field: str = "S",
    target_metric: str = "max_mises",
    n_time_points: int = N_TIME_POINTS,
    model_kind: str = "random_forest",
    random_state: int = 42,
) -> dict:
    """Train a model that predicts the full frame curve for a given case.

    Reads frame_series_index.csv to find per-case ODB frame CSVs,
    reads case_dataset.csv for input features,
    resamples curves to n_time_points,
    trains a separate model per time point (or a multi-output regressor).

    Returns a dict with model paths, metrics, and run directory.
    """
    import csv

    # Load case features
    with open(case_dataset_csv, newline="", encoding="utf-8") as f:
        case_rows = list(csv.DictReader(f))

    # Load frame series index
    with open(frame_series_index_csv, newline="", encoding="utf-8") as f:
        fs_rows = list(csv.DictReader(f))

    # Build training data
    X_list = []       # features per case
    Y_curves = []     # resampled curves (each: n_time_points values)

    for case_row in case_rows:
        case_id = case_row["case_id"]
        # Find frame series for this case
        fs_rows_case = [r for r in fs_rows if r["case_id"] == case_id]

        for fs_row in fs_rows_case:
            if target_field not in fs_row.get("fields", ""):
                continue

            # Read the frame curve CSV
            curve_csv = fs_row.get("frame_series_csv")
            if not curve_csv or not Path(curve_csv).exists():
                continue

            # Load and filter by target field + metric
            times, values = [], []
            with open(curve_csv, newline="", encoding="utf-8") as cf:
                for row in csv.DictReader(cf):
                    if (row.get("field") == target_field and
                        row.get("metric") == target_metric):
                        times.append(float(row["frame_value"]))
                        values.append(float(row["mean"]))

            if len(times) < 3:
                continue

            curve = resample_curve(np.array(times), np.array(values), n_time_points)
            Y_curves.append(curve)

            # Extract numeric features from case_row
            feat = {k: float(v) for k, v in case_row.items()
                    if k not in ("case_id", "title", "source_folder",
                                 "latest_frame_series_csv", "updated_at")
                    and v and v.replace(".", "").replace("-", "").isdigit()}
            X_list.append(feat)

    if len(X_list) < 2:
        return {"error": f"Only {len(X_list)} valid samples found for training"}

    # Convert to arrays
    from sklearn.feature_extraction import DictVectorizer
    vec = DictVectorizer(sparse=False)
    X = vec.fit_transform(X_list)
    Y = np.array(Y_curves)
    scaler = StandardScaler()
    Y_scaled = scaler.fit_transform(Y)

    # Train separate model per time point (simplest approach for MVP)
    models = []
    for t in range(n_time_points):
        if model_kind == "random_forest":
            model = RandomForestRegressor(n_estimators=100, random_state=random_state)
        else:
            from sklearn.neural_network import MLPRegressor
            model = MLPRegressor(hidden_layer_sizes=(32, 16), max_iter=1000,
                                 random_state=random_state)
        model.fit(X, Y_scaled[:, t])
        models.append(model)

    # Evaluate (in-sample for MVP — too few samples for holdout)
    Y_pred_scaled = np.column_stack([m.predict(X) for m in models])
    Y_pred = scaler.inverse_transform(Y_pred_scaled)

    mae_per_point = np.mean(np.abs(Y - Y_pred), axis=0)
    overall_mae = float(np.mean(mae_per_point))

    # Save
    run_dir = SURROGATES_ROOT / f"{datetime.now().strftime('%Y%m%d_%H%M%S')}_ts_{target_field}_{target_metric}"
    run_dir.mkdir(parents=True, exist_ok=True)

    model_path = run_dir / "time_series_model.pkl"
    with open(model_path, "wb") as f:
        pickle.dump({
            "models": models,
            "vectorizer": vec,
            "scaler": scaler,
            "n_time_points": n_time_points,
            "target_field": target_field,
            "target_metric": target_metric,
        }, f)

    # Plot a few predictions vs actual
    n_plot = min(5, len(X))
    fig, axes = plt.subplots(1, n_plot, figsize=(15, 4))
    for i in range(n_plot):
        t_grid = np.linspace(0, 1, n_time_points)
        axes[i].plot(t_grid, Y[i], "b-", label="True", linewidth=2)
        axes[i].plot(t_grid, Y_pred[i], "r--", label="Pred", linewidth=1.5)
        axes[i].set_title(f"Sample {i+1}")
        axes[i].legend(fontsize=7)
    fig.suptitle(f"Time-Series Surrogate: {target_field} {target_metric} (MAE={overall_mae:.3f})")
    fig.tight_layout()
    plot_path = run_dir / "prediction_curves.png"
    fig.savefig(plot_path, dpi=150)
    plt.close(fig)

    metrics = {
        "overall_mae": overall_mae,
        "n_samples": len(X),
        "n_time_points": n_time_points,
        "n_features": X.shape[1],
    }

    with open(run_dir / "metrics.json", "w") as f:
        json.dump(metrics, f, indent=2)

    logger.info("Time-series surrogate trained: %d samples, MAE=%.4f", len(X), overall_mae)

    return {
        "run_dir": str(run_dir),
        "model_path": str(model_path),
        "plot_path": str(plot_path),
        "metrics": metrics,
    }
```

#### b) Integration into Streamlit

In `streamlit_app.py` `_surrogate_panel()`, add a "Time Series" section:
1. Select a dataset (must have frame_series_index.csv)
2. Select target field (S-Mises, PEEQ, U, RF)
3. Select metric (mean, max)
4. Click "Train Time-Series Surrogate"
5. Show predicted vs. actual curves for a few samples

### Acceptance Criteria
- With a dataset containing frame series from 3+ cases, training completes without error
- Prediction curves visually match true curves for trained samples
- Model pickle can be loaded and used to predict curves for new input parameters
- Report correctly states number of samples and overall MAE

---

## Dependencies Between Tasks

```
4.1 (uncertainty) ── independent, enriches existing surrogate_model.py
4.2 (multi-fidelity) ── independent, new file
4.3 (time-series) ── depends on having frame_series_index.csv data (Phase 3.2 helps)
```

All three can be developed in parallel by different developers.
