from __future__ import annotations

import csv
import json
from pathlib import Path

from material_ai_workbench.case_library import (
    append_odb_extraction,
    append_odb_frame_series,
    filter_cases,
    infer_case_type,
    scan_case_folder,
)
from material_ai_workbench.dataset_export import export_case_dataset

SAMPLE_INP = """*Heading
*Node
1, 0., 0., 0.
2, 1., 0., 0.
*Element, type=T3D2
1, 1,2
*Material, name=Steel
*Elastic
210000., 0.3
*Step, name=Load
*Static
*Boundary
1, 1, 3
*Cload
2, 1, 1.
*End Step
"""


def test_export_case_dataset_builds_ml_index_files(tmp_path) -> None:
    source = tmp_path / "case_source"
    source.mkdir()
    (source / "model.inp").write_text(SAMPLE_INP, encoding="utf-8")
    (source / "job.odb").write_text("placeholder", encoding="utf-8")
    cases_root = tmp_path / "cases"
    summary = scan_case_folder(
        source,
        title="dataset case",
        tags=["J2", "ODB"],
        cases_root=cases_root,
        parameters={"material_type": "j2", "yield_strength": 55.0},
    )
    append_odb_extraction(
        summary,
        {
            "created_at": "2026-07-03T08:00:00",
            "odb_name": "job.odb",
            "odb_path": str(source / "job.odb"),
            "aggregate": {
                "max_mises": 100.0,
                "max_peeq": 0.12,
                "max_displacement": 0.5,
                "max_reaction_force": 10.0,
            },
            "report_path": str(tmp_path / "report.md"),
        },
    )
    append_odb_frame_series(
        summary,
        {
            "created_at": "2026-07-03T08:01:00",
            "odb_name": "job.odb",
            "odb_path": str(source / "job.odb"),
            "fields_requested": ["S", "U"],
            "regions_requested": ["FIXED"],
            "regions_found": [
                {"name": "FIXED", "kind": "node_set", "scope": "assembly"}
            ],
            "row_count": 20,
            "step_count": 1,
            "csv_path": str(tmp_path / "series.csv"),
            "json_path": str(tmp_path / "series.json"),
            "report_path": str(tmp_path / "series.md"),
        },
    )

    export = export_case_dataset(
        cases_root=cases_root, output_root=tmp_path / "datasets", name="unit"
    )

    assert export.case_count == 1
    assert export.row_count == 1
    assert export.frame_series_count == 1
    with export.dataset_csv.open("r", encoding="utf-8", newline="") as handle:
        rows = list(csv.DictReader(handle))
    assert rows[0]["case_id"] == summary.case_id
    assert rows[0]["material_type"] == "j2"
    assert rows[0]["case_type"] == "metal"
    assert rows[0]["mesh_node_count"] == "2"
    assert rows[0]["mesh_element_count"] == "1"
    assert rows[0]["yield_strength"] == "55.0"
    assert rows[0]["latest_odb_max_mises"] == "100.0"
    assert rows[0]["abaqus_max_mises"] == "100.0"
    assert rows[0]["latest_frame_series_rows"] == "20"
    with export.frame_series_index_csv.open(
        "r", encoding="utf-8", newline=""
    ) as handle:
        series_rows = list(csv.DictReader(handle))
    assert series_rows[0]["fields"] == "S;U"
    assert series_rows[0]["regions_requested"] == "FIXED"
    assert series_rows[0]["regions_found"] == "FIXED:node_set:assembly"
    assert Path(export.manifest_json).exists()
    assert Path(export.report_md).exists()


def test_export_case_dataset_can_use_selected_case_dirs(tmp_path) -> None:
    cases_root = tmp_path / "cases"
    first_source = tmp_path / "first_case"
    second_source = tmp_path / "second_case"
    first_source.mkdir()
    second_source.mkdir()
    (first_source / "model.inp").write_text(SAMPLE_INP, encoding="utf-8")
    (second_source / "model.inp").write_text(SAMPLE_INP, encoding="utf-8")
    first = scan_case_folder(first_source, title="first", cases_root=cases_root)
    second = scan_case_folder(second_source, title="second", cases_root=cases_root)

    export = export_case_dataset(
        cases_root=cases_root,
        output_root=tmp_path / "datasets",
        name="selected",
        case_dirs=[second.case_dir],
    )

    assert export.case_count == 1
    with export.dataset_csv.open("r", encoding="utf-8", newline="") as handle:
        rows = list(csv.DictReader(handle))
    assert rows[0]["case_id"] == second.case_id
    assert rows[0]["case_id"] != first.case_id


def test_training_only_export_excludes_cases_that_fail_quality_gate(tmp_path) -> None:
    cases_root = tmp_path / "cases"
    solved_source = tmp_path / "solved"
    prepared_source = tmp_path / "prepared"
    solved_source.mkdir()
    prepared_source.mkdir()
    for source in (solved_source, prepared_source):
        (source / "model.inp").write_text(SAMPLE_INP, encoding="utf-8")
    (solved_source / "job.odb").write_text("placeholder", encoding="utf-8")
    (solved_source / "job.sta").write_text(
        "THE ANALYSIS HAS COMPLETED SUCCESSFULLY", encoding="utf-8"
    )
    (solved_source / "results.csv").write_text(
        "frame,S_Mises\n0,10\n1,100\n", encoding="utf-8"
    )
    solved = scan_case_folder(
        solved_source,
        title="solved",
        units="mm-N-s-MPa",
        parameters={"material_type": "j2"},
        cases_root=cases_root,
    )
    prepared = scan_case_folder(
        prepared_source,
        title="prepared",
        cases_root=cases_root,
    )

    export = export_case_dataset(
        cases_root=cases_root,
        output_root=tmp_path / "datasets",
        name="training-only",
        training_only=True,
    )
    manifest = json.loads(export.manifest_json.read_text(encoding="utf-8"))
    with export.dataset_csv.open("r", encoding="utf-8", newline="") as handle:
        rows = list(csv.DictReader(handle))

    assert export.source_case_count == 2
    assert export.case_count == 1
    assert export.skipped_case_count == 1
    assert rows[0]["case_id"] == solved.case_id
    assert rows[0]["training_eligible"] == "True"
    assert rows[0]["execution_state"] == "solved"
    assert manifest["skipped_cases"][0]["case_id"] == prepared.case_id
    assert "units_not_declared" in manifest["skipped_cases"][0]["blocking_reasons"]


def test_filter_cases_supports_export_wizard_criteria(tmp_path) -> None:
    cases_root = tmp_path / "cases"
    metal_source = tmp_path / "metal_case"
    composite_source = tmp_path / "composite_case"
    metal_source.mkdir()
    composite_source.mkdir()
    (metal_source / "model.inp").write_text(SAMPLE_INP, encoding="utf-8")
    (composite_source / "model.inp").write_text(SAMPLE_INP, encoding="utf-8")
    metal = scan_case_folder(
        metal_source,
        title="steel j2 plate",
        tags=["j2", "metal"],
        status="success",
        cases_root=cases_root,
        parameters={"material_type": "j2"},
    )
    composite = scan_case_folder(
        composite_source,
        title="composite rve plate",
        tags=["composite", "rve"],
        status="candidate",
        cases_root=cases_root,
        parameters={"material_type": "composite_ud"},
    )

    assert infer_case_type(metal) == "metal"
    assert infer_case_type(composite) == "composite"

    rows = filter_cases(
        [metal, composite],
        tags="j2",
        statuses=["success"],
        material_types=["j2"],
        case_types=["metal"],
    )
    assert [case.case_id for case in rows] == [metal.case_id]

    rows = filter_cases([metal, composite], tags="rve", case_types=["composite"])
    assert [case.case_id for case in rows] == [composite.case_id]

    metal.parameters = {}
    metal.material_type = "j2"
    rows = filter_cases([metal, composite], material_types=["j2"])
    assert [case.case_id for case in rows] == [metal.case_id]
