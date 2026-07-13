"""Tests for core training pipeline. No Abaqus dependency.

Note: pipeline tests that invoke pyLabFEA's native FEM rendering may crash
with Windows fatal exception 0xc06d007f in certain conda environments.
This is a pyLabFEA DLL issue, not a MaterialAI Workbench bug.
"""
import json
import os
import tempfile
from pathlib import Path

import pytest

from material_ai_workbench.pipeline import WorkbenchConfig, run_material_workbench

# Skip pipeline tests by default in CI/non-interactive environments.
# Set MATERIALAI_RUN_PIPELINE_TESTS=1 to force execution.
_run_pipeline = os.environ.get("MATERIALAI_RUN_PIPELINE_TESTS", "0") == "1"
pipeline_test = pytest.mark.skipif(
    not _run_pipeline,
    reason="Set MATERIALAI_RUN_PIPELINE_TESTS=1 to run pipeline tests "
           "(requires working pyLabFEA native DLLs)",
)


@pipeline_test
def test_j2_training_creates_all_outputs():
    with tempfile.TemporaryDirectory() as td:
        config = WorkbenchConfig(
            material_type="j2", name="test_j2", output_dir=Path(td),
            n_load_cases=10, n_sequence=2, calculate_curves=False,
            test_size=20, random_seed=1,
        )
        result = run_material_workbench(config)
        assert result.summary_path.exists()
        assert result.report_path.exists()
        assert result.yield_locus_png.exists()
        assert result.umat_csv.exists()
        assert result.umat_meta_json.exists()
        assert result.support_vectors > 0
        assert len(result.metrics) == 6


@pipeline_test
def test_hill_training_creates_outputs():
    with tempfile.TemporaryDirectory() as td:
        config = WorkbenchConfig(
            material_type="hill", name="test_hill", output_dir=Path(td),
            yield_strength=50.0, n_load_cases=10, n_sequence=2,
            test_size=20, random_seed=2,
        )
        result = run_material_workbench(config)
        assert result.report_path.exists()
        assert result.umat_csv.exists()
        assert result.support_vectors > 0


@pipeline_test
def test_j2_metrics_are_reasonable():
    with tempfile.TemporaryDirectory() as td:
        config = WorkbenchConfig(
            material_type="j2", name="test_metrics", output_dir=Path(td),
            n_load_cases=20, n_sequence=3, random_seed=3,
        )
        result = run_material_workbench(config)
        assert result.metrics["accuracy"] > 0.8


def test_invalid_material_type_raises():
    with tempfile.TemporaryDirectory() as td:
        config = WorkbenchConfig(
            material_type="unsupported_xyz", name="test_fail", output_dir=Path(td),
        )
        try:
            run_material_workbench(config)
            assert False, "Should have raised ValueError"
        except ValueError:
            pass


@pipeline_test
def test_umat_export_contains_support_vectors():
    with tempfile.TemporaryDirectory() as td:
        config = WorkbenchConfig(
            material_type="j2", name="test_sv", output_dir=Path(td),
            n_load_cases=10, n_sequence=2, random_seed=5,
        )
        result = run_material_workbench(config)
        summary = json.loads(result.summary_path.read_text(encoding="utf-8"))
        assert summary["ml_material"]["support_vectors"] > 0
        assert summary["metrics"]["mae"] >= 0
        assert summary["metrics"]["f1"] >= 0
