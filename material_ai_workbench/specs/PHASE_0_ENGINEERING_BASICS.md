# Phase 0: Engineering Basics

## Objective
Make the project reproducible by other developers. No new features. Foundation-only.

## Prerequisites
- None. This is the starting point.

---

## Task 0.1: Initialize Git Repository

### Context
Project is at `D:\githubproject\pyLabFEA\material_ai_workbench\`. No `.git` exists. Only source code should be tracked; generated output directories must be excluded.

### Actions
1. Create `.gitignore` at project root with the content below.
2. Run `git init` in the project root.
3. Run `git add -A` and verify only intended files are staged. If generated files leak through, fix `.gitignore` before committing.

### `.gitignore` content (exact):
```gitignore
# Python
__pycache__/
*.pyc
*.pyo
*.egg-info/
dist/
build/

# Generated output directories (timestamped runs)
runs/
batches/
cases/
composite_runs/
composite_batches/
datasets/
surrogates/
composite_surrogates/
closed_loop_reports/
imports/
mcp_sessions/
logs/

# Abaqus binary outputs
*.odb
*.odb_f
*.cae
*.jnl
*.rpy
*.prt
*.com
*.dat
*.log
*.sta
*.msg

# Environment
.env
.env.local

# IDE
.vscode/
.idea/
*.swp
*.swo

# OS
Thumbs.db
Desktop.ini
```

### Acceptance Criteria
- `git status` shows only source files (`.py`, `.md`, `.json`, `.f`, `.inp`, `.ps1`) tracked
- No `runs/`, `batches/`, `cases/` directories in staging area
- `.gitignore` is committed as the first commit

---

## Task 0.2: Create Dependency Files

### Context
The README references a conda environment `pylabfea` but no environment file exists. The project imports `pyLabFEA`, `numpy`, `scipy`, `matplotlib`, `scikit-learn`, `streamlit`. Python 3.12.

### Actions
1. Create `environment.yml` at project root.
2. Create `requirements.txt` at project root (for pip-only users).
3. Verify by creating a fresh conda env from `environment.yml` and confirming `python -c "import pylabfea; import sklearn; import streamlit; print('OK')"` works.

### `environment.yml` content:
```yaml
name: pylabfea
channels:
  - conda-forge
  - defaults
dependencies:
  - python=3.12
  - numpy>=1.26
  - scipy>=1.12
  - matplotlib>=3.8
  - scikit-learn>=1.4
  - pandas>=2.2
  - pip
  - pip:
    - streamlit>=1.32
    - pylabfea
```

### `requirements.txt` content:
```
numpy>=1.26
scipy>=1.12
matplotlib>=3.8
scikit-learn>=1.4
pandas>=2.2
streamlit>=1.32
pylabfea
```

### Acceptance Criteria
- `conda env create -f environment.yml` succeeds on a machine without the `pylabfea` env
- `python -c "import pylabfea, sklearn, streamlit; print('OK')"` prints `OK`

---

## Task 0.3: Eliminate Hardcoded Paths

### Context
Multiple files contain hardcoded `D:\ABAQUS\2023\...` paths. These must be configurable via a single config file so the project can run on machines with different Abaqus installations.

### Files to modify

#### 0.3a: Create `config.py` at project root

```python
"""Central configuration for MaterialAI Workbench.

All paths and defaults that vary across machines live here.
Override via environment variables or a .env file at the project root.
"""

from __future__ import annotations

import os
from pathlib import Path


def _env(key: str, default: str) -> str:
    return os.environ.get(key, default)


# ---- Abaqus installation ----
ABAQUS_BAT = Path(_env("MATERIALAI_ABAQUS_BAT", r"D:\ABAQUS\2023\Commands\abaqus.bat"))
ABAQUS_SMAPYTHON = Path(
    _env(
        "MATERIALAI_ABAQUS_SMAPYTHON",
        r"D:\ABAQUS\2023\EstProducts\win_b64\code\bin\SMAPython.exe",
    )
)

# ---- Abaqus MCP connection ----
MCP_HOST = _env("MATERIALAI_MCP_HOST", "127.0.0.1")
MCP_PORT = int(_env("MATERIALAI_MCP_PORT", "48152"))
MCP_TIMEOUT = int(_env("MATERIALAI_MCP_TIMEOUT", "10"))

# ---- LLM API (optional) ----
LLM_BASE_URL = _env("MATERIALAI_LLM_BASE_URL", "")
LLM_MODEL = _env("MATERIALAI_LLM_MODEL", "")
LLM_API_KEY = _env("MATERIALAI_LLM_API_KEY", "")

# ---- Output ----
RUNS_ROOT = Path(_env("MATERIALAI_RUNS_ROOT", str(Path(__file__).resolve().parent / "runs")))
BATCHES_ROOT = Path(_env("MATERIALAI_BATCHES_ROOT", str(Path(__file__).resolve().parent / "batches")))
CASES_ROOT = Path(_env("MATERIALAI_CASES_ROOT", str(Path(__file__).resolve().parent / "cases")))
DATASETS_ROOT = Path(_env("MATERIALAI_DATASETS_ROOT", str(Path(__file__).resolve().parent / "datasets")))
SURROGATES_ROOT = Path(_env("MATERIALAI_SURROGATES_ROOT", str(Path(__file__).resolve().parent / "surrogates")))
IMPORTS_ROOT = Path(_env("MATERIALAI_IMPORTS_ROOT", str(Path(__file__).resolve().parent / "imports")))
COMPOSITE_ROOT = Path(_env("MATERIALAI_COMPOSITE_ROOT", str(Path(__file__).resolve().parent / "composite_runs")))
COMPOSITE_BATCH_ROOT = Path(_env("MATERIALAI_COMPOSITE_BATCH_ROOT", str(Path(__file__).resolve().parent / "composite_batches")))
COMPOSITE_SURROGATE_ROOT = Path(_env("MATERIALAI_COMPOSITE_SURROGATE_ROOT", str(Path(__file__).resolve().parent / "composite_surrogates")))
CLOSED_LOOP_ROOT = Path(_env("MATERIALAI_CLOSED_LOOP_ROOT", str(Path(__file__).resolve().parent / "closed_loop_reports")))
LIBRARY_DIR = Path(_env("MATERIALAI_LIBRARY_DIR", str(Path(__file__).resolve().parent / "library")))
```

#### 0.3b: Update every module that hardcodes paths

Replace local constants with imports from `config.py` in these files:

**`abaqus_bridge.py`** (line ~18-19):
- Replace `DEFAULT_ABAQUS_BAT = Path(r"D:\ABAQUS\2023\Commands\abaqus.bat")` with `from material_ai_workbench.config import ABAQUS_BAT`
- Replace `UMAT_TEMPLATE_DIR` reference to also use config if appropriate

**`abaqus_batch_client.py`** (line ~14):
- Replace `DEFAULT_SMAPYTHON = r"D:\ABAQUS\2023\EstProducts\win_b64\code\bin\SMAPython.exe"` with `from material_ai_workbench.config import ABAQUS_SMAPYTHON`

**`abaqus_mcp_client.py`** (lines ~14-16):
- Replace `DEFAULT_HOST = "127.0.0.1"`, `DEFAULT_PORT = 48152`, `DEFAULT_TIMEOUT = 10` with imports from `config.py`

**`pipeline.py`** (line 34):
- Replace `output_dir: Path = Path("material_ai_workbench/runs")` default. Instead, default to `None` and resolve to `config.RUNS_ROOT` inside `_prepare_run_dir`.

**`surrogate_model.py`** (line 30):
- Replace `SURROGATES_ROOT = Path(__file__).resolve().parent / "surrogates"` with import from config

**`dataset_export.py`**:
- Replace `DATASETS_ROOT` with import from config

**`data_import.py`**:
- Replace `IMPORTS_ROOT` with import from config

**`case_library.py`**:
- Replace `CASES_ROOT` with import from config

**`batch_simulation.py`**:
- Replace `BATCH_ROOT` with import from config

**`closed_loop_report.py`**:
- Replace `CLOSED_LOOP_ROOT` with import from config

**`material_library.py`**:
- Replace `LIBRARY_DIR` with import from config

**`composite_workflow.py`**:
- Replace `COMPOSITE_ROOT` with import from config

**`composite_dataset.py`**:
- Replace `COMPOSITE_BATCH_ROOT`, `COMPOSITE_SURROGATE_ROOT` with imports from config

**`llm_adapter.py`** (line ~15-18):
- Replace hardcoded env var names with constants from `config.py`

### Important constraint
All existing function signatures that accept path parameters (like `run_material_workbench(config)` where `config.output_dir` is a Path) must continue to work. The config.py values are only *defaults* — explicit user-provided paths take precedence.

### Acceptance Criteria
- `grep -rn "D:\\\\ABAQUS" material_ai_workbench/*.py` returns zero matches
- Setting `MATERIALAI_ABAQUS_BAT=C:\OtherAbaqus\abaqus.bat` as env var causes the bridge to use that path
- All existing CLI commands from README still work without setting env vars (defaults preserved)

---

## Task 0.4: Write Minimal Test Suite

### Context
No tests exist. Need tests that run without Abaqus (pure Python, no binary dependencies beyond pyLabFEA).

### Create `tests/` directory with these files:

#### `tests/__init__.py` — empty file

#### `tests/test_pipeline.py`:
```python
"""Tests for core training pipeline. No Abaqus dependency."""
from pathlib import Path
import tempfile
import json
from material_ai_workbench.pipeline import WorkbenchConfig, run_material_workbench


def test_j2_training_creates_all_outputs():
    """J2 training produces summary, figures, models, data, reports."""
    with tempfile.TemporaryDirectory() as td:
        config = WorkbenchConfig(
            material_type="j2",
            name="test_j2",
            output_dir=Path(td),
            n_load_cases=10,      # small for speed
            n_sequence=2,         # small for speed
            calculate_curves=True,
            test_size=20,
            random_seed=1,
        )
        result = run_material_workbench(config)

        assert result.run_dir.exists()
        assert result.report_path.exists()
        assert result.summary_path.exists()
        assert result.yield_locus_png.exists()
        assert result.stress_strain_png.exists()
        assert result.umat_csv.exists()
        assert result.umat_meta_json.exists()
        assert result.support_vectors > 0
        assert len(result.metrics) == 6

        summary = json.loads(result.summary_path.read_text())
        assert summary["metrics"]["mae"] >= 0
        assert summary["metrics"]["f1"] >= 0


def test_hill_training_creates_all_outputs():
    """Hill anisotropic training produces valid outputs."""
    with tempfile.TemporaryDirectory() as td:
        config = WorkbenchConfig(
            material_type="hill",
            name="test_hill",
            output_dir=Path(td),
            yield_strength=50.0,
            n_load_cases=10,
            n_sequence=2,
            calculate_curves=False,
            test_size=20,
            random_seed=2,
        )
        result = run_material_workbench(config)

        assert result.report_path.exists()
        assert result.umat_csv.exists()
        assert result.support_vectors > 0


def test_metrics_are_reasonable():
    """For a simple J2 material, accuracy should be > 0.8."""
    with tempfile.TemporaryDirectory() as td:
        config = WorkbenchConfig(
            material_type="j2",
            name="test_metrics",
            output_dir=Path(td),
            n_load_cases=20,
            n_sequence=3,
            random_seed=3,
        )
        result = run_material_workbench(config)
        assert result.metrics["accuracy"] > 0.8, f"Accuracy {result.metrics['accuracy']} too low"


def test_invalid_material_type_raises():
    """Unknown material type should raise ValueError."""
    with tempfile.TemporaryDirectory() as td:
        config = WorkbenchConfig(
            material_type="unsupported_xyz",
            name="test_fail",
            output_dir=Path(td),
        )
        try:
            run_material_workbench(config)
            assert False, "Should have raised ValueError"
        except ValueError:
            pass
```

#### `tests/test_material_library.py`:
```python
"""Tests for material preset library."""
import tempfile
from pathlib import Path
from material_ai_workbench.material_library import (
    MaterialPreset,
    load_material_presets,
    save_material_preset,
    delete_material_preset,
)


def test_save_and_load_preset():
    """Round-trip: save a preset, then load it back."""
    with tempfile.TemporaryDirectory() as td:
        lib_dir = Path(td)
        materials_file = lib_dir / "materials.json"
        # Override the global path for this test
        preset = MaterialPreset(
            name="TestPreset",
            material_type="j2",
            youngs_modulus=210000,
            poisson_ratio=0.3,
            yield_strength=100,
            hill_ratios=[1.0, 1.0, 1.0, 1.0, 1.0, 1.0],
            c_value=2.0,
            gamma=0.5,
        )
        from material_ai_workbench import material_library
        orig = material_library.MATERIALS_FILE
        try:
            material_library.MATERIALS_FILE = materials_file
            save_material_preset(preset)
            loaded = load_material_presets()
            assert "TestPreset" in loaded
            assert loaded["TestPreset"].yield_strength == 100
            assert loaded["TestPreset"].c_value == 2.0
        finally:
            material_library.MATERIALS_FILE = orig
```

#### `tests/test_nl_tasks.py`:
```python
"""Tests for natural language task parser."""
from material_ai_workbench.nl_tasks import parse_natural_language_task


def test_parse_chinese_j2():
    result = parse_natural_language_task("用J2模型，屈服强度80MPa，弹性模量210GPa")
    assert result.material is not None
    assert result.material.material_type == "j2"
    assert result.material.yield_strength == 80
    assert result.material.youngs_modulus == 210000


def test_parse_english_hill():
    result = parse_natural_language_task("Hill material with sy=120, E=70000, C=2.0")
    assert result.material is not None
    assert result.material.material_type == "hill"
    assert result.material.yield_strength == 120
    assert result.ml.c_value == 2.0
```

### Acceptance Criteria
- `python -m pytest tests/ -v` runs 7+ tests
- All tests pass without Abaqus installed
- Test suite completes in under 30 seconds

---

## Task 0.5: Create Missing Documentation

### Context
README_CN.md references two documents that don't exist:
- `docs/ABAQUS_MCP_WORKBENCH_CN.md`
- `docs/CASE_LIBRARY_USER_GUIDE_CN.md`

### Actions

#### 0.5a: Create `docs/ABAQUS_MCP_WORKBENCH_CN.md`

Write a user guide covering:
1. What is Abaqus MCP: a TCP socket bridge that lets Python talk to a running Abaqus/CAE session
2. Prerequisites: Abaqus/CAE 2023+, the MCP plugin installed
3. How to start the bridge: `Plug-ins > Abaqus MCP > Start Socket Bridge`
4. Default address: `127.0.0.1:48152`
5. Available operations (with Streamlit UI screenshots or terminal examples): connection check, model info, job list/monitor/submit, ODB inspect, field extraction, viewport capture, session snapshot
6. Troubleshooting: connection refused, timeout, Abaqus frozen
7. Protocol overview: JSON-over-TCP, newline-delimited, UUID request/response

#### 0.5b: Create `docs/CASE_LIBRARY_USER_GUIDE_CN.md`

Write a user guide covering:
1. What is the case library: indexes Abaqus simulation folders without copying large files
2. How to add a case: scan a folder or point to a single `.inp`
3. What gets extracted: INP structure, result CSV signals, log diagnostics, ODB fields
4. How to browse cases in the Streamlit UI
5. ODB deep post-processing: field extraction, frame series, named sets
6. How to export a training dataset from the case library
7. Using the dataset to train a surrogate model
8. File structure under `cases/<case_id>/`

### Acceptance Criteria
- Both files exist at the paths referenced in README_CN.md
- Each is at least 500 words of substantive documentation
- A new user can follow either guide end-to-end without additional help
