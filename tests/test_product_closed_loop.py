from __future__ import annotations

from material_ai_workbench.composite_workflow import CompositePlateConfig
from material_ai_workbench.run_product_closed_loop import run_product_closed_loop


def test_product_closed_loop_smoke_runs_without_abaqus(tmp_path) -> None:
    config = CompositePlateConfig(
        name="unit_product_smoke",
        output_dir=tmp_path,
        fiber_volume_fraction=0.45,
        interface_thickness_ratio=0.35,
        length=60.0,
        width=20.0,
        thickness=1.5,
        hole_radius=2.0,
        mesh_size=2.0,
        micro_fiber_count=4,
        micro_nx=2,
        micro_ny=12,
        micro_nz=12,
        n_preview_fibers=4,
        run_abaqus=False,
    )

    summary = run_product_closed_loop(config)

    assert summary["capability_status"]["micro_rve"] == "completed"
    assert summary["capability_status"]["abaqus_plate_solve"] == "generated"
    assert summary["acceptance"]["vf_within_3_percent"] is True
    assert summary["acceptance"]["pbc_job_count"] == 6
    assert summary["paths"]["product_summary"].endswith("product_closed_loop_summary.json")
    assert summary["paths"]["product_report"].endswith("product_closed_loop_report.md")
