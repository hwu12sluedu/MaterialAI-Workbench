"""Tests for material preset library."""
from material_ai_workbench.material_library import load_material_presets, preset_to_workbench_config


def test_default_presets_exist():
    presets = load_material_presets()
    assert isinstance(presets, dict)
    assert "Demo_J2_60MPa" in presets
    assert "Demo_Hill_sheet" in presets


def test_preset_fields():
    p = load_material_presets()["Demo_J2_60MPa"]
    assert p.material_type == "j2"
    assert p.youngs_modulus == 200000.0
    assert p.poisson_ratio == 0.3
    assert p.yield_strength == 60.0
    assert p.c_value == 1.0
    assert p.gamma == 1.0


def test_preset_to_workbench_config_round_trips_core_fields(tmp_path):
    p = load_material_presets()["Demo_MooneyRivlin_rubber"]
    config = preset_to_workbench_config(p, output_dir=tmp_path, name_suffix="_verify", calculate_curves=True)

    assert config.material_type == "mooney_rivlin"
    assert config.name.endswith("_verify")
    assert config.output_dir == tmp_path
    assert config.hyperelastic_c10 == p.hyperelastic_c10
    assert config.hyperelastic_c01 == p.hyperelastic_c01
    assert config.calculate_curves is True
