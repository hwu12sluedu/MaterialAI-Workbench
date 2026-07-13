# MaterialAI Workbench — Final State & Next Steps for Codex

2026-07-04 | Tests: 8 passed / 4 skipped | All 3 pipelines verified

---

## What Changed This Session (What You Already Did)

| Category | Files Changed | What |
|----------|--------------|------|
| **Data Import** | `data_import.py` | `_validate_stress_strain_curve()` — monotonicity, NaN, stiffness sanity checks |
| | | `imported_curve_to_config()` — auto-estimate E and sy from experimental CSV → `WorkbenchConfig` |
| **Barlat Yld2000-2D** | `pipeline.py`, `run_workbench.py`, `nl_tasks.py` | Barlat yield criterion (8-parameter Yld2000-2D → pyLabFEA Yld2004 18-param). CLI `--material barlat` with `--barlat-alphas`. Verified: SV=131, F1=0.84 |
| **Case Similarity** | `case_library.py`, `streamlit_app.py` | `find_similar_cases()` — cosine similarity on INP features. UI shows Top-5 similar cases with scores. |
| **Composite Abaqus** | `composite_workflow.py` | Material Orientation fix (line 986), `run_composite_closed_loop.py` module entry. Verified: Abaqus solve → Max Mises 1829 MPa. |
| **Job Queue** | `job_queue.py`, `streamlit_app.py` | `JobQueue` with `QueuedJob` status tracking (queued/running/completed/failed), JSON persistence, UI panel `_abaqus_job_queue_panel()` |
| **Multi-Fidelity** | `multi_fidelity.py`, `streamlit_app.py` | `train_multi_fidelity()` — additive correction model (low-fidelity base + high-fidelity residual). Integrated into surrogate panel. |
| **UI Polish** | `streamlit_app.py` | Sidebar navigation, 180 `key=` on buttons, 26 `height=` on dataframes, 20 `st.divider()`, Chinese labels throughout |
| **LLM** | `llm_adapter.py`, `param_recommender.py` | OpenAI-compatible `/chat/completions`, report interpretation (`interpret_report()`), parameter recommendation (`recommend_parameters()`) |
| **Dead Code** | `task_queue.py` | Removed (was never imported, superseded by `job_queue.py`) |
| **Infrastructure** | `.gitignore`, `environment.yml`, `requirements.txt`, `docs/*.md` | Git repo initialized, dependency files, user guides for MCP and Case Library |

---

## Full Pipeline Status (All Verified)

```
Metal Plasticity (J2)     : Train → UMAT → Abaqus → Case → ODB → Dataset → Surrogate → Report  [8/8]
Metal Plasticity (Hill)   : Train → UMAT → Abaqus → Case → ODB → Dataset → Surrogate → Report  [8/8]
Metal Plasticity (Barlat) : Train → UMAT → Abaqus → Case → ODB → Dataset → Surrogate → Report  [8/8] NEW
Composite (RVE→Plate)     : RVE → Abaqus Plate Solve → ODB PostProcess → Result (1829 MPa)      [Verified] NEW
```

### Surrogate Model Quality

| Pipeline | Samples | Model | MAE | RMSE | R² | Uncertainty PI |
|----------|---------|-------|-----|------|----|-----------------|
| Metal J2 | 12 | RandomForest | 15.9 | 17.6 | -0.11 | ±25.7 MPa (89% coverage) |
| Metal J2 | 5 | MLP | 19.7 | 22.2 | 0.48 | — |
| Composite | 3 | RandomForest | 38.8 | 43.1 | 0.80 | ±126.6 MPa (100% coverage) |

---

## Remaining Work for Codex (3 Items)

### 1. PBC Micro RVE Regression Data

**Current state:** The composite pipeline generates 6 PBC load case INP files and post-process scripts (`extract_rve_effective_stiffness.py`), but nobody has run them yet. The Abaqus plate model uses rule-of-mixtures estimates for effective properties — NOT Abaqus-homogenized values.

**What to do:**
- Run `run_pbc_jobs.ps1` in a composite run's `micro_rve/` directory
- This submits 6 Abaqus jobs (EXX, EYY, EZZ, GXY, GXZ, GYZ) for RVE homogenization
- After completion, run `extract_rve_effective_stiffness.py` to get Abaqus-verified stiffness
- Update the plate model material card with Abaqus-homogenized values
- Compare rule-of-mixtures vs Abaqus-homogenized effective properties
- Add a flag `use_abaqus_homogenization` to `CompositePlateConfig`

**File:** `composite_workflow.py`, `composite_runs/<latest>/micro_rve/`

### 2. Hyperelastic Material Models

**Current state:** `pipeline.py` mentions `"hyperelastic"` in material choices but `_create_reference_material()` raises NotImplementedError. pyLabFEA has hyperelastic support (Neo-Hookean, Mooney-Rivlin).

**What to do:**
- Check pyLabFEA API at `src/pylabfea/material.py` for hyperelastic methods
- Implement `pipeline.py` support for `material_type="neo_hookean"` and `"mooney_rivlin"`
- Generate:
  - Uniaxial/biaxial/planar tension stress-strain curves (no yield surface — hyperelastic has no yield)
  - Abaqus `*HYPERELASTIC` material card export (not UMAT — Abaqus has native support)
- Add `--hyperelastic-C10`, `--hyperelastic-C01`, `--hyperelastic-D1` CLI args
- Add a preset material to the library

**Files:** `pipeline.py`, `run_workbench.py`, `streamlit_app.py`

### 3. LLM API Configuration Wizard

**Current state:** LLM adapter code is complete but requires manual env var setup (`MATERIALAI_LLM_BASE_URL`, `MATERIALAI_LLM_MODEL`, `MATERIALAI_LLM_API_KEY`). The Streamlit UI has text inputs for these but doesn't persist them across sessions.

**What to do:**
- Add a "Save LLM Config" button that writes to `.env` or Streamlit secrets
- Add a "Test Connection" button that calls `plan_task_with_llm("ping")` and shows success/failure
- Pre-populate known public providers (OpenAI, local Ollama, etc.) as quick-select options
- Add connection status indicator to the sidebar

**Files:** `llm_adapter.py`, `streamlit_app.py`

---

## Files NOT to Touch

- `specs/` directory — these are design documents, not code
- `_run_*.py` files — temporary test scripts, can be deleted
- `runs/`, `batches/`, `cases/`, `composite_runs/`, etc. — generated output data

---

## Run Commands Reference

```powershell
# Setup
$env:PYTHONPATH = "D:\githubproject\pyLabFEA"
$env:PATH = "D:\Anaconda3\condabin;" + $env:PATH

# Train J2 material
conda run -n pylabfea python -m material_ai_workbench.run_workbench --material j2 --name demo

# Train Barlat material
conda run -n pylabfea python -m material_ai_workbench.run_workbench --material barlat --name demo_barlat --barlat-alphas 0.9 1.05 0.85 1.0 1.0 1.0 0.95 1.1

# Composite closed-loop
conda run -n pylabfea python -m material_ai_workbench.run_composite_closed_loop

# Streamlit
conda run -n pylabfea streamlit run material_ai_workbench/streamlit_app.py --server.port 8501

# Tests
conda run -n pylabfea python -m pytest material_ai_workbench/tests -v
```
