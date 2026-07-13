# Codex Round 2 — Bug Fixes + 12 New Tasks

2026-07-04 | Based on full audit of Round 1 changes

---

## BUGS FOUND (Fix These First)

### BUG-1: Hyperelastic listed but crashes immediately
**Severity: HIGH**  
**Files:** `run_workbench.py:55`, `pipeline.py:241-244`, `streamlit_app.py`

`run_workbench.py` CLI has `choices=("j2", "hill", "barlat", "hyperelastic")`. Streamlit dropdown also includes it. But `_create_reference_material()` in `pipeline.py` raises `NotImplementedError` immediately.

```python
# pipeline.py line 241-244:
elif material_type == "hyperelastic":
    raise NotImplementedError("Hyperelastic training ... not yet supported")
```

**Fix:** Remove `"hyperelastic"` from CLI choices and Streamlit dropdown until it's implemented. OR implement basic Neo-Hookean support (see Task 5 below).

---

### BUG-2: Duplicate validation warnings with fragile string dedup
**Severity: MEDIUM**  
**File:** `data_import.py:74-86`

`_validate_stress_strain_curve()` is called twice:
1. On raw data (strain may be percent-scale, e.g., 5.0)
2. On normalized data (strain is absolute, e.g., 0.05)

The "units may be percent" warning embeds the actual value: `"Strain range 5.00 - units may be percent"` vs `"Strain range 0.05 - ..."`. These are different strings, so the dedup at line 85 (`if warning not in warnings`) can't match them. Result: user sees duplicate or confusing warnings.

**Fix:** Use a structured warning type (e.g., tuple of `(category, message)`) or check only the warning prefix before the number. Or better: only validate the normalized data, skip raw-data validation.

---

### BUG-3: Uncertainty code silently swallows ALL exceptions
**Severity: LOW**  
**File:** `composite_dataset.py:233-234`

```python
except Exception:
    pass
```

If uncertainty computation fails for any reason (e.g., incompatible sklearn version, memory error), the user gets no feedback. The surrogate appears to train successfully but without uncertainty intervals.

**Fix:** Add `import logging; _log = logging.getLogger(__name__)` and `_log.warning("Ensemble uncertainty failed: %s", exc)` inside the except block.

---

### BUG-4: Empty job name default in Job Queue panel
**Severity: LOW**  
**File:** `streamlit_app.py:1477`

```python
job_name = q1.text_input("Job 名称",
    value=(Path(input_file).stem if input_file else "queued_abaqus_job"), ...)
```

When `input_file` is `""` (user hasn't selected one), `Path("").stem` returns `""` (not `"."` as you might expect). This produces an empty default job name. Abaqus rejects empty job names.

**Fix:** Add `if not input_file.strip():` guard, or use `or "queued_abaqus_job"` after the conditional.

---

## TASK LIST (12 items, ordered)

### TASK 1: Fix All 4 Bugs Above
Do BUG-1 through BUG-4 as a single task. Remove hyperelastic from choices, fix validation dedup, add logging to uncertainty, fix empty job name default.

### TASK 2: PBC Micro RVE Abaqus Homogenization Pipeline
**Why:** The composite plate model currently uses rule-of-mixtures estimates. Running the 6 PBC load cases in Abaqus gives REAL homogenized stiffness that replaces estimates with data.

**What to do:**
1. In `run_composite_closed_loop.py` (or a new script), after Stage 1, run the PBC jobs:
   ```python
   pbc_dir = result.micro_pbc_job_dir
   # Run 6 Abaqus jobs: EXX, EYY, EZZ, GXY, GXZ, GYZ
   for job_name in result.manifest["paths"]["micro_pbc_jobs"]:
       inp = pbc_dir / f"{job_name}.inp"
       subprocess.run([abaqus_bat, f"job={job_name}", f"input={inp.name}", "cpus=4", "interactive"], cwd=pbc_dir, ...)
   ```
2. After all 6 complete, run `extract_rve_effective_stiffness.py` to get Abaqus-verified stiffness
3. Compare rule-of-mixtures values vs Abaqus-homogenized values
4. Update the plate material card with Abaqus values (or add `--use-abaqus-homogenization` flag)
5. Update `composite_plate_dataset_row.csv` to include both estimated AND Abaqus-homogenized properties

**Acceptance:** PBC jobs complete, stiffness CSV has E1/E2/G12 from Abaqus within 10% of rule-of-mixtures (Vf=0.55).

### TASK 3: Batch Composite Data Generation (10+ Samples)
**Why:** Current composite surrogate has only 3 samples. Need 10+ for meaningful ML.

**What to do:**
1. Run `run_composite_batch.py create` with 12+ samples:
   ```
   conda run -n pylabfea python -m material_ai_workbench.run_composite_batch create \
     --name rve_sweep_12 --sample-count 12 \
     --vf-min 0.4 --vf-max 0.7 \
     --interface-efficiency-min 0.8 --interface-efficiency-max 1.0 \
     --hole-radius-min 3.0 --hole-radius-max 7.0
   ```
2. Run all 12 samples (Abaqus solve per sample is fast — single element plate, ~10s each)
3. Train surrogate on the 12-sample dataset with uncertainty
4. Compare R² vs the 3-sample baseline (should improve from 0.80 → hopefully >0.90)

**Acceptance:** 12+ samples completed, composite_dataset.csv has 12+ rows, surrogate R² > 0.85.

### TASK 4: Hyperelastic Material Model Implementation
**Why:** Currently placeholder. Rubber/elastomer materials need this for completeness.

**What to do:**
1. Check pyLabFEA hyperelastic API at `src/pylabfea/material.py` — look for `hyperelastic`, `neo_hookean`, `mooney_rivlin` methods
2. Implement in `pipeline.py`:
   - Neo-Hookean: single parameter C10
   - Mooney-Rivlin: two parameters C10, C01
   - Skip SVC training (no yield surface)
   - Generate uniaxial/biaxial/planar stress-strain curves
   - Export Abaqus `*HYPERELASTIC` material card
3. Add CLI args `--hyperelastic-C10`, `--hyperelastic-C01`, `--hyperelastic-D1`
4. Add "Neo-Hookean" and "Mooney-Rivlin" presets to material library
5. Add to Streamlit dropdown

**Acceptance:** `--material neo_hookean --hyperelastic-C10 0.5` produces stress-strain curves and Abaqus material card.

### TASK 5: Real Experimental Data Validation (with pyLabFEA FE Curve Check)
**Why:** `data_import.py` has validation but doesn't check against pyLabFEA's FE curve generation. Import + train + compare gives a full validation loop.

**What to do:**
1. After `imported_curve_to_config()` builds the config, run `run_material_workbench(config)` with `calculate_curves=True`
2. Compare the pyLabFEA-generated stress-strain curves against the imported experimental data
3. Add a "Validation" section to the import report showing:
   - Overlay plot: experimental vs pyLabFEA curves
   - R² of pyLabFEA fit to experimental data
   - Maximum stress deviation

**Acceptance:** Import experimental CSV → train → report shows overlay plot comparing experiment vs ML predictions.

### TASK 6: Surrogate Model Comparison Dashboard
**Why:** Multiple surrogate runs accumulate. Need a way to compare them.

**What to do:**
1. In `streamlit_app.py` Results Browser or Surrogate panel, add a "模型对比" section
2. Use `surrogate_comparison_rows()` from `surrogate_model.py` to build a comparison table
3. Show: model type, target, MAE, RMSE, R², CV metrics, uncertainty PI width, sample count
4. Add a bar chart comparing MAE across models
5. Highlight the best model (lowest RMSE, highest R²)

**Acceptance:** Table shows all surrogate runs sorted by RMSE. Best model highlighted.

### TASK 7: Material Library → Direct Abaqus Export
**Why:** Users create material presets. They should be able to go directly from preset → Abaqus verification without going through the training panel.

**What to do:**
In `streamlit_app.py` Model Management panel:
1. For each preset, add a "快速验算" button
2. On click: load preset → train → run Abaqus 1-load-case sanity check
3. Show a progress indicator
4. If successful, show link to run directory

**Acceptance:** Click "快速验算" on Demo_J2_60MPa → Abaqus unit-element check completes → link to results.

### TASK 8: Case Library Batch Export Wizard
**Why:** Exporting datasets requires selecting the "right" cases. A wizard helps users pick relevant cases.

**What to do:**
1. Add a "批量导出向导" expander in the case library panel
2. Let user filter cases by: tags, status, date range, material type, case type (metal vs composite)
3. Preview how many cases match each filter
4. "一键导出" button that calls `export_case_dataset()` with the filtered cases
5. Show export summary (N cases, M features, target columns)

**Acceptance:** Filter by tag "j2" → shows 5 matching cases → export produces dataset with those 5 cases.

### TASK 9: Abaqus Job Queue History + Retry
**Why:** `job_queue.py` works for submitting but doesn't track history or support retry.

**What to do:**
1. Add a "retry" button next to failed jobs that re-submits them
2. Add a "view log" button that displays the .log file contents in an expander
3. Add a job history table at the bottom showing all completed/failed jobs
4. Add queue statistics: total submitted, success rate, average duration
5. Persist queue history in `job_queue_history.json`

**Acceptance:** Failed job shows "重试" button. Click → re-submits → runs → completes.

### TASK 10: CLI Pipeline for Batch Metal Plasticity with Abaqus
**Why:** Currently only composite has a full CLI pipeline. Metal plasticity needs one too.

**What to do:**
Create `run_metal_closed_loop.py` (similar to `run_composite_closed_loop.py`):
1. Create parameter sweep (sy=50, 60, 70, 80, 90 MPa)
2. For each: train → Abaqus verify → archive case → ODB extract
3. Export dataset from all cases
4. Train surrogate with uncertainty
5. Generate closed-loop report
6. Print summary table

**Acceptance:** `python -m material_ai_workbench.run_metal_closed_loop` → 5 samples → surrogate trained → report generated.

### TASK 11: Barlat Documentation + Test
**Why:** The Barlat α→Yld2004 mapping is an engineering approximation. Users need to understand the limitations.

**What to do:**
1. Document `_barlat18_from_yld2000_alphas()` transformation in detail
2. Add a test: `tests/test_barlat.py` with:
   - Verify 8 alphas → 18 coefficients
   - Verify isotropic alphas (all 1.0) produce near-circular yield surface
   - Verify anisotropic alphas produce non-circular yield surface
3. Add a Streamlit info box explaining the approximation when Barlat is selected
4. Add a reference link to the Yld2000-2D / Yld2004 literature

**Acceptance:** Test verifies isotropic Barlat produces circular yield surface within 5% tolerance.

### TASK 12: Docker Image + CI Complete
**Why:** Phase 6 from the original plan. Package for deployment.

**What to do:**
1. Verify `Dockerfile` at `D:\githubproject\pyLabFEA\Dockerfile` builds correctly
2. Add `matplotlib.use("Agg")` to Dockerfile's CMD if needed
3. Verify `docker-compose.yml` mounts volumes correctly
4. Test: `docker build -t material-ai-workbench .` + `docker run -p 8501:8501 material-ai-workbench`
5. Fix `.github/workflows/ci.yml` to install `pylabfea` dependency
6. Verify CI passes: `pytest material_ai_workbench/tests/ -v`

**Acceptance:** `docker build` succeeds, `curl http://localhost:8501` returns 200, CI green.

---

## Execution Order

```
BUG-1 → BUG-2 → BUG-3 → BUG-4  (fixed in one pass)
  ↓
TASK 2 (PBC) → TASK 3 (batch composite data)
  ↓
TASK 5 (exp data validation) → TASK 4 (hyperelastic)
  ↓
TASK 6 → TASK 7 → TASK 8 → TASK 9 → TASK 10 → TASK 11 → TASK 12
```

Tasks 6-12 are independent and can be parallelized.

---

## Code Quality Notes for Round 2

- Codex Round 1 was very productive. Almost all code is correct and well-structured.
- The 4 bugs found are minor (1 HIGH — hyperelastic crash, 3 LOW/MEDIUM).
- The LLM adapter now has full .env persistence + provider presets — this was the user's main concern, now resolved.
- All 3 pipelines (J2, Hill, Barlat) verified working with uncertainty quantification.
