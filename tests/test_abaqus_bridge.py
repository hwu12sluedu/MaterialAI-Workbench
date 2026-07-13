from __future__ import annotations

import json
from types import SimpleNamespace

from material_ai_workbench.abaqus_bridge import AbaqusBridgeConfig, run_abaqus_verification


def test_run_abaqus_verification_tolerates_empty_stdout(tmp_path, monkeypatch) -> None:
    run_dir = tmp_path / "run"
    model_dir = run_dir / "models"
    model_dir.mkdir(parents=True)
    csv_path = model_dir / "abq_demo-svm.csv"
    meta_path = model_dir / "abq_demo-svm_meta.json"
    csv_path.write_text("1,2,3\n", encoding="utf-8")
    meta_path.write_text(json.dumps({"Model": {"Names": ["Ndata"], "Parameters": [1]}}), encoding="utf-8")
    (run_dir / "summary.json").write_text(
        json.dumps(
            {
                "ml_material": {"name": "demo"},
                "outputs": {
                    "umat_csv": str(csv_path),
                    "umat_meta_json": str(meta_path),
                },
            }
        ),
        encoding="utf-8",
    )

    def fake_run(*args, **kwargs):
        return SimpleNamespace(returncode=0, stdout=None)

    monkeypatch.setattr("material_ai_workbench.abaqus_bridge.subprocess.run", fake_run)

    result = run_abaqus_verification(
        AbaqusBridgeConfig(
            run_dir=run_dir,
            abaqus_bat=tmp_path / "abaqus.bat",
            timeout_seconds=1,
        )
    )

    assert result.status == "completed_no_result_csv"
    assert result.log_path is not None
    assert result.log_path.read_text(encoding="utf-8") == ""
