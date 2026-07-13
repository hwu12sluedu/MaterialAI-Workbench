# Phase 2: Material Model Expansion

## Objective
Extend from J2/Hill to Barlat anisotropic yield, experimental-curve-driven plasticity, and hyperelastic entry points.

## Prerequisites
- Phase 0 complete (config.py, tests)
- Phase 1 recommended (logging for debugging)

---

## Task 2.1: Add Barlat Yld2000-2D Yield Criterion

### Context
Currently only J2 (isotropic) and Hill (anisotropic) are supported. Barlat Yld2000-2D is the industry standard for aluminum alloy sheet forming. The `pyLabFEA` library already supports Barlat — we need to expose it through the Workbench pipeline.

### Background
In pyLabFEA, Barlat Yld2000-2D is an 8-parameter anisotropic yield function. The parameters (typically called `a1` through `a8`, or alpha parameters) control the shape of the yield surface. The exponent `m` is 8 for FCC materials (aluminum) and 6 for BCC (steel).

### Files to modify

#### a) `pipeline.py` — `WorkbenchConfig`

Add fields to the dataclass:
```python
barlat_exponent: float = 8.0          # 8 for FCC (Al), 6 for BCC (steel)
barlat_alphas: tuple[float, ...] = (  # 8 alpha parameters for Yld2000-2D
    1.0, 1.0, 1.0, 1.0, 1.0, 1.0, 1.0, 1.0,
)
```

#### b) `pipeline.py` — `_create_reference_material()`

Add elif branch:
```python
elif material_type == "barlat":
    ref_mat.plasticity(
        sy=config.yield_strength,
        barlat_exp=config.barlat_exponent,
        barlat_alphas=list(config.barlat_alphas),
        sdim=6,
    )
```

#### c) `pipeline.py` — `_create_ml_material()`

For barlat, the ML material setup is same as Hill (non-dev-only):
```python
if material_type == "j2":
    ml_mat.dev_only = True
# barlat and hill both keep dev_only = False
```

#### d) `run_workbench.py` — CLI args

Add:
```python
parser.add_argument("--barlat-exponent", type=float, default=8.0)
parser.add_argument("--barlat-alphas", type=float, nargs=8,
                    default=[1.0, 1.0, 1.0, 1.0, 1.0, 1.0, 1.0, 1.0])
```

#### e) `material_library.py` — `MaterialPreset`

Add fields:
```python
barlat_exponent: float = 8.0
barlat_alphas: list[float] = field(default_factory=lambda: [1.0]*8)
```

#### f) `streamlit_app.py` — `_training_panel()`

Add "barlat" to the material type dropdown. When barlat is selected, show:
- `barlat_exponent` number input (6 or 8)
- 8 alpha parameter number inputs in a 2x4 grid

#### g) `nl_tasks.py` — `parse_natural_language_task()`

Add regex patterns for barlat keywords:
- Chinese: "巴莱特", "Barlat", "Yld2000", "铝板"
- English: "barlat", "yld2000", "aluminum"

### Acceptance Criteria
- `python -m material_ai_workbench.run_workbench --material barlat --name test_barlat --barlat-exponent 8 --barlat-alphas 0.9 1.0 0.8 1.0 1.0 1.0 0.9 1.1` produces valid output
- Yield locus plot shows anisotropic shape (not circular)
- UMAT SVM parameters are exported correctly
- Streamlit UI barlat controls work
- Test: `test_barlat_training_creates_outputs()` added to `tests/test_pipeline.py`

---

## Task 2.2: Experimental Curve-Driven Plasticity

### Context
Currently, material models are defined by analytical parameters (E, nu, sy, etc.). Real materials are often characterized by experimental stress-strain curves. Need a path: import experimental CSV → train ML model directly from the curve data.

### Design Decision
Rather than trying to auto-fit analytical model parameters (which is a research problem), we create a "tabular" material type where the pyLabFEA material is parameterized directly from the imported stress-strain data points. The ML yield surface is trained on load cases derived from the experimental flow curve.

### Files to modify

#### a) `data_import.py` — connect to `pipeline.py`

Add a function to convert imported data to a `WorkbenchConfig`:
```python
def imported_curve_to_config(
    import_dir: Path | str,
    material_type: str = "j2",
    name: str | None = None,
) -> "WorkbenchConfig | None":
    """Build a WorkbenchConfig from an imported experimental curve.

    Reads the normalized curve CSV from the import directory,
    estimates Young's modulus from the initial slope,
    estimates yield strength via 0.2% offset method,
    and returns a config ready for pipeline training.
    """
    import json
    from pathlib import Path
    from material_ai_workbench.pipeline import WorkbenchConfig

    import_dir = Path(import_dir)
    summary_path = import_dir / "summary.json"
    if not summary_path.exists():
        return None

    summary = json.loads(summary_path.read_text())
    curve_csv = import_dir / "normalized_curve.csv"

    # Read curve data
    import csv
    strains, stresses = [], []
    with open(curve_csv, newline="", encoding="utf-8") as f:
        reader = csv.DictReader(f)
        for row in reader:
            strains.append(float(row["strain"]))
            stresses.append(float(row["stress_mpa"]))

    import numpy as np
    strains = np.array(strains)
    stresses = np.array(stresses)

    # Estimate E from initial linear region (first 0.05% strain)
    elastic_mask = strains <= 0.0005
    if elastic_mask.sum() >= 3:
        E = float(np.polyfit(strains[elastic_mask], stresses[elastic_mask], 1)[0])
    else:
        E = 200_000.0  # fallback default

    # Estimate 0.2% offset yield
    offset_line = E * (strains - 0.002)
    yield_mask = stresses < offset_line
    if yield_mask.any():
        # Take last point below offset line as yield
        sy = float(stresses[yield_mask][-1])
    else:
        sy = 60.0  # fallback

    return WorkbenchConfig(
        material_type=material_type,
        name=name or f"exp_{import_dir.name}",
        youngs_modulus=E,
        poisson_ratio=0.3,
        yield_strength=sy,
        calculate_curves=True,
    )
```

#### b) `streamlit_app.py` — `_data_import_panel()`

Add a button: "Train Material from This Curve" that:
1. Calls `imported_curve_to_config()` to build config
2. Shows estimated E and sy to the user for confirmation
3. On confirm, calls `run_material_workbench()`
4. Shows link to the resulting run

#### c) Update `DataImportResult` dataclass

Add estimated properties:
```python
estimated_E: float | None = None
estimated_sy: float | None = None
```

Set them in `import_csv_dataset()` after curve loading.

### Acceptance Criteria
- Import a valid stress-strain CSV → see estimated E and sy in import report
- Click "Train Material from This Curve" → pipeline runs → yield locus and curves generated
- Estimated E within 10% of true value for a clean linear-elastic start
- Handler gracefully when imported CSV has no elastic region (noise, already-plastic data)

---

## Task 2.3: Hyperelastic Material Entry Point

### Context
For rubber, elastomers, and soft biological tissues. pyLabFEA supports hyperelastic models (Neo-Hookean, Mooney-Rivlin). We add them as trainable material types.

### Background
Unlike plastic models, hyperelastic models are trained on different data: strain energy density vs. deformation. The pyLabFEA hyperelastic workflow differs from the SVC-based plastic workflow. For an MVP entry point, we support:
- `neo_hookean`: Single parameter C10
- `mooney_rivlin`: Two parameters C10, C01

The Workbench for hyperelastic materials skips the SVC training (no yield surface) and instead:
1. Defines the analytical model
2. Computes stress-strain curves for uniaxial, biaxial, planar tension
3. Exports Abaqus material card (not UMAT — Abaqus has native hyperelastic support)

### Files to modify

#### a) `pipeline.py` — `WorkbenchConfig`

Add hyperelastic-specific fields:
```python
# Hyperelastic parameters
hyperelastic_model: str = "neo_hookean"     # "neo_hookean" or "mooney_rivlin"
hyperelastic_C10: float = 1.0
hyperelastic_C01: float = 0.0               # Only used for Mooney-Rivlin
hyperelastic_D1: float = 0.0                # Incompressibility parameter
```

#### b) `pipeline.py` — `_create_reference_material()`

Add hyperelastic branch:
```python
if material_type in ("neo_hookean", "mooney_rivlin"):
    # pyLabFEA hyperelastic material setup
    mat = FE.Material(name=f"{material_type.upper()}-reference", num=1)
    mat.elasticity(E=config.youngs_modulus, nu=config.poisson_ratio)
    if material_type == "neo_hookean":
        mat.hyperelastic(model="neo_hookean", C10=config.hyperelastic_C10,
                         D1=config.hyperelastic_D1)
    elif material_type == "mooney_rivlin":
        mat.hyperelastic(model="mooney_rivlin",
                         C10=config.hyperelastic_C10,
                         C01=config.hyperelastic_C01,
                         D1=config.hyperelastic_D1)
    return mat
```

**Important**: If `pyLabFEA.Material` does not have a `hyperelastic()` method, this task first requires checking the pyLabFEA API. If the method exists but has a different signature, adapt to it. If it doesn't exist, document the gap and implement the forward calculation using pyLabFEA's lower-level stress computation utilities.

#### c) `pipeline.py` — `run_material_workbench()`

For hyperelastic materials, skip SVC training and UMAT export. Generate only:
- Stress-strain curves (uniaxial, equibiaxial, planar if supported)
- A summary JSON with the material parameters
- An Abaqus-compatible material parameter card as a text file

#### d) `streamlit_app.py` — training panel

Add hyperelastic models to the material type selector. When selected, show C10/C01/D1 inputs.

### Acceptance Criteria
- `python -m material_ai_workbench.run_workbench --material neo_hookean --name test_nh --hyperelastic-C10 0.5` produces stress-strain curves
- Mooney-Rivlin with C01=0 reduces to Neo-Hookean behavior
- Model card export is in valid Abaqus `*HYPERELASTIC` keyword format
- If pyLabFEA lacks hyperelastic support: a feature-gap document is created at `docs/HYPERELASTIC_GAP.md`

---

## Dependencies Between Tasks

```
2.1 (Barlat) ── independent, can do first
2.2 (experimental curves) ── depends on 1.3 (data validation) being done
2.3 (hyperelastic) ── independent, may require pyLabFEA investigation first
```

All three tasks are independent of each other and can be parallelized.
