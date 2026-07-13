"""Tests for Barlat Yld2000-2D / Yld2004 parameter mapping.

These tests validate the configuration layer ONLY — they do not invoke
pyLabFEA's native FEM/SVC training, so they are safe to run in any environment.
"""
from __future__ import annotations

import pytest

from material_ai_workbench.pipeline import (
    WorkbenchConfig,
    _barlat18_from_yld2000_alphas,
)


class TestBarlatAlphaMapping:
    """Yld2000-2D (8 alphas) → Yld2004 (18 params) transformation."""

    def test_isotropic_alphas_produce_symmetric_output(self):
        """All-1.0 alphas → 18 all-1.0 params (isotropic J2 equivalent)."""
        config = WorkbenchConfig(
            material_type="barlat",
            barlat_alphas=(1.0, 1.0, 1.0, 1.0, 1.0, 1.0, 1.0, 1.0),
        )
        result = _barlat18_from_yld2000_alphas(config)
        assert len(result) == 18
        assert all(abs(v - 1.0) < 1e-9 for v in result), (
            f"Isotropic alphas should map to all-1.0 params, got {result[:6]}..."
        )

    def test_output_length_is_always_18(self):
        config = WorkbenchConfig(
            material_type="barlat",
            barlat_alphas=(0.9, 1.05, 0.85, 1.0, 1.0, 1.0, 0.95, 1.1),
        )
        result = _barlat18_from_yld2000_alphas(config)
        assert len(result) == 18

    def test_shear_alphas_averaged_into_ninth_param(self):
        """a7 and a8 are averaged to create the 9th Yld2004 parameter."""
        config = WorkbenchConfig(
            material_type="barlat",
            barlat_alphas=(1.0, 1.0, 1.0, 1.0, 1.0, 1.0, 0.8, 1.2),
        )
        result = _barlat18_from_yld2000_alphas(config)
        shear = result[8]
        assert abs(shear - 1.0) < 1e-9, f"Expected shear=(0.8+1.2)/2=1.0, got {shear}"

    def test_barlat_coeffs_override_alphas(self):
        config = WorkbenchConfig(
            material_type="barlat",
            barlat_alphas=(1.0, 1.0, 1.0, 1.0, 1.0, 1.0, 1.0, 1.0),
            barlat_coeffs=(0.9, 1.0, 0.8, 1.0, 1.0, 1.0, 0.9, 1.1),
        )
        result = _barlat18_from_yld2000_alphas(config)
        assert abs(result[0] - 0.9) < 1e-9, "barlat_coeffs should override barlat_alphas"

    def test_second_half_is_swapped_first_half(self):
        """The 18-param output is [first_9] + [swapped_first_9]."""
        config = WorkbenchConfig(
            material_type="barlat",
            barlat_alphas=(0.9, 1.0, 0.8, 1.0, 1.0, 1.0, 0.95, 1.1),
        )
        result = _barlat18_from_yld2000_alphas(config)
        first = result[:9]
        second = result[9:]
        assert second[0] == first[1]  # a2
        assert second[1] == first[0]  # a1
        assert second[2] == first[3]  # a4
        assert second[3] == first[2]  # a3


class TestBarlatValidation:
    def test_wrong_count_raises(self):
        config = WorkbenchConfig(
            material_type="barlat",
            barlat_alphas=(1.0, 1.0, 1.0),  # only 3
        )
        with pytest.raises(ValueError, match="exactly 8"):
            _barlat18_from_yld2000_alphas(config)

    def test_negative_alphas_raise(self):
        config = WorkbenchConfig(
            material_type="barlat",
            barlat_alphas=(1.0, -1.0, 1.0, 1.0, 1.0, 1.0, 1.0, 1.0),
        )
        with pytest.raises(ValueError, match="positive"):
            _barlat18_from_yld2000_alphas(config)

    def test_zero_alpha_raises(self):
        config = WorkbenchConfig(
            material_type="barlat",
            barlat_alphas=(1.0, 0.0, 1.0, 1.0, 1.0, 1.0, 1.0, 1.0),
        )
        with pytest.raises(ValueError, match="positive"):
            _barlat18_from_yld2000_alphas(config)


class TestBarlatConfig:
    def test_barlat_config_defaults(self):
        config = WorkbenchConfig(material_type="barlat")
        assert config.barlat_exponent == 8.0
        assert len(config.barlat_alphas) == 8
        assert all(v == 1.0 for v in config.barlat_alphas)

    def test_barlat_config_name_default(self):
        config = WorkbenchConfig(material_type="barlat", name=None)
        assert config.material_type == "barlat"
        assert config.name is None
