from __future__ import annotations

from pathlib import Path

from material_ai_workbench.case_library import (
    append_odb_extraction,
    append_odb_frame_series,
    load_case_summary,
    odb_extraction_table_rows,
    odb_frame_series_table_rows,
    scan_case_folder,
)
from material_ai_workbench.odb_postprocess import frame_series_rows, run_case_odb_extraction, run_case_odb_frame_series_extraction


def test_run_case_odb_extraction_writes_outputs_and_updates_case(tmp_path, monkeypatch) -> None:
    case_dir = tmp_path / "case_source"
    case_dir.mkdir()
    odb_path = case_dir / "job.odb"
    odb_path.write_text("placeholder", encoding="utf-8")
    cases_root = tmp_path / "cases"
    summary = scan_case_folder(case_dir, title="odb case", cases_root=cases_root)

    def fake_extract_odb_field_summary(*args, **kwargs):
        return {
            "path": str(odb_path),
            "frame_mode": "last_frame_per_step",
            "instances": [{"name": "PART-1-1", "nodes": 8, "elements": 1}],
            "node_sets": ["FIXED"],
            "element_sets": ["EALL"],
            "steps": [{"name": "Step-1", "frame_count": 2, "field_stats": []}],
            "field_stats": [
                {
                    "step": "Step-1",
                    "frame_index": 1,
                    "field": "S",
                    "metric": "MISES",
                    "scanned_count": 8,
                    "min": 0.0,
                    "max": 120.0,
                    "mean": 40.0,
                    "max_abs": 120.0,
                    "max_location": {"instance": "PART-1-1", "element_label": "1"},
                    "max_abs_location": {"instance": "PART-1-1", "element_label": "1"},
                    "truncated": False,
                },
                {
                    "step": "Step-1",
                    "frame_index": 1,
                    "field": "PEEQ",
                    "metric": "RAW_OR_MAGNITUDE",
                    "scanned_count": 8,
                    "min": 0.0,
                    "max": 0.12,
                    "mean": 0.03,
                    "max_abs": 0.12,
                    "max_location": {"instance": "PART-1-1", "element_label": "1"},
                    "max_abs_location": {"instance": "PART-1-1", "element_label": "1"},
                    "truncated": False,
                },
                {
                    "step": "Step-1",
                    "frame_index": 1,
                    "field": "U",
                    "metric": "MAGNITUDE",
                    "scanned_count": 8,
                    "min": 0.0,
                    "max": 0.25,
                    "mean": 0.08,
                    "max_abs": 0.25,
                    "max_location": {"instance": "PART-1-1", "node_label": "8"},
                    "max_abs_location": {"instance": "PART-1-1", "node_label": "8"},
                    "truncated": False,
                },
            ],
            "history_outputs": [{"region": "Assembly ASSEMBLY", "output": "ALLIE", "count": 2, "last": 1.0}],
        }

    def fake_display(*args, **kwargs):
        return {"success": True}

    def fake_capture(output_dir, *args, **kwargs):
        path = Path(output_dir) / "viewport.png"
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_bytes(b"fake png")
        return path

    monkeypatch.setattr("material_ai_workbench.odb_postprocess.extract_odb_field_summary", fake_extract_odb_field_summary)
    monkeypatch.setattr("material_ai_workbench.odb_postprocess.display_odb_contour", fake_display)
    monkeypatch.setattr("material_ai_workbench.odb_postprocess.capture_viewport", fake_capture)

    extraction = run_case_odb_extraction(summary, odb_path, fields=["S", "PEEQ", "U"], capture_contour=True)
    append_odb_extraction(summary, extraction)
    loaded = load_case_summary(summary.case_dir)

    assert extraction["aggregate"]["max_mises"] == 120.0
    assert extraction["aggregate"]["max_peeq"] == 0.12
    assert extraction["aggregate"]["max_displacement"] == 0.25
    assert Path(extraction["json_path"]).exists()
    assert Path(extraction["csv_path"]).exists()
    assert Path(extraction["report_path"]).exists()
    assert Path(extraction["viewport_image"]).exists()
    assert len(loaded.odb_extractions) == 1
    rows = odb_extraction_table_rows(loaded)
    assert rows[0]["Max Mises"] == 120.0
    assert rows[0]["Max PEEQ"] == 0.12


def test_run_case_odb_extraction_auto_falls_back_to_batch(tmp_path, monkeypatch) -> None:
    case_dir = tmp_path / "case_source"
    case_dir.mkdir()
    odb_path = case_dir / "job.odb"
    odb_path.write_text("placeholder", encoding="utf-8")
    summary = scan_case_folder(case_dir, title="odb case", cases_root=tmp_path / "cases")

    def fail_mcp(*args, **kwargs):
        raise RuntimeError("bridge not reloaded")

    def fake_batch(*args, **kwargs):
        return {
            "path": str(odb_path),
            "frame_mode": "last_frame_per_step",
            "instances": [],
            "node_sets": [],
            "element_sets": [],
            "steps": [],
            "field_stats": [
                {
                    "step": "Step-1",
                    "frame_index": 1,
                    "field": "S",
                    "metric": "MISES",
                    "scanned_count": 4,
                    "min": 0.0,
                    "max": 88.0,
                    "mean": 22.0,
                    "max_abs": 88.0,
                    "max_location": {"instance": "PART-1-1", "element_label": "1"},
                    "max_abs_location": {"instance": "PART-1-1", "element_label": "1"},
                    "truncated": False,
                }
            ],
            "history_outputs": [],
        }

    monkeypatch.setattr("material_ai_workbench.odb_postprocess.extract_odb_field_summary", fail_mcp)
    monkeypatch.setattr("material_ai_workbench.odb_postprocess.extract_odb_field_summary_batch", fake_batch)

    extraction = run_case_odb_extraction(summary, odb_path, fields=["S"], capture_contour=True)

    assert extraction["backend_requested"] == "auto"
    assert extraction["backend_used"] == "abaqus_python"
    assert extraction["backend_errors"] == ["MCP: bridge not reloaded"]
    assert extraction["aggregate"]["max_mises"] == 88.0
    assert extraction["contour_errors"]


def test_run_case_odb_frame_series_writes_outputs_and_updates_case(tmp_path, monkeypatch) -> None:
    case_dir = tmp_path / "case_source"
    case_dir.mkdir()
    odb_path = case_dir / "job.odb"
    odb_path.write_text("placeholder", encoding="utf-8")
    summary = scan_case_folder(case_dir, title="odb series case", cases_root=tmp_path / "cases")

    def fake_extract_odb_frame_series_batch(*args, **kwargs):
        assert kwargs["region_names"] == ["FIXED", "EALL"]
        return {
            "path": str(odb_path),
            "frame_mode": "all_frames_per_step_limited",
            "regions_requested": ["FIXED", "EALL"],
            "regions_found": [{"name": "FIXED", "kind": "node_set", "scope": "assembly"}],
            "steps": [{"name": "Step-1", "frame_count": 2, "sampled_frame_count": 2}],
            "rows": [
                {
                    "step": "Step-1",
                    "frame_index": 0,
                    "frame_value": 0.0,
                    "field": "S",
                    "metric": "MISES",
                    "region_name": "GLOBAL",
                    "region_kind": "global",
                    "scanned_count": 8,
                    "min": 0.0,
                    "max": 10.0,
                    "mean": 5.0,
                    "max_abs": 10.0,
                    "max_abs_location": {"instance": "PART-1-1", "element_label": "1"},
                    "truncated": False,
                },
                {
                    "step": "Step-1",
                    "frame_index": 1,
                    "frame_value": 1.0,
                    "field": "S",
                    "metric": "MISES",
                    "region_name": "FIXED",
                    "region_kind": "node_set",
                    "scanned_count": 8,
                    "min": 0.0,
                    "max": 20.0,
                    "mean": 10.0,
                    "max_abs": 20.0,
                    "max_abs_location": {"instance": "PART-1-1", "element_label": "1"},
                    "truncated": False,
                },
            ],
        }

    monkeypatch.setattr("material_ai_workbench.odb_postprocess.extract_odb_frame_series_batch", fake_extract_odb_frame_series_batch)

    series = run_case_odb_frame_series_extraction(summary, odb_path, fields=["S"], region_names=["FIXED", "EALL"], max_frames_per_step=10)
    append_odb_frame_series(summary, series)
    loaded = load_case_summary(summary.case_dir)

    assert series["row_count"] == 2
    assert series["step_count"] == 1
    assert Path(series["json_path"]).exists()
    assert Path(series["csv_path"]).exists()
    assert Path(series["report_path"]).exists()
    assert frame_series_rows(series)[1]["Max"] == 20.0
    assert frame_series_rows(series)[1]["Region"] == "FIXED"
    assert series["regions_found"][0]["name"] == "FIXED"
    assert len(loaded.odb_frame_series) == 1
    assert odb_frame_series_table_rows(loaded)[0]["行数"] == 2
