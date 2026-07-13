from __future__ import annotations

import json

from material_ai_workbench.case_library import (
    case_table_rows,
    extract_csv_result_features,
    extract_inp_features,
    file_table_rows,
    inp_feature_table_rows,
    list_cases,
    load_case_summary,
    result_feature_table_rows,
    scan_case_folder,
)


SAMPLE_INP = """** minimal Abaqus input for case-library tests
*Heading
*Part, name=PART-1
*Node
1, 0., 0., 0.
2, 1., 0., 0.
3, 1., 1., 0.
4, 0., 1., 0.
5, 0., 0., 1.
6, 1., 0., 1.
7, 1., 1., 1.
8, 0., 1., 1.
*Element, type=C3D8R
1, 1,2,3,4,5,6,7,8
*Nset, nset=FIXED
1, 4, 5, 8
*Elset, elset=EALL
1
*Solid Section, elset=EALL, material=Steel
*End Part
*Assembly, name=ASSEMBLY
*Instance, name=PART-1-1, part=PART-1
*End Instance
*Surface, type=ELEMENT, name=TOP
EALL, S2
*End Assembly
*Material, name=Steel
*Elastic
210000., 0.3
*Step, name=LoadStep
*Static
*Boundary
FIXED, 1, 3
*Cload
2, 1, 10.
*Output, field
*Node Output
U
*Element Output
S
*End Step
"""


def test_extract_inp_features_reads_model_structure(tmp_path) -> None:
    inp_path = tmp_path / "single_case.inp"
    inp_path.write_text(SAMPLE_INP, encoding="utf-8")

    features = extract_inp_features(inp_path)

    assert features["estimated_node_count"] == 8
    assert features["estimated_element_count"] == 1
    assert features["materials"] == ["Steel"]
    assert features["steps"] == ["LoadStep"]
    assert features["element_types"] == ["C3D8R"]
    assert features["load_keywords"] == ["cload"]
    assert features["boundary_keywords"] == ["boundary"]
    assert "node output" in features["output_keywords"]
    assert features["keyword_counts"]["material"] == 1


def test_scan_case_folder_indexes_files_and_inp_features(tmp_path) -> None:
    source = tmp_path / "abaqus_case"
    source.mkdir()
    (source / "model.inp").write_text(SAMPLE_INP, encoding="utf-8")
    (source / "job.odb").write_text("placeholder", encoding="utf-8")
    (source / "result.csv").write_text(
        "time,mises,PEEQ,UMAG,RF2\n0,10,0.01,0.1,-3\n1,100,0.12,0.6,-30\n",
        encoding="utf-8",
    )
    (source / "job.sta").write_text("WARNING: increment cut back\nTHE ANALYSIS HAS COMPLETED\n", encoding="utf-8")
    (source / "report.pdf").write_text("placeholder", encoding="utf-8")
    cases_root = tmp_path / "library"

    summary = scan_case_folder(
        source,
        title="thin plate validation",
        tags="Abaqus, test",
        description="fixture case",
        cases_root=cases_root,
    )
    loaded = load_case_summary(summary.case_dir)
    saved_json = json.loads((cases_root / loaded.case_id / "case_summary.json").read_text(encoding="utf-8"))

    assert loaded.file_counts["model"] == 1
    assert loaded.file_counts["result"] == 2
    assert loaded.file_counts["data"] == 1
    assert loaded.file_counts["report"] == 1
    assert loaded.inp_features["summary"]["estimated_node_count"] == 8
    assert loaded.inp_features["summary"]["estimated_element_count"] == 1
    assert loaded.inp_features["summary"]["materials"] == ["Steel"]
    assert loaded.material_type == "metal"
    assert loaded.geometry["estimated_node_count"] == 8.0
    assert loaded.geometry["estimated_element_count"] == 1.0
    assert loaded.mesh_stats["node_count"] == 8
    assert loaded.mesh_stats["element_count"] == 1
    assert loaded.abaqus_results["max_mises"] == 100.0
    assert loaded.odb_features["csv_row_count"] == 2.0
    assert saved_json["inp_features"]["summary"]["element_types"] == ["C3D8R"]
    assert loaded.result_features["summary"]["csv_file_count"] == 1
    assert loaded.result_features["summary"]["odb_file_count"] == 1
    assert loaded.result_features["summary"]["log_file_count"] == 1
    assert loaded.result_features["summary"]["csv_row_count"] == 2
    assert loaded.result_features["summary"]["max_mises"] == 100.0
    assert loaded.result_features["summary"]["max_peeq"] == 0.12
    assert loaded.result_features["summary"]["max_reaction_force"] == 30.0
    assert loaded.result_features["summary"]["warning_count"] == 1
    assert case_table_rows([loaded])[0]["文件数"] == 5
    assert len(file_table_rows(loaded, "model")) == 1
    assert inp_feature_table_rows(loaded)[0]["单元类型"] == "C3D8R"
    result_rows = result_feature_table_rows(loaded)
    assert {row["类型"] for row in result_rows} == {"csv", "odb", "log"}
    assert list_cases(cases_root)[0].case_id == loaded.case_id


def test_extract_csv_result_features_picks_common_abaqus_signals(tmp_path) -> None:
    csv_path = tmp_path / "job_result.csv"
    csv_path.write_text("frame,S_Mises,PEEQ,U_mag,RF\n1,95,0.08,0.2,-12\n2,120,0.11,0.4,-18\n", encoding="utf-8")

    features = extract_csv_result_features(csv_path)

    assert features["row_count"] == 2
    assert features["signals"]["max_mises"] == 120.0
    assert features["signals"]["max_peeq"] == 0.11
    assert features["signals"]["max_reaction_force"] == 18.0


def test_scan_single_inp_file_as_case(tmp_path) -> None:
    inp_path = tmp_path / "standalone.inp"
    inp_path.write_text(SAMPLE_INP, encoding="utf-8")
    cases_root = tmp_path / "single_file_library"

    summary = scan_case_folder(inp_path, title="standalone inp", cases_root=cases_root)

    assert len(summary.files) == 1
    assert summary.files[0].relative_path == "standalone.inp"
    assert summary.file_counts["model"] == 1
    assert summary.inp_features["summary"]["inp_file_count"] == 1
    assert summary.inp_features["summary"]["steps"] == ["LoadStep"]
