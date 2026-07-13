import csv
from pathlib import Path

from material_ai_workbench.data_import import (
    import_csv_dataset,
    imported_curve_to_config,
    validate_imported_curve_with_workbench,
)


def _write_curve(path: Path, rows: list[tuple[float, float]]) -> None:
    with path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.writer(handle)
        writer.writerow(["strain", "stress_mpa"])
        writer.writerows(rows)


def test_import_warns_for_non_monotonic_strain(tmp_path):
    source = tmp_path / "bad_curve.csv"
    _write_curve(source, [(0.0, 0.0), (0.002, 200.0), (0.001, 100.0), (0.003, 220.0), (0.004, 230.0)])

    result = import_csv_dataset(source_path=source, material_name="bad", imports_root=tmp_path / "imports")

    assert any("monotonic" in warning for warning in result.warnings)
    assert "Validation" in result.report_path.read_text(encoding="utf-8")


def test_import_warns_for_percent_scale_strain(tmp_path):
    source = tmp_path / "percent_curve.csv"
    _write_curve(source, [(0.0, 0.0), (0.5, 100.0), (1.0, 150.0), (2.0, 180.0), (5.0, 220.0)])

    result = import_csv_dataset(source_path=source, material_name="percent", imports_root=tmp_path / "imports")

    assert any("percent" in warning for warning in result.warnings)


def test_imported_curve_to_config_estimates_elastic_properties(tmp_path):
    source = tmp_path / "clean_curve.csv"
    rows = [
        (0.0, 0.0),
        (0.00025, 50.0),
        (0.0005, 100.0),
        (0.001, 200.0),
        (0.002, 250.0),
        (0.003, 260.0),
        (0.004, 270.0),
        (0.006, 290.0),
    ]
    _write_curve(source, rows)
    result = import_csv_dataset(source_path=source, material_name="clean", imports_root=tmp_path / "imports")

    config = imported_curve_to_config(result.import_dir, output_dir=tmp_path / "runs")

    assert config is not None
    assert abs(config.youngs_modulus - 200_000.0) / 200_000.0 < 0.1
    assert config.yield_strength > 0
    assert config.calculate_curves is True


def test_imported_curve_validation_runs_workbench_loop(tmp_path):
    source = tmp_path / "validation_curve.csv"
    rows = [
        (0.0, 0.0),
        (0.00025, 50.0),
        (0.0005, 100.0),
        (0.001, 200.0),
        (0.002, 240.0),
        (0.004, 255.0),
        (0.006, 260.0),
    ]
    _write_curve(source, rows)
    result = import_csv_dataset(source_path=source, material_name="validation", imports_root=tmp_path / "imports")

    validation = validate_imported_curve_with_workbench(
        result.import_dir,
        output_dir=tmp_path / "runs",
        n_load_cases=8,
        test_size=20,
    )

    assert validation.workbench_run_dir.exists()
    assert validation.validation_json.exists()
    assert validation.overlay_plot.exists()
    assert validation.report_path.exists()
    assert validation.sample_count >= 3
    assert "Workbench Curve Validation" in result.report_path.read_text(encoding="utf-8")
