from __future__ import annotations

import json
from pathlib import Path

import jsonschema

from material_ai_workbench import case_package
from material_ai_workbench.case_library import load_case_summary, scan_case_folder

SAMPLE_INP = """*Heading
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
*Elset, elset=EALL
1
*Solid Section, elset=EALL, material=Steel
*End Part
*Material, name=Steel
*Elastic
210000., 0.3
*Step, name=Load
*Static
*Cload
2, 1, 10.
*End Step
"""


def _write_case_files(source: Path, *, failed: bool = False) -> None:
    source.mkdir()
    (source / "plate.inp").write_text(SAMPLE_INP, encoding="utf-8")
    (source / "plate.odb").write_bytes(b"ODB placeholder")
    (source / "plate.csv").write_text(
        "frame,S_Mises,PEEQ,U_mag,RF\n0,10,0.0,0.0,0\n1,120,0.08,0.4,-20\n",
        encoding="utf-8",
    )
    message = (
        "Abaqus JOB plate IS ABORTED\nERROR: numerical singularity\n"
        if failed
        else "THE ANALYSIS HAS COMPLETED SUCCESSFULLY\n"
    )
    (source / "plate.sta").write_text(message, encoding="utf-8")


def test_file_fingerprint_switches_to_bounded_sampling(tmp_path, monkeypatch) -> None:
    monkeypatch.setattr(case_package, "FULL_HASH_LIMIT_BYTES", 64)
    monkeypatch.setattr(case_package, "SAMPLED_HASH_BYTES", 16)
    small = tmp_path / "small.inp"
    large = tmp_path / "large.odb"
    small.write_bytes(b"small model")
    large.write_bytes(bytes(range(200)))

    small_hash, small_mode = case_package.fingerprint_file(small)
    large_hash, large_mode = case_package.fingerprint_file(large)

    assert len(small_hash) == 64
    assert len(large_hash) == 64
    assert small_mode == "sha256-full"
    assert large_mode == "sha256-size-first-last-1MiB"


def test_complete_case_writes_valid_training_eligible_v2_package(tmp_path) -> None:
    source = tmp_path / "complete"
    _write_case_files(source)

    summary = scan_case_folder(
        source,
        title="3D plate-hole validation",
        tags=["Abaqus", "plate-hole"],
        units="mm-N-s-MPa",
        solver_version="2024",
        cases_root=tmp_path / "library",
    )
    package_path = Path(summary.case_dir) / "case_package.json"
    package = json.loads(package_path.read_text(encoding="utf-8"))
    schema = json.loads(
        (Path(__file__).parents[1] / "schemas" / "case_package.schema.json").read_text(
            encoding="utf-8"
        )
    )

    jsonschema.Draft202012Validator(schema).validate(package)
    assert summary.schema_version == "2.0"
    assert summary.quality["execution_state"] == "solved"
    assert summary.quality["training_eligible"] is True
    assert summary.units["stress"] == "MPa"
    assert summary.solver["version"] == "2024"
    assert len(summary.source_fingerprint) == 64
    assert all(len(item.fingerprint) == 64 for item in summary.files)
    assert package["results"]["labels"]["max_mises"] == 120.0


def test_incomplete_case_is_not_training_truth(tmp_path) -> None:
    source = tmp_path / "prepared"
    source.mkdir()
    (source / "model.inp").write_text(SAMPLE_INP, encoding="utf-8")

    summary = scan_case_folder(
        source,
        title="prepared model only",
        cases_root=tmp_path / "library",
    )

    assert summary.quality["execution_state"] == "prepared"
    assert summary.quality["training_eligible"] is False
    assert "units_not_declared" in summary.quality["blocking_reasons"]
    assert "numeric_targets_missing" in summary.quality["blocking_reasons"]


def test_failed_solver_evidence_blocks_training(tmp_path) -> None:
    source = tmp_path / "failed"
    _write_case_files(source, failed=True)

    summary = scan_case_folder(
        source,
        title="failed run",
        units="SI",
        cases_root=tmp_path / "library",
    )

    assert summary.quality["execution_state"] == "failed"
    assert summary.quality["training_eligible"] is False
    assert "solver_error_or_abort_detected" in summary.quality["blocking_reasons"]


def test_old_summary_without_v2_fields_remains_loadable(tmp_path) -> None:
    source = tmp_path / "legacy-source"
    _write_case_files(source)
    summary = scan_case_folder(
        source,
        title="legacy fixture",
        units="mm-N-s-MPa",
        cases_root=tmp_path / "library",
    )
    summary_path = Path(summary.case_dir) / "case_summary.json"
    payload = json.loads(summary_path.read_text(encoding="utf-8"))
    for key in (
        "schema_version",
        "source_fingerprint",
        "units",
        "solver",
        "provenance",
        "quality",
    ):
        payload.pop(key)
    for item in payload["files"]:
        item.pop("fingerprint")
        item.pop("fingerprint_mode")
    summary_path.write_text(json.dumps(payload), encoding="utf-8")

    loaded = load_case_summary(summary.case_dir)

    assert loaded.schema_version == "2.0"
    assert loaded.source_fingerprint == ""
    assert loaded.files[0].fingerprint == ""


def test_custom_unit_name_without_dimensions_is_not_training_declaration() -> None:
    units = case_package.normalize_case_units("custom-mm-kN")

    assert units["system"] == "custom-mm-kN"
    assert units["declared"] is False
