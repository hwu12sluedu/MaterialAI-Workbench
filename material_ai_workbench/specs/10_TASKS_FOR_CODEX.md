# 10 Tasks for MaterialAI Workbench

Feed individual tasks to Codex. Each is self-contained with file paths, code snippets, and acceptance criteria.

---

## TASK 1: Fix Composite Abaqus Orientation + Run Full Closed Loop

**Priority:** HIGH — blocks all composite surrogate work  
**Dependencies:** None  
**Effort:** 1-2 hours (mostly Abaqus run time)

### Problem
`composite_workflow.py` generates orthotropic ENGINEERING CONSTANTS but the Abaqus CAE script didn't assign material orientation — solver fails with "Anisotropic material properties without a local orientation system."

### Fix (already applied)
Line 976 of `composite_workflow.py` now has:
```python
part.MaterialOrientation(region=part.cells, orientationType=SYSTEM, axis=AXIS_1, localCsys=None)
```

### What to do
1. Run the provided `_run_comp_abaqus.py` script (already at project root) to execute the full composite closed loop:
   ```
   $env:PYTHONPATH = "D:/githubproject/pyLabFEA"
   $env:PATH = "D:\Anaconda3\condabin;" + $env:PATH
   conda run -n pylabfea python material_ai_workbench/_run_comp_abaqus.py
   ```
2. Verify the Abaqus solve completes (check `comp_full_demo_plate_hole.log` for "COMPLETED")
3. Verify ODB post-process extracts Max Mises, Max U, Sum RF1
4. Verify case library archive + ODB extraction stages pass
5. Clean up `_run_comp_abaqus.py` after success

### Acceptance
- Abaqus plate-with-hole solve completes without errors
- ODB contains S, U, RF field outputs
- Plate post-process JSON has max_mises close to the estimate (~800-900 MPa for Vf=0.55, R=5mm, 0.3% strain)

---

## TASK 2: Data Import Validation (Experimental Curve QC)

**Priority:** HIGH — prevents garbage data entering the training pipeline  
**Dependencies:** None  
**Effort:** 1 hour

### What to do
Edit `D:\githubproject\pyLabFEA\material_ai_workbench\data_import.py`.

Add a validation function called after CSV loading:

```python
def _validate_stress_strain_curve(strain: list[float], stress: list[float]) -> list[str]:
    """Return list of validation warnings."""
    import numpy as np
    warnings = []
    s_strain = np.array(strain, dtype=float)
    s_stress = np.array(stress, dtype=float)

    if np.any(np.diff(s_strain) <= 0):
        warnings.append("Strain is not strictly monotonic increasing")
    if np.any(np.isnan(s_strain)) or np.any(np.isnan(s_stress)):
        warnings.append("NaN values detected")
    if np.any(np.isinf(s_strain)) or np.any(np.isinf(s_stress)):
        warnings.append("Inf values detected")

    # Check initial stiffness
    if len(s_strain) >= 5:
        n_fit = max(3, int(len(s_strain) * 0.1))
        x, y = s_strain[:n_fit], s_stress[:n_fit]
        if np.std(x) > 1e-12:
            slope = np.polyfit(x, y, 1)[0]
            if slope <= 0:
                warnings.append(f"Initial modulus appears negative or zero ({slope:.1f})")
            elif slope > 500_000:
                warnings.append(f"Initial modulus unusually high ({slope:.0f} MPa)")

    max_strain = np.max(np.abs(s_strain))
    if max_strain > 10:
        warnings.append(f"Strain range {max_strain:.2f} — units may be percent, not absolute")

    return warnings
```

Call it inside `import_csv_dataset()` after data loading. Append results to `DataImportResult.warnings`. Add a "Validation" section to the import report markdown.

### Acceptance
- Import CSV with decreasing strain → warnings appear in report
- Import CSV with strain=5.0 (percent-scale) → "units may be percent" warning
- Import normal stress-strain CSV → no warnings

---

## TASK 3: Experimental Curve → Train Material Model

**Priority:** MEDIUM — enables experimental data-driven workflow  
**Dependencies:** Task 2 (validation) recommended  
**Effort:** 2 hours

### What to do
Add a function to `data_import.py` that converts imported experimental data into a `WorkbenchConfig`:

```python
def imported_curve_to_config(import_dir: Path) -> WorkbenchConfig | None:
    """Build a WorkbenchConfig from an imported experimental curve.
    Estimates E from initial slope (first 0.05% strain).
    Estimates sy via 0.2% offset method.
    """
    import json, csv
    import numpy as np
    from material_ai_workbench.pipeline import WorkbenchConfig

    summary_path = Path(import_dir) / "summary.json"
    if not summary_path.exists():
        return None
    summary = json.loads(summary_path.read_text(encoding="utf-8"))
    curve_csv = Path(import_dir) / "normalized_curve.csv"
    if not curve_csv.exists():
        return None

    strains, stresses = [], []
    with open(curve_csv, newline="", encoding="utf-8") as f:
        for row in csv.DictReader(f):
            strains.append(float(row["strain"]))
            stresses.append(float(row["stress_mpa"]))
    strains = np.array(strains)
    stresses = np.array(stresses)

    # Estimate E from first 0.05% strain
    elastic = strains <= 0.0005
    if elastic.sum() >= 3:
        E = float(np.polyfit(strains[elastic], stresses[elastic], 1)[0])
    else:
        E = 200_000.0

    # 0.2% offset yield
    offset_line = E * (strains - 0.002)
    plastic = stresses < offset_line
    sy = float(stresses[plastic][-1]) if plastic.any() else 60.0

    return WorkbenchConfig(
        material_type="j2", name=f"exp_{Path(import_dir).name}",
        youngs_modulus=E, poisson_ratio=0.3, yield_strength=sy,
        calculate_curves=True,
    )
```

In `streamlit_app.py` `_data_import_panel()`, add a button "从该曲线训练材料" that:
1. Calls `imported_curve_to_config()` 
2. Shows estimated E and sy to user
3. On confirm, calls `run_material_workbench()`

### Acceptance
- Import a valid experimental CSV → E and sy estimates shown
- Click "从该曲线训练材料" → pipeline runs → yield locus and curves generated
- Estimated E within 10% of true value for clean linear-elastic data

---

## TASK 4: Barlat Yld2000-2D Yield Criterion Support

**Priority:** MEDIUM — industry standard for aluminum forming  
**Dependencies:** None  
**Effort:** 2-3 hours

### What to do
Extend the pipeline to support Barlat Yld2000-2D (8-parameter anisotropic yield for aluminum).

**Files to modify:**

**`pipeline.py`** — `WorkbenchConfig`: add fields:
```python
barlat_exponent: float = 8.0       # 8=FCC (Al), 6=BCC (steel)
barlat_alphas: tuple[float, ...] = (1.0, 1.0, 1.0, 1.0, 1.0, 1.0, 1.0, 1.0)
```

**`pipeline.py`** — `_create_reference_material()`: add barlat branch:
```python
elif material_type == "barlat":
    ref_mat.plasticity(sy=config.yield_strength, sdim=6,
                       barlat_exp=config.barlat_exponent,
                       barlat_alphas=list(config.barlat_alphas))
```

If pyLabFEA doesn't have `barlat_exp`/`barlat_alphas` parameters in `plasticity()`, first check the pyLabFEA source at `D:\githubproject\pyLabFEA\src\pylabfea\material.py` to find the correct API, then adapt.

**`run_workbench.py`**: add `--barlat-exponent` and `--barlat-alphas` CLI args.

**`streamlit_app.py`**: add "barlat" to material type selector. When selected, show 8 alpha inputs in a grid. Add a "barlat" preset to the material library.

### Acceptance
- `--material barlat --barlat-exponent 8 --barlat-alphas 0.9 1.0 0.8 1.0 1.0 1.0 0.9 1.1` produces valid UMAT export
- Yield locus plot shows anisotropic (non-circular) shape
- Barlat test added to `tests/test_pipeline.py`

---

## TASK 5: Streamlit UI Overhaul (Navigation + Buttons + Layout)

**Priority:** MEDIUM — user experience  
**Dependencies:** None  
**Effort:** 3-4 hours

### What to do
Major UI polish pass on `streamlit_app.py`:

**5a. Move 11 tabs to sidebar navigation (line 142)**
```python
with st.sidebar:
    page = st.radio("导航", ["AI 任务", "材料训练", ...], label_visibility="collapsed")
# Main area: if page == "AI 任务": _ai_task_panel() ...
```

**5b. Add explicit `key=` to every st.button()** (~26 locations)
Pattern: `st.button("解析任务", key="ai_parse_rule")`

**5c. Add `height=400` to every st.dataframe()** (~13 locations)

**5d. Fix nested expander at line 1249** (composite_dataset.csv inside 复合材料批量数据)

**5e. Add `st.divider()` between logical sections in training panel (lines 281-332)**

**5f. Fix English labels to Chinese** (lines 834-835: "Bridge host" → "主机地址")

**5g. Add `st.spinner()` around all long-running operations**

### Acceptance
- Sidebar shows 11 navigation items, main area shows only the selected page
- No `DuplicateElementId` errors when switching between panels
- Tables don't stretch page beyond viewport
- Chinese labels consistent throughout

---

## TASK 6: Abaqus Job Queue (Non-Blocking UI)

**Priority:** MEDIUM — prevents UI freezing during Abaqus runs  
**Dependencies:** None  
**Effort:** 3-4 hours

### What to do
Create `D:\githubproject\pyLabFEA\material_ai_workbench\job_queue.py`:

```python
@dataclass
class QueuedJob:
    job_id: str
    name: str
    input_file: str
    work_dir: str
    status: str = "queued"  # queued | running | completed | failed
    cpus: int = 4
    submitted_at: str = field(default_factory=lambda: datetime.now().isoformat())

class JobQueue:
    def __init__(self): ...
    def submit(self, name, input_file, work_dir, cpus=4) -> QueuedJob: ...
    def process_next(self) -> bool: ...  # run next queued job
    def get_status(self) -> dict: ...    # {queued: N, running: N, completed: N, failed: N}
    def list_jobs(self) -> list[QueuedJob]: ...
    def _save(self): ...   # persist to job_queue.json
    def _load(self): ...   # load from job_queue.json
```

In `streamlit_app.py`, add a "Job Queue" section inside the "Abaqus Verification" tab or as its own expander:
- Submit form (job name, input file, work dir, CPUs)
- "Process Next Job" button
- Job status table
- Survives Streamlit restarts (JSON persistence)

### Acceptance
- Submit 3 Abaqus jobs → all show "queued"
- Click "Process Next" → first job runs, status changes to "completed"/"failed"
- Refresh browser → queue state persists

---

## TASK 7: Similar Case Search in Case Library

**Priority:** LOW — QoL feature  
**Dependencies:** None  
**Effort:** 2 hours

### What to do
Add a similarity search function to `case_library.py` and expose it in Streamlit.

```python
def find_similar_cases(query_case_id: str, top_k: int = 5) -> list[dict]:
    """Return top-k similar cases by normalized feature distance."""
    # Build feature vectors from: inp_node_count, inp_element_count, file_count,
    # csv_row_count, max_mises, max_peeq, yield_strength, youngs_modulus, etc.
    # Compute cosine similarity, return top-k (excluding self)
```

In `streamlit_app.py` case detail view, add a "Similar Cases" section showing top-5 matches with similarity scores.

### Acceptance
- Two J2 cases with similar element counts → similarity > 0.9
- J2 case vs composite case → similarity < 0.5
- Similar cases appear in UI below case detail

---

## TASK 8: Multi-Fidelity Surrogate Model

**Priority:** LOW — improves small-sample prediction accuracy  
**Dependencies:** Task 1 (composite Abaqus data) recommended  
**Effort:** 3-4 hours

### What to do
The project already has `multi_fidelity.py` with `train_multi_fidelity()` implemented. Integrate it into the UI.

In `streamlit_app.py` `_surrogate_panel()`:
1. Add a "Multi-Fidelity" expander
2. Let user select:
   - Low-fidelity dataset (pyLabFEA batch runs → cheap, many samples)
   - High-fidelity dataset (Abaqus-verified cases → expensive, few samples)
   - Common feature mapping
3. Call `train_multi_fidelity(X_low, y_low, X_high, y_high)`
4. Show comparison: single-fidelity MAE vs multi-fidelity MAE
5. Show the multi-fidelity prediction plot

### Acceptance
- With 3 high-fidelity + 20 low-fidelity samples, multi-fidelity MAE < single-fidelity MAE
- Comparison plot shows both models on same axes

---

## TASK 9: Clean Up Dead Code + Fix CWD-Dependent Paths

**Priority:** LOW — code hygiene  
**Dependencies:** None  
**Effort:** 1-2 hours

### What to do

**9a.** These files are in `__init__.py`'s `__all__` but never imported by any consumer:
- `task_queue.py` — remove from `__init__.py`
- `time_series_surrogate.py` — remove from `__init__.py`
- `param_recommender.py` — remove from `__init__.py`
- `multi_fidelity.py` — keep imported (used in Task 8)

**9b.** Fix CWD-dependent default paths. These use `Path("material_ai_workbench/...")` which resolves relative to CWD, not the package root:
- `pipeline.py:34` — `output_dir: Path = Path("material_ai_workbench/runs")`
- `run_workbench.py:58` — same pattern
- `run_composite_workflow.py:51` — same
- `run_composite_batch.py:58` — same

Change each to import and use the config values:
```python
from material_ai_workbench.config import RUNS_ROOT
# Change default to: output_dir: Path | None = None
# Then resolve inside the function: output_dir = output_dir or RUNS_ROOT
```

**9c.** Fix `_case_odb_options` in `streamlit_app.py` (line 796-813) to properly handle the `result_features.summary.odb_files` list (which stores relative paths as flat strings) vs `result_features.odb_files` (which stores absolute paths as dicts). The function currently reads from the correct source (`result_features.odb_files`) but should add a fallback to also scan `result_features.summary.odb_files`.

### Acceptance
- `grep -rn "Path(\"material_ai_workbench"` returns zero matches outside config.py
- `from material_ai_workbench import *` doesn't import unused TaskQueue/BackgroundTask symbols
- Tests still pass (8 passed, 4 skipped)

---

## TASK 10: Docker + CI/CD Pipeline

**Priority:** LOW — deployment ready  
**Dependencies:** Task 9 (clean paths) recommended  
**Effort:** 2-3 hours

### What to do

**10a. Create `D:\githubproject\pyLabFEA\Dockerfile`:**
```dockerfile
FROM python:3.12-slim
RUN apt-get update && apt-get install -y --no-install-recommends libgl1-mesa-glx libglib2.0-0 && rm -rf /var/lib/apt/lists/*
WORKDIR /app
COPY pyproject.toml .
COPY material_ai_workbench/ material_ai_workbench/
RUN pip install --no-cache-dir -e ".[web]"
EXPOSE 8501
CMD ["streamlit", "run", "material_ai_workbench/streamlit_app.py", "--server.port=8501", "--server.address=0.0.0.0", "--server.headless=true"]
```

**10b. Create `D:\githubproject\pyLabFEA\docker-compose.yml`** with volume mounts for runs/library/cases.

**10c. Create `D:\githubproject\pyLabFEA\.github\workflows\ci.yml`:**
```yaml
name: CI
on: [push, pull_request]
jobs:
  test:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4
      - uses: actions/setup-python@v5
        with: {python-version: "3.12"}
      - run: pip install -e ".[dev]"
      - run: pytest material_ai_workbench/tests/ -v
```

**10d. Verify `pyproject.toml`** exists at the repo root with proper `[project.scripts]` entry points.

### Acceptance
- `docker build -t material-ai-workbench .` succeeds
- `docker run -p 8501:8501 material-ai-workbench` → `curl http://localhost:8501` returns HTTP 200
- GitHub Actions CI runs pytest on push

---

## Execution Order

```
Task 1 (composite Abaqus) ──> Task 8 (multi-fidelity, needs composite data)
Task 2 (data validation)  ──> Task 3 (exp curve training)
Task 4 (Barlat)           ── independent
Task 5 (UI overhaul)      ── independent, touch ALL panels
Task 6 (job queue)        ── independent
Task 7 (case search)      ── independent
Task 9 (dead code)        ── independent, do before Task 10
Task 10 (Docker/CI)       ── depends on Task 9
```

Tasks 1-5 should be done first (high impact). Tasks 6-10 are lower priority.

---

## Current State Reference

| Pipeline | Train | Abaqus Verify | Case Lib | ODB | Dataset | Surrogate | Uncertainty |
|----------|-------|---------------|----------|-----|---------|-----------|-------------|
| Metal J2/Hill | DONE | DONE | DONE | DONE | DONE | RF R2=0.17 | PI=±26MPa |
| Composite RVE | DONE | FIXED (Task 1) | TODO | TODO | 3 samples | RF R2=0.80 | PI=±127MPa |

Tests: 8 passed, 4 skipped (pipeline tests need `MATERIALAI_RUN_PIPELINE_TESTS=1`)
Git: initialized at D:\githubproject\pyLabFEA with .gitignore
