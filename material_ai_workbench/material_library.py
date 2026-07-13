"""JSON-backed material preset library for MaterialAI Workbench."""

from __future__ import annotations

import json
from dataclasses import asdict, dataclass
from datetime import datetime
from pathlib import Path
from typing import Any

from material_ai_workbench.config import RUNS_ROOT
from material_ai_workbench.pipeline import WorkbenchConfig


LIBRARY_DIR = Path(__file__).resolve().parent / "library"
MATERIALS_FILE = LIBRARY_DIR / "materials.json"


@dataclass
class MaterialPreset:
    name: str
    material_type: str = "j2"
    youngs_modulus: float = 200_000.0
    poisson_ratio: float = 0.3
    yield_strength: float = 60.0
    hill_ratios: list[float] | None = None
    barlat_alphas: list[float] | None = None
    barlat_exponent: float = 8.0
    hyperelastic_c10: float = 0.5
    hyperelastic_c01: float = 0.2
    hyperelastic_d1: float = 0.0
    c_value: float = 1.0
    gamma: float = 1.0
    n_load_cases: int = 40
    n_sequence: int = 4
    test_size: int = 80
    plot_mesh: int = 50
    calculate_curves: bool = False
    notes: str = ""
    created_at: str = ""
    updated_at: str = ""

    def normalized(self) -> "MaterialPreset":
        now = datetime.now().isoformat(timespec="seconds")
        if not self.created_at:
            self.created_at = now
        self.updated_at = now
        if self.hill_ratios is None:
            self.hill_ratios = [1.2, 1.0, 0.8, 1.0, 1.0, 1.0]
        if self.barlat_alphas is None:
            self.barlat_alphas = [1.0] * 8
        self.material_type = self.material_type.lower()
        return self


def load_material_presets() -> dict[str, MaterialPreset]:
    ensure_material_library()
    payload = json.loads(MATERIALS_FILE.read_text(encoding="utf-8"))
    presets: dict[str, MaterialPreset] = {}
    for item in payload.get("materials", []):
        preset = MaterialPreset(**item).normalized()
        presets[preset.name] = preset
    return dict(sorted(presets.items(), key=lambda pair: pair[0].lower()))


def save_material_preset(preset: MaterialPreset) -> None:
    presets = load_material_presets()
    preset.normalized()
    presets[preset.name] = preset
    _write_presets(presets)


def delete_material_preset(name: str) -> None:
    presets = load_material_presets()
    presets.pop(name, None)
    _write_presets(presets)


def ensure_material_library() -> None:
    LIBRARY_DIR.mkdir(parents=True, exist_ok=True)
    if MATERIALS_FILE.exists():
        return
    now = datetime.now().isoformat(timespec="seconds")
    defaults = [
        MaterialPreset(
            name="Demo_J2_60MPa",
            material_type="j2",
            youngs_modulus=200_000.0,
            poisson_ratio=0.3,
            yield_strength=60.0,
            c_value=1.0,
            gamma=1.0,
            notes="pyLabFEA J2 baseline used for fast sanity checks.",
            created_at=now,
            updated_at=now,
        ),
        MaterialPreset(
            name="Demo_Hill_sheet",
            material_type="hill",
            youngs_modulus=200_000.0,
            poisson_ratio=0.3,
            yield_strength=50.0,
            hill_ratios=[1.2, 1.0, 0.8, 1.0, 1.0, 1.0],
            c_value=1.5,
            gamma=1.0,
            notes="Hill anisotropic sheet-material style demo preset.",
            created_at=now,
            updated_at=now,
        ),
        MaterialPreset(
            name="Demo_Barlat_Al_sheet",
            material_type="barlat",
            youngs_modulus=70_000.0,
            poisson_ratio=0.33,
            yield_strength=150.0,
            barlat_alphas=[0.9, 1.0, 0.85, 1.05, 1.0, 0.95, 0.9, 1.1],
            barlat_exponent=8.0,
            c_value=1.5,
            gamma=1.0,
            notes="Starter Barlat/Yld2000-style aluminum sheet forming preset.",
            created_at=now,
            updated_at=now,
        ),
        MaterialPreset(
            name="Demo_NeoHookean_rubber",
            material_type="neo_hookean",
            youngs_modulus=6.0,
            poisson_ratio=0.49,
            yield_strength=1.0,
            hyperelastic_c10=0.5,
            hyperelastic_c01=0.0,
            hyperelastic_d1=0.0,
            notes="Starter rubber-like Neo-Hookean preset for Abaqus *HYPERELASTIC export.",
            created_at=now,
            updated_at=now,
        ),
        MaterialPreset(
            name="Demo_MooneyRivlin_rubber",
            material_type="mooney_rivlin",
            youngs_modulus=8.0,
            poisson_ratio=0.49,
            yield_strength=1.0,
            hyperelastic_c10=0.45,
            hyperelastic_c01=0.15,
            hyperelastic_d1=0.0,
            notes="Starter Mooney-Rivlin preset for elastomer curve generation and Abaqus export.",
            created_at=now,
            updated_at=now,
        ),
    ]
    _write_presets({preset.name: preset for preset in defaults})


def preset_to_training_state(preset: MaterialPreset) -> dict[str, Any]:
    preset.normalized()
    return {
        "train_material_type": preset.material_type,
        "train_name": preset.name,
        "train_E": float(preset.youngs_modulus),
        "train_nu": float(preset.poisson_ratio),
        "train_sy": float(preset.yield_strength),
        "train_C": float(preset.c_value),
        "train_gamma": float(preset.gamma),
        "train_n_load_cases": int(preset.n_load_cases),
        "train_n_sequence": int(preset.n_sequence),
        "train_test_size": int(preset.test_size),
        "train_plot_mesh": int(preset.plot_mesh),
        "train_calculate_curves": bool(preset.calculate_curves),
        **{f"train_hill_r{i + 1}": float(value) for i, value in enumerate(preset.hill_ratios or [])},
        "train_barlat_exponent": float(preset.barlat_exponent),
        **{f"train_barlat_a{i + 1}": float(value) for i, value in enumerate(preset.barlat_alphas or [])},
        "train_hyperelastic_c10": float(preset.hyperelastic_c10),
        "train_hyperelastic_c01": float(preset.hyperelastic_c01),
        "train_hyperelastic_d1": float(preset.hyperelastic_d1),
    }


def preset_to_workbench_config(
    preset: MaterialPreset,
    *,
    output_dir: Path | None = None,
    name_suffix: str = "",
    calculate_curves: bool | None = None,
) -> WorkbenchConfig:
    preset.normalized()
    return WorkbenchConfig(
        material_type=preset.material_type,
        name=f"{preset.name}{name_suffix}",
        output_dir=output_dir or RUNS_ROOT,
        youngs_modulus=float(preset.youngs_modulus),
        poisson_ratio=float(preset.poisson_ratio),
        yield_strength=float(preset.yield_strength),
        hill_ratios=tuple(float(value) for value in (preset.hill_ratios or [1.2, 1.0, 0.8, 1.0, 1.0, 1.0])),
        barlat_alphas=tuple(float(value) for value in (preset.barlat_alphas or [1.0] * 8)),
        barlat_exponent=float(preset.barlat_exponent),
        hyperelastic_c10=float(preset.hyperelastic_c10),
        hyperelastic_c01=float(preset.hyperelastic_c01),
        hyperelastic_d1=float(preset.hyperelastic_d1),
        c_value=float(preset.c_value),
        gamma=float(preset.gamma),
        n_load_cases=int(preset.n_load_cases),
        n_sequence=int(preset.n_sequence),
        test_size=int(preset.test_size),
        plot_mesh=int(preset.plot_mesh),
        calculate_curves=bool(preset.calculate_curves if calculate_curves is None else calculate_curves),
    )


def preset_from_training_state(name: str, state: dict[str, Any], notes: str = "") -> MaterialPreset:
    return MaterialPreset(
        name=name.strip(),
        material_type=str(state.get("train_material_type", "j2")),
        youngs_modulus=float(state.get("train_E", 200_000.0)),
        poisson_ratio=float(state.get("train_nu", 0.3)),
        yield_strength=float(state.get("train_sy", 60.0)),
        hill_ratios=[float(state.get(f"train_hill_r{i + 1}", value)) for i, value in enumerate([1.2, 1.0, 0.8, 1.0, 1.0, 1.0])],
        barlat_alphas=[float(state.get(f"train_barlat_a{i + 1}", 1.0)) for i in range(8)],
        barlat_exponent=float(state.get("train_barlat_exponent", 8.0)),
        hyperelastic_c10=float(state.get("train_hyperelastic_c10", 0.5)),
        hyperelastic_c01=float(state.get("train_hyperelastic_c01", 0.2)),
        hyperelastic_d1=float(state.get("train_hyperelastic_d1", 0.0)),
        c_value=float(state.get("train_C", 1.0)),
        gamma=float(state.get("train_gamma", 1.0)),
        n_load_cases=int(state.get("train_n_load_cases", 40)),
        n_sequence=int(state.get("train_n_sequence", 4)),
        test_size=int(state.get("train_test_size", 80)),
        plot_mesh=int(state.get("train_plot_mesh", 50)),
        calculate_curves=bool(state.get("train_calculate_curves", False)),
        notes=notes,
    ).normalized()


def _write_presets(presets: dict[str, MaterialPreset]) -> None:
    LIBRARY_DIR.mkdir(parents=True, exist_ok=True)
    payload = {
        "version": 1,
        "updated_at": datetime.now().isoformat(timespec="seconds"),
        "materials": [asdict(preset.normalized()) for preset in presets.values()],
    }
    MATERIALS_FILE.write_text(json.dumps(payload, indent=2), encoding="utf-8")
