# Phase 1: Quality Hardening

## Objective
Improve code robustness without changing behavior. Fix known quality gaps.

## Prerequisites
- Phase 0 complete (config.py exists, tests pass)

---

## Task 1.1: Add K-Fold Cross-Validation to Surrogate Models

### Context
`surrogate_model.py` line ~115-145 in `train_surrogate_from_dataset()` currently uses a single `train_test_split(random_state=42, test_size=0.25)`. With small datasets (5-20 cases), this gives unstable metrics. Need K-fold CV as the primary evaluation.

### File to modify
`D:\githubproject\pyLabFEA\material_ai_workbench\surrogate_model.py`

### Specific changes

#### a) Update function signature
Add parameter `cv_folds: int = 5` to `train_surrogate_from_dataset()`:
```python
def train_surrogate_from_dataset(
    dataset_dir: Path | str | None = None,
    target: str = DEFAULT_TARGET,
    model_kind: str = "random_forest",
    holdout_size: float = 0.25,
    cv_folds: int = 5,          # NEW
    random_state: int = 42,
) -> SurrogateRun:
```

#### b) Add CV evaluation block
After the existing holdout evaluation, add:
```python
from sklearn.model_selection import cross_val_score, KFold

# Cross-validation on full dataset
if cv_folds > 1 and len(y_all) >= cv_folds:
    kfold = KFold(n_splits=min(cv_folds, len(y_all)), shuffle=True, random_state=random_state)
    cv_mae = -cross_val_score(pipeline, X_all, y_all, cv=kfold, scoring='neg_mean_absolute_error')
    cv_rmse = -cross_val_score(pipeline, X_all, y_all, cv=kfold, scoring='neg_root_mean_squared_error')
    cv_r2 = cross_val_score(pipeline, X_all, y_all, cv=kfold, scoring='r2')

    cv_metrics = {
        "cv_mae_mean": float(np.mean(cv_mae)),
        "cv_mae_std": float(np.std(cv_mae)),
        "cv_rmse_mean": float(np.mean(cv_rmse)),
        "cv_rmse_std": float(np.std(cv_rmse)),
        "cv_r2_mean": float(np.mean(cv_r2)),
        "cv_r2_std": float(np.std(cv_r2)),
        "cv_folds": cv_folds,
    }
else:
    cv_metrics = {"cv_note": "Too few samples for cross-validation"}

metrics.update(cv_metrics)
```

#### c) Update the surrogate report
In the markdown report generation (around line ~200), add a "Cross-Validation Results" section that displays the CV metrics with mean ± std when available.

#### d) Update `surrogate_comparison_rows()` (around line ~240)
Include `cv_mae_mean`, `cv_rmse_mean`, `cv_r2_mean` in the comparison table.

### No changes needed
- The Streamlit UI in `streamlit_app.py` `_surrogate_panel()` should add a `cv_folds` number input (default 5). Find the surrogate training section and add the input.

### Acceptance Criteria
- `python -m material_ai_workbench.surrogate_model` runs with default `cv_folds=5`
- `surrogate_metrics.json` contains `cv_mae_mean`, `cv_mae_std`, `cv_rmse_mean`, `cv_rmse_std`
- When dataset has < 3 samples, `cv_note` field appears instead
- Surrogate report markdown shows CV section with mean ± std formatting

---

## Task 1.2: Introduce Structured Logging

### Context
The project uses `print()` scattered across modules and basic `streamlit_app.log` file writing. Replace with Python's `logging` module for consistent, configurable log output.

### Files to create/modify

#### a) Create `logging_config.py` at project root
```python
"""Shared logging configuration for MaterialAI Workbench."""
import logging
import sys
from pathlib import Path

LOG_DIR = Path(__file__).resolve().parent / "logs"
LOG_DIR.mkdir(exist_ok=True)

_LOGGER_CACHE: dict[str, logging.Logger] = {}

def get_logger(name: str) -> logging.Logger:
    """Return a configured logger for the given module name.

    Logs to both console (INFO+) and a rotating file (DEBUG+).
    """
    if name in _LOGGER_CACHE:
        return _LOGGER_CACHE[name]

    logger = logging.getLogger(name)
    logger.setLevel(logging.DEBUG)
    logger.propagate = False

    # File handler: DEBUG and above
    fh = logging.FileHandler(LOG_DIR / "material_ai_workbench.log", encoding="utf-8")
    fh.setLevel(logging.DEBUG)
    fh.setFormatter(logging.Formatter(
        "%(asctime)s | %(levelname)-7s | %(name)s | %(message)s",
        datefmt="%Y-%m-%d %H:%M:%S",
    ))
    logger.addHandler(fh)

    # Console handler: INFO and above
    ch = logging.StreamHandler(sys.stdout)
    ch.setLevel(logging.INFO)
    ch.setFormatter(logging.Formatter(
        "%(levelname)-7s | %(name)s | %(message)s"
    ))
    logger.addHandler(ch)

    _LOGGER_CACHE[name] = logger
    return logger
```

#### b) Replace `print()` calls in these files
For each file below, add `logger = get_logger(__name__)` at module level and replace `print(...)` with `logger.info(...)` / `logger.debug(...)` / `logger.warning(...)`:

| File | Approximate print count | Guideline |
|------|------------------------|-----------|
| `pipeline.py` | 0 (already clean) | Add entry/exit logging to `run_material_workbench()` |
| `abaqus_bridge.py` | ~5 | Subprocess start/end → info; internal details → debug |
| `abaqus_mcp_client.py` | ~8 | Connection events → info; payload details → debug; errors → error |
| `abaqus_batch_client.py` | ~3 | Script generation → debug; subprocess start/end → info |
| `case_library.py` | ~2 | Scan start/complete → info |
| `surrogate_model.py` | ~2 | Training start/end → info |
| `streamlit_app.py` | ~10 | Replace `st.write()` debug lines with proper logger calls |

#### c) Add logging to `streamlit_app.py`
In `main()` (around line 1980), add at the top:
```python
from material_ai_workbench.logging_config import get_logger
logger = get_logger("streamlit")
logger.info("Streamlit app started")
```

### Important constraint
Do NOT change `streamlit_app.py` `st.write()` calls that are part of the user-facing UI. Only replace `print()` calls used for debugging.

### Acceptance Criteria
- `logs/material_ai_workbench.log` is created on first run
- All key pipeline stages (train, abaqus run, dataset export, surrogate train) produce log entries
- Console output is cleaner: no bare `print()` from library code
- Streamlit logs appear in the file

---

## Task 1.3: Add Validation to Data Import

### Context
`data_import.py` `import_csv_dataset()` auto-detects columns and normalizes data, but does no sanity checking on the imported curves. A stress-strain curve with negative stiffness or physically impossible values should be flagged.

### File to modify
`D:\githubproject\pyLabFEA\material_ai_workbench\data_import.py`

### Specific changes

#### a) Add validation function
```python
def _validate_stress_strain_curve(
    strain: list[float],
    stress: list[float],
) -> list[str]:
    """Return list of validation warnings for a stress-strain curve."""
    import numpy as np
    warnings = []
    s_strain = np.array(strain)
    s_stress = np.array(stress)

    # Check monotonic strain
    if np.any(np.diff(s_strain) <= 0):
        warnings.append("Strain is not strictly monotonic increasing")

    # Check positive stress for tensile data
    if np.all(s_strain >= 0) and np.any(s_stress < -1e-6):
        warnings.append("Negative stress values found in tensile region")

    # Check initial stiffness is positive
    if len(s_strain) >= 3:
        # Linear fit to first 10% of data
        n_fit = max(3, int(len(s_strain) * 0.1))
        x, y = s_strain[:n_fit], s_stress[:n_fit]
        if np.std(x) > 1e-12:
            slope = np.polyfit(x, y, 1)[0]
            if slope <= 0:
                warnings.append(f"Initial modulus appears negative or zero ({slope:.1f})")
            elif slope > 500_000:
                warnings.append(f"Initial modulus unusually high ({slope:.0f} MPa)")

    # Check for NaN/Inf
    if np.any(np.isnan(s_strain)) or np.any(np.isnan(s_stress)):
        warnings.append("NaN values detected in data")
    if np.any(np.isinf(s_strain)) or np.any(np.isinf(s_stress)):
        warnings.append("Inf values detected in data")

    # Check strain range reasonable
    max_strain = np.max(np.abs(s_strain))
    if max_strain > 10:
        warnings.append(f"Maximum strain {max_strain:.2f} seems large (units may be percent?)")

    return warnings
```

#### b) Call validation in `import_csv_dataset()`
After the data is loaded and before generating the report, call the validator and add warnings to `DataImportResult.warnings`. Include validation results in the import report markdown.

#### c) Update `DataImportResult` dataclass
Already has `warnings: list[str]` field. Ensure validation warnings are appended to it.

### Acceptance Criteria
- Import a CSV with negative initial stiffness → `warnings` contains the issue
- Import a CSV with strain decreasing → `warnings` contains "not strictly monotonic"
- Import a normal CSV → `warnings` is empty
- Import report markdown shows warnings section when non-empty

---

## Task 1.4: Fix Streamlit Error Log Capture

### Context
`streamlit_app.err.log` exists at project root but is empty (0 bytes). Streamlit's stderr is not being captured. This makes debugging UI errors nearly impossible.

### Investigation needed
Check how Streamlit is launched. The README says:
```powershell
conda run -n pylabfea streamlit run material_ai_workbench/streamlit_app.py --server.port 8501
```
No stderr redirect. The log files at project root exist but are empty.

### Solution
Wrap the Streamlit launch in a PowerShell script that captures both stdout and stderr:

#### Create `run_streamlit.ps1` at project root:
```powershell
$projectRoot = Split-Path -Parent $MyInvocation.MyCommand.Path
$logDir = Join-Path $projectRoot "logs"
New-Item -ItemType Directory -Force -Path $logDir | Out-Null

$timestamp = Get-Date -Format "yyyyMMdd_HHmmss"
$logFile = Join-Path $logDir "streamlit_${timestamp}.log"

Write-Host "Starting Streamlit... logs -> $logFile"

streamlit run "$projectRoot\streamlit_app.py" --server.port 8501 *>&1 | Tee-Object -FilePath $logFile
```

#### HOWEVER, a simpler approach:
Modify `streamlit_app.py` itself to redirect stderr at the Python level. Add at the very top of `streamlit_app.py` (before any imports):
```python
import sys
from pathlib import Path
from datetime import datetime

_log_dir = Path(__file__).resolve().parent / "logs"
_log_dir.mkdir(exist_ok=True)
_log_path = _log_dir / f"streamlit_{datetime.now().strftime('%Y%m%d_%H%M%S')}.log"

class _TeeStream:
    def __init__(self, stream, filepath):
        self.stream = stream
        self.file = open(filepath, "w", encoding="utf-8", buffering=1)

    def write(self, data):
        self.stream.write(data)
        self.file.write(data)

    def flush(self):
        self.stream.flush()
        self.file.flush()

sys.stderr = _TeeStream(sys.__stderr__, _log_path)
sys.stdout = _TeeStream(sys.__stdout__, _log_path)
```

### Acceptance Criteria
- Start Streamlit, interact with the UI, observe errors (or trigger an intentional error)
- A timestamped log file appears in `logs/` containing both stdout and stderr
- The old empty `streamlit_app.log` and `streamlit_app.err.log` at root can be deleted

---

## Task 1.5: Add Timeout and Retry to Abaqus Subprocess Calls

### Context
`abaqus_bridge.py` `run_abaqus_verification()` calls Abaqus via subprocess with a timeout, but there's no retry logic. Abaqus license checkout can transiently fail. A single retry with backoff is appropriate.

### File to modify
`D:\githubproject\pyLabFEA\material_ai_workbench\abaqus_bridge.py`

### Changes
In `run_abaqus_verification()`, wrap the subprocess.run call:
```python
import time

max_attempts = 2
for attempt in range(1, max_attempts + 1):
    try:
        proc = subprocess.run(cmd, ...)
        break
    except subprocess.TimeoutExpired:
        if attempt == max_attempts:
            raise
        logger.warning("Abaqus timed out (attempt %d/%d), retrying...", attempt, max_attempts)
        time.sleep(10 * attempt)  # progressive backoff
```

### Acceptance Criteria
- First attempt timeout → second attempt runs after 10s delay
- Second attempt timeout → exception raised
- Successful first attempt → no retry

---

## Dependencies Between Tasks

```
1.1 (CV) ── independent
1.2 (logging) ── independent, but 1.4 should import from logging_config
1.3 (validation) ── independent
1.4 (stderr capture) ── imports from 1.2's logging_config
1.5 (retry) ── independent
```

Recommended execution order: 1.2 → 1.4 → 1.1, 1.3, 1.5 in parallel.
