"""Tests for natural language task parser."""
from material_ai_workbench.nl_tasks import parse_natural_language_task


def test_parse_chinese_j2():
    r = parse_natural_language_task("J2 材料 sy=80 E=210000")
    assert r.material is not None
    assert r.material.material_type == "j2"
    assert r.material.yield_strength == 80
    assert r.material.youngs_modulus == 210000


def test_parse_chinese_j2_alt():
    r = parse_natural_language_task("用J2模型，屈服强度80MPa，弹性模量210GPa")
    assert r.material is not None
    assert r.material.material_type == "j2"


def test_parse_english_hill():
    r = parse_natural_language_task("Hill material with sy=120, E=70000, C=2.0")
    assert r.material is not None
    assert r.material.material_type == "hill"
    assert r.material.yield_strength == 120
    assert r.ml.c_value == 2.0


def test_parse_with_abaqus_keyword():
    r = parse_natural_language_task("J2 sy=100 UMAT check max_load_cases=3")
    assert r.material is not None
    assert r.material.material_type == "j2"
    assert r.abaqus.run_check is True


def test_parse_unknown_material():
    r = parse_natural_language_task("do something with no parameters")
    assert r is not None  # should not crash
    assert len(r.warnings) > 0 or r.material is None
