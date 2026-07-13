import csv
import json
from dataclasses import asdict

import numpy as np
import pytest

from material_ai_workbench.composite_workflow import (
    CompositePlateConfig,
    generate_fiber_layout,
    run_composite_plate_workflow,
)
from material_ai_workbench.rve_visualization import (
    build_rve_phase_grid,
    cylinder_mesh_between_points,
    plot_oriented_fiber_rve_3d,
)


def _oriented_config(tmp_path=None) -> CompositePlateConfig:
    kwargs = {
        "name": "oriented_rve_test",
        "fiber_volume_fraction": 0.42,
        "micro_fiber_count": 10,
        "micro_nx": 6,
        "micro_ny": 12,
        "micro_nz": 12,
        "fiber_orientation_theta_deg": 28.0,
        "fiber_orientation_phi_deg": 3.0,
        "fiber_orientation_spread_deg": 6.0,
        "fiber_length_normalized": 1.15,
        "random_seed": 19,
    }
    if tmp_path is not None:
        kwargs["output_dir"] = tmp_path
    return CompositePlateConfig(**kwargs)


def _elset_ids(inp_text: str, name: str) -> list[int]:
    lines = inp_text.splitlines()
    marker = f"*Elset, elset={name}".lower()
    start = next(i for i, line in enumerate(lines) if line.strip().lower() == marker)
    values: list[int] = []
    for line in lines[start + 1 :]:
        if line.startswith("*"):
            break
        values.extend(int(item.strip()) for item in line.split(",") if item.strip())
    return values


def test_oriented_layout_is_reproducible_and_json_ready():
    config = _oriented_config()
    first = generate_fiber_layout(config)
    second = generate_fiber_layout(config)

    assert first == second
    assert len(first["fibers"]) == config.micro_fiber_count
    assert any(abs(fiber["theta_deg"]) > 1.0 for fiber in first["fibers"])
    assert abs(first["actual_vf"] - config.fiber_volume_fraction) <= 0.03
    assert sum(first["orientation_tensor"][key] for key in ("a11", "a22", "a33")) == pytest.approx(1.0)
    json.dumps({"config": asdict(config), "layout": first}, default=str)


def test_phase_grid_uses_the_same_oriented_layout():
    result = build_rve_phase_grid(_oriented_config())
    phase_grid = result["phase_grid"]
    layout = result["layout"]

    assert phase_grid.shape == (6, 12, 12)
    assert set(np.unique(phase_grid)).issubset({0, 1, 2})
    assert np.mean(phase_grid == 2) == pytest.approx(layout["actual_vf"])
    assert np.mean(phase_grid == 1) == pytest.approx(layout["interface_vf"])


def test_3d_renderer_contains_fiber_interface_matrix_and_bounds():
    pytest.importorskip("plotly")
    fig = plot_oriented_fiber_rve_3d(config=_oriented_config())
    trace_names = {trace.name for trace in fig.data}
    trace_types = [trace.type for trace in fig.data]

    assert {"Fiber", "Interface", "Matrix", "RVE bounds"}.issubset(trace_names)
    assert trace_types.count("mesh3d") >= 3
    assert "scatter3d" in trace_types


def test_cylinder_mesh_is_finite_and_closed():
    mesh = cylinder_mesh_between_points((0.1, 0.2, 0.3), (0.9, 0.7, 0.6), 0.04)

    assert len(mesh["x"]) == 34
    assert len(mesh["i"]) == 64
    assert all(np.isfinite(mesh[key]).all() for key in ("x", "y", "z"))


def test_workflow_keeps_preview_phase_map_pbc_and_dataset_in_sync(tmp_path):
    config = _oriented_config(tmp_path)
    result = run_composite_plate_workflow(config)
    layout = json.loads(result.micro_rve_layout_path.read_text(encoding="utf-8"))

    with result.micro_phase_map_path.open(encoding="utf-8", newline="") as handle:
        phase_rows = list(csv.DictReader(handle))
    fiber_count = sum(row["phase"] == "fiber" for row in phase_rows)

    pbc_path = result.micro_pbc_job_dir / "micro_rve_pbc_exx.inp"
    pbc_fiber_ids = _elset_ids(pbc_path.read_text(encoding="utf-8"), "FIBER_PHASE")
    with result.dataset_csv.open(encoding="utf-8", newline="") as handle:
        dataset_row = next(csv.DictReader(handle))

    assert result.microstructure_png.exists()
    assert fiber_count == len(pbc_fiber_ids)
    assert fiber_count / len(phase_rows) == pytest.approx(layout["actual_vf"])
    assert float(dataset_row["fiber_orientation_theta_deg"]) == config.fiber_orientation_theta_deg
    assert "orientation_a11" in dataset_row
