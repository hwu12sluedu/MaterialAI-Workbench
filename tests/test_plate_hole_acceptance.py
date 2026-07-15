from __future__ import annotations

import json
from pathlib import Path
from types import SimpleNamespace

import pytest
from jsonschema import Draft202012Validator

import material_ai_workbench.plate_hole_acceptance as acceptance
from material_ai_workbench.plate_hole_acceptance import (
    PlateHoleAcceptanceConfig,
    resume_plate_hole_acceptance,
    run_plate_hole_acceptance,
)


def _fake_diagnostic(tmp_path: Path) -> SimpleNamespace:
    return SimpleNamespace(
        overall_status="partial",
        batch_ready=True,
        mcp_ready=False,
        json_path=tmp_path / "diagnostics.json",
        markdown_path=tmp_path / "diagnostics.md",
    )


def _config(tmp_path: Path, **overrides) -> PlateHoleAcceptanceConfig:
    values = {
        "name": "test_plate_hole",
        "output_root": tmp_path / "runs",
        "cases_root": tmp_path / "cases",
        "abaqus_bat": tmp_path / "abaqus.bat",
        "smapython": tmp_path / "SMAPython.exe",
    }
    values.update(overrides)
    return PlateHoleAcceptanceConfig(**values)


def test_prepare_creates_auditable_assets_without_claiming_a_solve(
    tmp_path: Path, monkeypatch
) -> None:
    monkeypatch.setattr(
        acceptance,
        "run_abaqus_diagnostics",
        lambda _config: _fake_diagnostic(tmp_path),
    )
    result = run_plate_hole_acceptance(_config(tmp_path), execute=False)

    assert result.status == "prepared"
    assert result.config_path.is_file()
    assert result.build_script_path.is_file()
    assert result.postprocess_script_path.is_file()
    assert result.run_script_path.is_file()
    manifest = json.loads(result.manifest_path.read_text(encoding="utf-8"))
    schema = json.loads(
        Path("schemas/acceptance_manifest.schema.json").read_text(encoding="utf-8")
    )
    Draft202012Validator(schema).validate(manifest)
    assert manifest["stages"]["prepare"]["status"] == "pass"
    assert manifest["stages"]["solve"]["status"] == "pending"
    assert not Path(manifest["artifacts"]["odb"]).exists()

    build_source = result.build_script_path.read_text(encoding="utf-8")
    post_source = result.postprocess_script_path.read_text(encoding="utf-8")
    assert "C3D10" in build_source
    assert "HOLE_ROI" in build_source
    assert "LOAD_FACE_NODES" in build_source
    assert "PEEQ" in post_source
    assert "stress_concentration_ratio" in post_source


def test_build_only_state_does_not_claim_solver_success(
    tmp_path: Path, monkeypatch
) -> None:
    monkeypatch.setattr(
        acceptance,
        "run_abaqus_diagnostics",
        lambda _config: _fake_diagnostic(tmp_path),
    )

    def fake_build(_config, paths, _run_dir):
        paths["cae"].write_bytes(b"cae")
        paths["inp"].write_text("*HEADING", encoding="ascii")
        paths["build_summary"].write_text('{"ok": true}', encoding="ascii")
        return {"backend": "batch", "returncode": 0}

    monkeypatch.setattr(acceptance, "_execute_build", fake_build)
    abaqus_bat = tmp_path / "abaqus.bat"
    abaqus_bat.write_text("stub", encoding="ascii")
    result = run_plate_hole_acceptance(
        _config(tmp_path, abaqus_bat=abaqus_bat, submit_job=False),
        execute=True,
    )

    assert result.status == "built"
    assert result.manifest["stages"]["build"]["status"] == "pass"
    assert result.manifest["stages"]["solve"]["status"] == "skipped"
    assert result.manifest["results"] == {}


def test_resume_uses_persisted_configuration(tmp_path: Path, monkeypatch) -> None:
    monkeypatch.setattr(
        acceptance,
        "run_abaqus_diagnostics",
        lambda _config: _fake_diagnostic(tmp_path),
    )
    prepared = run_plate_hole_acceptance(_config(tmp_path), execute=False)
    resumed = resume_plate_hole_acceptance(
        prepared.run_dir, execute=False, backend="batch"
    )

    assert resumed.run_dir == prepared.run_dir
    assert resumed.status == "prepared"
    assert resumed.manifest["run_id"] == prepared.manifest["run_id"]


def test_resume_does_not_duplicate_an_existing_case_archive(
    tmp_path: Path, monkeypatch
) -> None:
    monkeypatch.setattr(
        acceptance,
        "run_abaqus_diagnostics",
        lambda _config: _fake_diagnostic(tmp_path),
    )
    abaqus_bat = tmp_path / "abaqus.bat"
    abaqus_bat.write_text("stub", encoding="ascii")
    prepared = run_plate_hole_acceptance(
        _config(tmp_path, abaqus_bat=abaqus_bat), execute=False
    )
    manifest = json.loads(prepared.manifest_path.read_text(encoding="utf-8"))
    manifest["case_id"] = "existing-case"
    manifest["stages"]["archive"] = {
        "status": "pass",
        "message": "already archived",
        "updated_at": "2026-07-15T12:00:00",
        "evidence": {
            "case_id": "existing-case",
            "case_dir": str(tmp_path / "cases" / "existing-case"),
        },
    }
    prepared.manifest_path.write_text(json.dumps(manifest), encoding="utf-8")
    artifacts = manifest["artifacts"]
    Path(artifacts["odb"]).write_bytes(b"odb-evidence")

    def fake_postprocess(_config, paths, _run_dir):
        payload = {
            "ok": True,
            "results": {
                "max_mises_mpa": 300.0,
                "max_displacement_mm": 0.3501,
                "reaction_force_n": 53_000.0,
                "stress_concentration_ratio": 1.4,
                "max_peeq": 0.07,
            },
        }
        paths["result_json"].write_text(json.dumps(payload), encoding="utf-8")
        return {"returncode": 0}

    monkeypatch.setattr(acceptance, "_execute_postprocess", fake_postprocess)
    monkeypatch.setattr(
        acceptance,
        "scan_case_folder",
        lambda *args, **kwargs: (_ for _ in ()).throw(
            AssertionError("archive must not be duplicated")
        ),
    )
    resumed = resume_plate_hole_acceptance(
        prepared.run_dir,
        execute=True,
        submit_job=True,
        archive_case=True,
    )

    assert resumed.status == "archived"
    assert resumed.manifest["case_id"] == "existing-case"
    assert "无需重复索引" in resumed.manifest["stages"]["archive"]["message"]


@pytest.mark.parametrize(
    ("field", "value"),
    [
        ("hole_radius", 24.0),
        ("mesh_size", 6.0),
        ("poisson_ratio", 0.5),
        ("cpus", 0),
    ],
)
def test_invalid_acceptance_configuration_is_rejected(
    tmp_path: Path, field: str, value
) -> None:
    with pytest.raises(ValueError):
        run_plate_hole_acceptance(_config(tmp_path, **{field: value}), execute=False)


def test_engineering_validation_accepts_a_consistent_result() -> None:
    check = acceptance._engineering_validation(
        PlateHoleAcceptanceConfig(displacement=0.35),
        {
            "max_mises_mpa": 300.0,
            "max_displacement_mm": 0.3501,
            "reaction_force_n": 53_000.0,
            "stress_concentration_ratio": 1.4,
            "max_peeq": 0.07,
        },
    )

    assert check["status"] == "pass"
    assert all(item["passed"] for item in check["checks"])
