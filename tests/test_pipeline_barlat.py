import os
from pathlib import Path

import numpy as np
import pytest
import pylabfea as FE

from material_ai_workbench.pipeline import WorkbenchConfig, _barlat18_from_yld2000_alphas, run_material_workbench


def test_barlat_alphas_expand_to_pylabfea_18_parameter_form():
    config = WorkbenchConfig(
        material_type="barlat",
        barlat_alphas=(0.9, 1.0, 0.8, 1.0, 1.0, 1.0, 0.9, 1.1),
    )

    values = _barlat18_from_yld2000_alphas(config)

    assert len(values) == 18
    assert values[0] == 0.9
    assert values[9] == 1.0
    assert all(value > 0 for value in values)


def test_isotropic_barlat_is_near_j2_on_representative_sheet_directions():
    sy = 100.0
    barlat = _barlat_material(WorkbenchConfig(material_type="barlat", yield_strength=sy), sy=sy)
    j2 = _j2_material(sy=sy)
    directions = [
        np.array([1.0, 0.0, 0.0, 0.0, 0.0, 0.0]),
        np.array([0.0, 1.0, 0.0, 0.0, 0.0, 0.0]),
        np.array([2.0**-0.5, 2.0**-0.5, 0.0, 0.0, 0.0, 0.0]),
    ]

    errors = []
    for direction in directions:
        j2_seq_at_unit = float(j2.calc_yf(direction) + sy)
        scaled = direction * (sy / j2_seq_at_unit)
        errors.append(abs(float(barlat.calc_yf(scaled))) / sy)

    assert max(errors) < 0.05


def test_anisotropic_barlat_alphas_create_directional_response():
    sy = 100.0
    config = WorkbenchConfig(
        material_type="barlat",
        yield_strength=sy,
        barlat_alphas=(0.7, 1.3, 0.9, 1.1, 1.0, 1.0, 0.8, 1.2),
    )
    barlat = _barlat_material(config, sy=sy)

    yf_x = float(barlat.calc_yf(np.array([sy, 0.0, 0.0, 0.0, 0.0, 0.0])))
    yf_y = float(barlat.calc_yf(np.array([0.0, sy, 0.0, 0.0, 0.0, 0.0])))

    assert abs(yf_x - yf_y) > sy * 0.05


@pytest.mark.skipif(
    os.environ.get("MATERIALAI_RUN_PIPELINE_TESTS", "0") != "1",
    reason="Set MATERIALAI_RUN_PIPELINE_TESTS=1 to run pyLabFEA training smoke tests.",
)
def test_barlat_training_creates_umat_export(tmp_path: Path):
    config = WorkbenchConfig(
        material_type="barlat",
        name="test_barlat",
        output_dir=tmp_path,
        yield_strength=150.0,
        youngs_modulus=70_000.0,
        poisson_ratio=0.33,
        barlat_exponent=8.0,
        barlat_alphas=(0.9, 1.0, 0.8, 1.0, 1.0, 1.0, 0.9, 1.1),
        n_load_cases=8,
        n_sequence=2,
        test_size=20,
        plot_mesh=20,
    )

    result = run_material_workbench(config)

    assert result.umat_csv.exists()
    assert result.umat_meta_json.exists()
    assert result.support_vectors > 0


def _barlat_material(config: WorkbenchConfig, *, sy: float) -> FE.Material:
    material = FE.Material(name="barlat_test", num=1)
    material.elasticity(E=config.youngs_modulus, nu=config.poisson_ratio)
    material.plasticity(
        sy=sy,
        sdim=6,
        barlat=_barlat18_from_yld2000_alphas(config),
        barlat_exp=int(config.barlat_exponent),
    )
    return material


def _j2_material(*, sy: float) -> FE.Material:
    material = FE.Material(name="j2_test", num=2)
    material.elasticity(E=200_000.0, nu=0.3)
    material.plasticity(sy=sy, sdim=6)
    return material
