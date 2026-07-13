import csv

from material_ai_workbench.data_import import import_csv_dataset
from material_ai_workbench.job_queue import JobQueue
from material_ai_workbench.pipeline import WorkbenchConfig, run_material_workbench


def test_hyperelastic_neo_hookean_generates_curves_and_material_card(tmp_path):
    result = run_material_workbench(
        WorkbenchConfig(
            material_type="neo_hookean",
            name="unit_neo",
            output_dir=tmp_path / "runs",
            hyperelastic_c10=0.5,
            hyperelastic_d1=0.0,
            strain_max=0.25,
        )
    )

    assert result.support_vectors == 0
    assert result.stress_strain_csv.exists()
    assert result.umat_csv.exists()
    assert "*Hyperelastic, neo hooke" in result.umat_csv.read_text(encoding="utf-8")
    assert result.metrics["max_uniaxial_stress_mpa"] > 0


def test_percent_warning_is_deduplicated_after_normalization(tmp_path):
    source = tmp_path / "percent_curve.csv"
    with source.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.writer(handle)
        writer.writerow(["strain", "stress_mpa"])
        writer.writerows([(0.0, 0.0), (0.5, 100.0), (1.0, 150.0), (2.0, 180.0), (5.0, 220.0)])

    result = import_csv_dataset(source_path=source, material_name="percent", imports_root=tmp_path / "imports")

    percent_warnings = [warning for warning in result.warnings if "percent" in warning]
    assert len(percent_warnings) == 1


def test_job_queue_empty_name_uses_safe_default(tmp_path):
    queue = JobQueue(queue_file=tmp_path / "queue.json", abaqus_bat=tmp_path / "abaqus.bat")
    job = queue.submit("", tmp_path / "model.inp", tmp_path)

    assert job.name == "abaqus_job"
