from __future__ import annotations

import json
from datetime import datetime
from pathlib import Path

from material_ai_workbench.case_library import CaseSummary, save_case_summary
from material_ai_workbench.closed_loop_report import generate_closed_loop_report, list_closed_loop_reports


def _write_json(path: Path, data: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(data, indent=2, ensure_ascii=False), encoding="utf-8")


def test_generate_closed_loop_report_links_all_artifacts(tmp_path) -> None:
    run_dir = tmp_path / "runs" / "demo_run"
    _write_json(
        run_dir / "summary.json",
        {
            "config": {"material_type": "j2"},
            "ml_material": {"name": "demo_j2", "support_vectors": 12},
            "metrics": {"accuracy": 0.98, "f1": 0.97},
        },
    )
    _write_json(
        run_dir / "abaqus_verification" / "bridge_summary.json",
        {
            "status": "completed",
            "result_stats": {"row_count": 20, "max_mises_mpa": 123.4, "max_peeq": 0.02},
        },
    )

    now = datetime.now().isoformat(timespec="seconds")
    case_dir = tmp_path / "cases" / "demo_case"
    case = CaseSummary(
        case_id="demo_case",
        title="闭环测试案例",
        description="unit test",
        tags=["closed-loop"],
        status="success",
        source_folder=str(tmp_path / "source"),
        created_at=now,
        updated_at=now,
        case_dir=str(case_dir),
        files=[],
        file_counts={},
        total_size_bytes=0,
        key_files={},
        inp_features={"summary": {"estimated_node_count": 2}},
        result_features={"summary": {"max_mises": 120.0}},
        odb_extractions=[{"aggregate": {"max_mises": 123.4}}],
        odb_frame_series=[{"row_count": 10, "csv_path": str(tmp_path / "series.csv")}],
    )
    save_case_summary(case)

    dataset_dir = tmp_path / "datasets" / "dataset"
    _write_json(
        dataset_dir / "dataset_manifest.json",
        {
            "case_count": 1,
            "row_count": 1,
            "frame_series_count": 1,
            "dataset_csv": str(dataset_dir / "case_dataset.csv"),
            "frame_series_index_csv": str(dataset_dir / "frame_series_index.csv"),
        },
    )

    surrogate_dir = tmp_path / "surrogates" / "surrogate"
    _write_json(
        surrogate_dir / "surrogate_metrics.json",
        {
            "dataset_csv": str(dataset_dir / "case_dataset.csv"),
            "target_column": "latest_odb_max_mises",
            "model_kind": "random_forest",
            "sample_count": 1,
            "evaluation_mode": "training_set_only",
            "mae": 0.0,
            "rmse": 0.0,
            "quality_note": "unit test",
        },
    )

    report = generate_closed_loop_report(
        material_run=run_dir,
        case_dir=case_dir,
        dataset_dir=dataset_dir,
        surrogate_run=surrogate_dir,
        output_root=tmp_path / "closed_loop_reports",
    )

    assert report.report_path.exists()
    assert report.manifest_path.exists()
    assert report.manifest["completion"]["status"] == "complete"
    assert report.manifest["completion"]["complete_steps"] == 7
    assert report.manifest["surrogate_model"]["target_column"] == "latest_odb_max_mises"
    assert report.manifest["surrogate_comparison"][0]["model_kind"] == "random_forest"
    assert "材料训练 -> Abaqus 验算" in report.report_path.read_text(encoding="utf-8")

    reports = list_closed_loop_reports(tmp_path / "closed_loop_reports")
    assert reports == [report.report_dir]


def test_generate_closed_loop_report_can_resolve_batch_plan(tmp_path) -> None:
    run_dir = tmp_path / "batch_runs" / "sample_001"
    _write_json(
        run_dir / "summary.json",
        {
            "config": {"material_type": "j2"},
            "ml_material": {"name": "batch_j2", "support_vectors": 8},
            "metrics": {"accuracy": 0.9, "f1": 0.8},
        },
    )
    _write_json(
        run_dir / "abaqus_verification" / "bridge_summary.json",
        {
            "status": "completed",
            "result_stats": {"row_count": 24, "max_mises_mpa": 88.0, "max_peeq": 0.01},
        },
    )

    now = datetime.now().isoformat(timespec="seconds")
    case_dir = tmp_path / "cases" / "batch_case"
    case = CaseSummary(
        case_id="batch_case",
        title="batch case",
        description="unit test",
        tags=["batch"],
        status="success",
        source_folder=str(run_dir / "abaqus_verification"),
        created_at=now,
        updated_at=now,
        case_dir=str(case_dir),
        files=[],
        odb_extractions=[{"aggregate": {"max_mises": 88.0}}],
        odb_frame_series=[{"row_count": 12, "csv_path": str(tmp_path / "series.csv")}],
    )
    save_case_summary(case)

    dataset_dir = tmp_path / "datasets" / "batch_dataset"
    _write_json(
        dataset_dir / "dataset_manifest.json",
        {
            "case_count": 1,
            "row_count": 1,
            "frame_series_count": 1,
            "dataset_csv": str(dataset_dir / "case_dataset.csv"),
            "frame_series_index_csv": str(dataset_dir / "frame_series_index.csv"),
        },
    )
    surrogate_dir = tmp_path / "surrogates" / "batch_surrogate"
    _write_json(
        surrogate_dir / "surrogate_metrics.json",
        {
            "dataset_csv": str(dataset_dir / "case_dataset.csv"),
            "target_column": "latest_odb_max_mises",
            "model_kind": "random_forest",
            "sample_count": 1,
            "evaluation_mode": "training_set_only",
        },
    )
    plan_dir = tmp_path / "batches" / "batch_plan"
    _write_json(
        plan_dir / "batch_plan.json",
        {
            "name": "batch_plan",
            "samples": [
                {
                    "sample_id": "001",
                    "status": "postprocessed",
                    "run_dir": str(run_dir),
                    "case_dir": str(case_dir),
                    "abaqus_status": "completed",
                    "postprocess_status": "completed",
                    "yield_strength": 50.0,
                    "result_stats": {"max_mises_mpa": 88.0},
                }
            ],
            "outputs": {
                "dataset_dir": str(dataset_dir),
                "surrogate_run": str(surrogate_dir),
            },
        },
    )

    report = generate_closed_loop_report(batch_plan=plan_dir, output_root=tmp_path / "closed_loop_reports")

    assert report.manifest["completion"]["complete_steps"] == 8
    assert report.manifest["batch_plan"]["sample_count"] == 1
    assert report.manifest["surrogate_comparison"][0]["model_kind"] == "random_forest"
    assert report.manifest["paths"]["batch_plan"] == str(plan_dir)
    assert "001" in report.report_path.read_text(encoding="utf-8")
