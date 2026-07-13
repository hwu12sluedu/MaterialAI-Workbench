import csv

from material_ai_workbench.composite_workflow import (
    CompositePlateConfig,
    generate_fiber_layout,
    load_composite_manifest,
    run_composite_plate_workflow,
)


def test_composite_workflow_generates_three_phase_rve_and_ml_inputs(tmp_path):
    config = CompositePlateConfig(
        name="unit_composite",
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

    result = run_composite_plate_workflow(config)

    assert result.micro_rve_inp_path.exists()
    assert result.micro_phase_map_path.exists()
    assert result.micro_rve_layout_path.exists()
    assert result.micro_pbc_plan_path.exists()
    assert result.micro_pbc_run_script_path.exists()
    assert result.micro_pbc_postprocess_script_path.exists()
    assert result.effective_properties_path.exists()
    assert result.material_card_path.exists()
    assert result.abaqus_script_path.exists()
    assert result.dataset_csv.exists()
    assert result.report_path.exists()

    inp_text = result.micro_rve_inp_path.read_text(encoding="utf-8")
    assert "FIBER_PHASE" in inp_text
    assert "INTERFACE_PHASE" in inp_text
    assert "MATRIX_PHASE" in inp_text
    assert "C3D8R" in inp_text
    assert "Micro_Uniaxial_X" in inp_text

    pbc_jobs = sorted(result.micro_pbc_job_dir.glob("micro_rve_pbc_*.inp"))
    assert len(pbc_jobs) == 6
    pbc_text = pbc_jobs[0].read_text(encoding="utf-8")
    assert "XMAX_FACE" in pbc_text
    assert "*Boundary" in pbc_text
    assert "S, E" in pbc_text
    assert "PBC_" in pbc_text

    with result.micro_phase_map_path.open("r", encoding="utf-8") as handle:
        rows = list(csv.DictReader(handle))
    phases = {row["phase"] for row in rows}
    assert {"fiber", "interface", "matrix"}.issubset(phases)
    assert {"element_id", "ix", "iy", "iz", "phase_code", "phase"}.issubset(rows[0])

    manifest = load_composite_manifest(result.run_dir)
    assert manifest["paths"]["micro_phase_map"].endswith("phase_map.csv")
    assert len(manifest["paths"]["micro_pbc_jobs"]) == 6
    assert manifest["pylabfea_material_summary"]["source"] == "pylabfea.Material.elasticity"
    assert manifest["microstructure_metrics"]["micro_rve_interface_elements"] > 0
    assert abs(manifest["microstructure_metrics"]["actual_vf"] - config.fiber_volume_fraction) <= 0.03
    assert abs(
        manifest["microstructure_metrics"]["actual_vf"]
        - manifest["microstructure_metrics"]["micro_rve_fiber_fraction_voxel"]
    ) <= 0.02
    assert manifest["workflow"] == "composite_micro_to_macro_plate_hole"

    with result.dataset_csv.open("r", encoding="utf-8") as handle:
        dataset_rows = list(csv.DictReader(handle))
    assert dataset_rows[0]["case_type"] == "composite_plate_with_hole_3d"
    assert "actual_vf" in dataset_rows[0]
    assert "micro_rve_interface_elements" in dataset_rows[0]


def test_fiber_layout_calibration_handles_discrete_voxel_jumps():
    config = CompositePlateConfig(
        fiber_volume_fraction=0.55,
        micro_fiber_count=9,
        micro_nx=3,
        micro_ny=12,
        micro_nz=12,
    )

    layout = generate_fiber_layout(config)

    assert abs(layout["actual_vf"] - config.fiber_volume_fraction) <= 0.03
