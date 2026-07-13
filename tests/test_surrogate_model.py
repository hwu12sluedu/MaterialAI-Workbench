from __future__ import annotations

import csv
import json
import os
from pathlib import Path

from material_ai_workbench.surrogate_model import (
    compare_all_models,
    list_dataset_exports,
    surrogate_comparison_rows,
    train_surrogate_from_dataset,
)


def _write_case_dataset(dataset_dir: Path) -> Path:
    dataset_dir.mkdir(parents=True)
    dataset_csv = dataset_dir / "case_dataset.csv"
    fieldnames = [
        "case_id",
        "title",
        "source_folder",
        "status",
        "tags",
        "material_type",
        "case_type",
        "geometry_length",
        "geometry_width",
        "geometry_thickness",
        "geometry_hole_radius",
        "fiber_volume_fraction",
        "loading_applied_strain",
        "loading_applied_stress",
        "loading_type",
        "mesh_node_count",
        "mesh_element_count",
        "yield_strength",
        "youngs_modulus",
        "poisson_ratio",
        "file_count",
        "model_file_count",
        "result_file_count",
        "data_file_count",
        "inp_node_count",
        "inp_element_count",
        "inp_element_types",
        "materials",
        "log_warning_count",
        "log_error_count",
        "odb_extraction_count",
        "frame_series_count",
        "latest_frame_series_rows",
        "latest_odb_max_mises",
        "latest_odb_max_peeq",
        "latest_odb_max_displacement",
        "latest_odb_max_reaction_force",
    ]
    rows = []
    for idx in range(6):
        node_count = 100 + idx * 20
        element_count = 60 + idx * 10
        rows.append(
            {
                "case_id": f"case_{idx}",
                "title": f"unit case {idx}",
                "source_folder": f"D:/cases/case_{idx}",
                "status": "success",
                "tags": "Abaqus;steel",
                "material_type": "j2",
                "case_type": "metal",
                "geometry_length": 10.0,
                "geometry_width": 4.0,
                "geometry_thickness": 1.0,
                "geometry_hole_radius": 0.5,
                "fiber_volume_fraction": "",
                "loading_applied_strain": 0.02,
                "loading_applied_stress": "",
                "loading_type": "tension",
                "mesh_node_count": node_count,
                "mesh_element_count": element_count,
                "yield_strength": 50.0 + idx * 5,
                "youngs_modulus": 200000.0,
                "poisson_ratio": 0.3,
                "file_count": 4 + idx,
                "model_file_count": 1,
                "result_file_count": 1,
                "data_file_count": 2,
                "inp_node_count": node_count,
                "inp_element_count": element_count,
                "inp_element_types": "C3D8R",
                "materials": "Steel",
                "log_warning_count": idx % 2,
                "log_error_count": 0,
                "odb_extraction_count": 1,
                "frame_series_count": 1,
                "latest_frame_series_rows": 20 + idx,
                "latest_odb_max_mises": 100.0 + node_count * 0.8 + element_count * 0.3,
                "latest_odb_max_peeq": 0.01 * (idx + 1),
                "latest_odb_max_displacement": 0.05 * (idx + 1),
                "latest_odb_max_reaction_force": 10.0 * (idx + 1),
            }
        )

    with dataset_csv.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(rows)
    return dataset_csv


def test_train_surrogate_from_case_dataset_writes_artifacts(tmp_path) -> None:
    dataset_dir = tmp_path / "datasets" / "unit_dataset"
    _write_case_dataset(dataset_dir)

    run = train_surrogate_from_dataset(
        dataset_dir,
        target_column="latest_odb_max_mises",
        model_kind="random_forest",
        output_root=tmp_path / "surrogates",
        random_state=7,
    )

    assert run.model_path.exists()
    assert run.metrics_path.exists()
    assert run.predictions_csv.exists()
    assert run.features_csv.exists()
    assert run.targets_csv.exists()
    assert run.plot_path.exists()
    assert run.report_path.exists()
    assert run.metrics["target_column"] == "latest_odb_max_mises"
    assert run.metrics["sample_count"] == 6
    assert run.metrics["model_kind"] == "random_forest"
    assert run.metrics["evaluation_mode"] == "holdout"
    assert run.metrics["cv_r2_mean"] is not None

    metrics = json.loads(run.metrics_path.read_text(encoding="utf-8"))
    assert metrics["feature_count"] > 0
    with run.features_csv.open("r", encoding="utf-8", newline="") as handle:
        feature_rows = list(csv.DictReader(handle))
    assert feature_rows[0]["yield_strength"] == "50.0"
    with run.predictions_csv.open("r", encoding="utf-8", newline="") as handle:
        rows = list(csv.DictReader(handle))
    assert len(rows) == 6
    assert any(row["evaluated"] == "True" for row in rows)


def test_list_dataset_exports_returns_newest_first(tmp_path) -> None:
    old_dataset = tmp_path / "old"
    new_dataset = tmp_path / "new"
    _write_case_dataset(old_dataset)
    _write_case_dataset(new_dataset)
    os.utime(old_dataset, (1, 1))
    os.utime(new_dataset, (2, 2))

    exports = list_dataset_exports(tmp_path)

    assert exports[0] == new_dataset
    assert old_dataset in exports


def test_surrogate_comparison_rows_filters_and_sorts(tmp_path) -> None:
    dataset_dir = tmp_path / "datasets" / "unit_dataset"
    dataset_csv = _write_case_dataset(dataset_dir)
    run_a = tmp_path / "surrogates" / "rf"
    run_b = tmp_path / "surrogates" / "mlp"
    run_c = tmp_path / "surrogates" / "other_target"
    for run_dir, model_kind, rmse, target in [
        (run_a, "random_forest", 3.0, "latest_odb_max_mises"),
        (run_b, "mlp", 1.5, "latest_odb_max_mises"),
        (run_c, "random_forest", 0.2, "latest_odb_max_peeq"),
    ]:
        run_dir.mkdir(parents=True)
        (run_dir / "surrogate_metrics.json").write_text(
            json.dumps(
                {
                    "dataset_csv": str(dataset_csv),
                    "target_column": target,
                    "model_kind": model_kind,
                    "sample_count": 6,
                    "evaluation_mode": "holdout",
                    "mae": rmse / 2,
                    "rmse": rmse,
                    "r2": 0.5,
                }
            ),
            encoding="utf-8",
        )

    rows = surrogate_comparison_rows([run_a, run_b, run_c], dataset_dir=dataset_dir, target_column="latest_odb_max_mises")

    assert [row["model_kind"] for row in rows] == ["mlp", "random_forest"]
    assert rows[0]["rmse"] == 1.5
    assert rows[0]["dataset_dir"] == str(dataset_dir.resolve())


def test_compare_all_models_trains_rf_mlp_and_gbr(tmp_path) -> None:
    dataset_dir = tmp_path / "datasets" / "unit_dataset"
    _write_case_dataset(dataset_dir)

    rows = compare_all_models(
        dataset_dir,
        target_column="latest_odb_max_mises",
        output_root=tmp_path / "surrogates",
        random_state=11,
    )

    assert {row["model_kind"] for row in rows} == {"random_forest", "mlp", "gbr"}
    assert all(row["error"] is None for row in rows)
    assert all(row["run_dir"] for row in rows)
    assert all(row["cv_r2_mean"] is not None for row in rows)
